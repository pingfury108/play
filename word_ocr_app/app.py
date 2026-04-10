"""
单词 OCR 识别应用
Flask 主应用
"""

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# 加载环境变量
BASE_DIR = Path(__file__).parent
env_path = BASE_DIR / ".env"
load_dotenv(env_path)

# 添加当前目录到路径以支持导入
sys.path.insert(0, str(BASE_DIR))

# 导入模型和服务
from models import init_db, Task, Image, WordEntry
from services.ai_service import AIService
from services.ocr_processor import OCRProcessor
from services.translator import Translator
from services.excel_exporter import ExcelExporter

app = Flask(__name__)
CORS(app)

# 上传目录
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# 初始化数据库
init_db()


@app.route("/")
def index():
    """首页"""
    return render_template("word_ocr.html")


# ========== 任务管理 API ==========


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    """获取任务列表"""
    tasks = Task.list_all()

    # 补充每个任务的图片信息
    for task in tasks:
        images = Image.list_by_task(task["id"])
        task["image_count"] = len(images)
        task["processed_count"] = len(
            [img for img in images if img["status"] == "completed"]
        )

    return jsonify({"success": True, "tasks": tasks})


@app.route("/api/tasks", methods=["POST"])
def create_task():
    """创建新任务"""
    data = request.get_json()
    name = data.get("name", "").strip()

    if not name:
        # 自动生成名称
        name = f"任务 {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    task = Task.create(name)
    return jsonify({"success": True, "task": task})


@app.route("/api/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    """获取任务详情"""
    task = Task.get_by_id(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    images = Image.list_by_task(task_id)
    task["images"] = images

    return jsonify({"success": True, "task": task})


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    """删除任务"""
    # 获取任务图片并删除文件 (stored_path 是相对路径)
    images = Image.list_by_task(task_id)
    for img in images:
        try:
            full_path = BASE_DIR / img["stored_path"]
            full_path.unlink(missing_ok=True)
        except:
            pass

    # 删除数据库记录（级联删除）
    import sqlite3
    from models import get_db

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM word_entries WHERE task_id = ?", (task_id,))
    cursor.execute("DELETE FROM images WHERE task_id = ?", (task_id,))
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


# ========== 图片管理 API ==========


@app.route("/api/upload", methods=["POST"])
def upload_images():
    """上传图片，自动创建任务"""
    if "images" not in request.files:
        return jsonify({"success": False, "error": "没有上传文件"}), 400

    files = request.files.getlist("images")
    if not files or all(f.filename == "" for f in files):
        return jsonify({"success": False, "error": "没有选择文件"}), 400

    # 自动创建任务，使用第一个文件名作为任务名
    first_filename = Path(files[0].filename).stem if files[0].filename else "未命名"
    task_name = f"{first_filename}"
    task = Task.create(task_name)
    task_id = task["id"]

    uploaded = []
    task_upload_dir = UPLOAD_FOLDER / task_id
    task_upload_dir.mkdir(exist_ok=True)

    for file in files:
        if file.filename == "":
            continue

        # 生成唯一文件名
        ext = Path(file.filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]:
            continue

        filename = f"{uuid.uuid4().hex[:8]}{ext}"
        stored_path = task_upload_dir / filename
        file.save(stored_path)

        # 保存相对路径到数据库 (相对于应用根目录)
        relative_path = f"static/uploads/{task_id}/{filename}"
        image = Image.create(
            task_id=task_id, filename=file.filename, stored_path=relative_path
        )
        uploaded.append(image)

    return jsonify({"success": True, "task": task, "images": uploaded})


@app.route("/api/tasks/<task_id>/upload", methods=["POST"])
def append_images(task_id):
    """向现有任务追加图片"""
    task = Task.get_by_id(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    if "images" not in request.files:
        return jsonify({"success": False, "error": "没有上传文件"}), 400

    files = request.files.getlist("images")
    uploaded = []
    task_upload_dir = UPLOAD_FOLDER / task_id
    task_upload_dir.mkdir(exist_ok=True)

    for file in files:
        if file.filename == "":
            continue

        ext = Path(file.filename).suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]:
            continue

        filename = f"{uuid.uuid4().hex[:8]}{ext}"
        stored_path = task_upload_dir / filename
        file.save(stored_path)

        # 保存相对路径到数据库
        relative_path = f"static/uploads/{task_id}/{filename}"
        image = Image.create(
            task_id=task_id, filename=file.filename, stored_path=relative_path
        )
        uploaded.append(image)

    return jsonify({"success": True, "images": uploaded})


@app.route("/api/images/<image_id>", methods=["DELETE"])
def delete_image(image_id):
    """删除图片"""
    image = Image.get_by_id(image_id)
    if not image:
        return jsonify({"success": False, "error": "图片不存在"}), 404

    # 删除文件 (stored_path 是相对路径，需要拼接 BASE_DIR)
    try:
        full_path = BASE_DIR / image["stored_path"]
        full_path.unlink(missing_ok=True)
    except:
        pass

    # 删除数据库记录
    import sqlite3
    from models import get_db

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM word_entries WHERE image_id = ?", (image_id,))
    cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
    conn.commit()
    conn.close()

    return jsonify({"success": True})


# ========== 处理 API ==========


@app.route("/api/tasks/<task_id>/process", methods=["POST"])
def process_task(task_id):
    """处理任务中的所有待处理图片"""
    print(f"[DEBUG] 开始处理任务: {task_id}")
    
    task = Task.get_by_id(task_id)
    if not task:
        print(f"[ERROR] 任务不存在: {task_id}")
        return jsonify({"success": False, "error": "任务不存在"}), 404

    # 获取待处理图片
    pending_images = Image.list_pending_by_task(task_id)
    print(f"[DEBUG] 待处理图片数: {len(pending_images)}")
    
    if not pending_images:
        return jsonify({"success": True, "message": "没有待处理的图片", "processed": 0})

    # 更新任务状态
    Task.update_status(task_id, "processing")

    # 初始化处理器
    print("[DEBUG] 初始化 AI 服务...")
    try:
        ai_service = AIService()
        processor = OCRProcessor(ai_service)
        translator = Translator(ai_service)
        print("[DEBUG] AI 服务初始化完成")
    except Exception as e:
        print(f"[ERROR] AI 服务初始化失败: {str(e)}")
        Task.update_status(task_id, "pending")
        return jsonify({"success": False, "error": f"AI 服务初始化失败: {str(e)}"}), 500

    # 处理每张图片
    processed = 0
    failed = 0

    for image in pending_images:
        print(f"[DEBUG] 处理图片: {image['id']} - {image['filename']}")
        try:
            success = processor.process_image(image["id"])
            if success:
                processed += 1
                print(f"[DEBUG] 图片处理成功: {image['id']}")
            else:
                failed += 1
                print(f"[DEBUG] 图片处理失败: {image['id']}")
        except Exception as e:
            print(f"[ERROR] 处理图片异常: {str(e)}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"[DEBUG] 图片处理完成: 成功 {processed}, 失败 {failed}")

    # 翻译所有条目
    print("[DEBUG] 开始翻译...")
    try:
        translator.translate_entries(task_id)
        print("[DEBUG] 翻译完成")
    except Exception as e:
        print(f"[ERROR] 翻译失败: {str(e)}")
        import traceback
        traceback.print_exc()

    # 更新任务状态
    final_status = "completed" if failed == 0 and processed > 0 else ("partial" if processed > 0 else "pending")
    Task.update_status(task_id, final_status)
    print(f"[DEBUG] 任务状态更新为: {final_status}")

    return jsonify(
        {
            "success": True,
            "processed": processed,
            "failed": failed,
            "message": f"处理完成: 成功 {processed}, 失败 {failed}",
        }
    )


# ========== 数据查询 API ==========


@app.route("/api/tasks/<task_id>/entries", methods=["GET"])
def list_entries(task_id):
    """获取任务的所有单词条目"""
    task = Task.get_by_id(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    entries = WordEntry.list_by_task(task_id)
    return jsonify({"success": True, "entries": entries})


@app.route("/api/tasks/<task_id>/stats", methods=["GET"])
def get_stats(task_id):
    """获取任务统计信息"""
    task = Task.get_by_id(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    stats = ExcelExporter.get_export_stats(task_id)
    return jsonify({"success": True, "stats": stats})


# ========== 导出 API ==========


@app.route("/api/tasks/<task_id>/export", methods=["GET"])
def export_excel(task_id):
    """导出任务为 Excel"""
    task = Task.get_by_id(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    try:
        output_path = UPLOAD_FOLDER / f"{task_id}_export.xlsx"
        ExcelExporter.export_task(task_id, str(output_path))

        return send_file(
            output_path,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"{task['name']}.xlsx",
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/tasks/<task_id>/preview", methods=["GET"])
def preview_data(task_id):
    """预览数据"""
    task = Task.get_by_id(task_id)
    if not task:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    preview = ExcelExporter.get_preview_data(task_id, limit=50)
    return jsonify({"success": True, "preview": preview})


if __name__ == "__main__":
    port = 5003
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"错误: 无效的端口号 '{sys.argv[1]}'，使用默认端口 5003")

    print(f"启动单词 OCR 识别服务，访问 http://localhost:{port}")
    app.run(debug=True, host="0.0.0.0", port=port)
