import os
import re
import sys
import traceback
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
env_path = BASE_DIR / ".env"
load_dotenv(env_path)

sys.path.insert(0, str(BASE_DIR))

from models import init_db, Dictionary, Entry

app = Flask(__name__, template_folder="templates")
CORS(app)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB max file size

UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

init_db()

DEFAULT_CSS = """
<style>
.mdict-entry { font-family: Georgia, "Times New Roman", serif; line-height: 1.7; color: #333; }
.mdict-entry main, .mdict-entry dl, .mdict-entry dt, .mdict-entry dd { display: block; }
.mdict-entry .hw { font-size: 1.4em; font-weight: bold; color: #1a1a1a; }
.mdict-entry h-word { font-size: 1.4em; font-weight: bold; color: #1a1a1a; }
.mdict-entry hyph { color: #666; font-style: italic; margin-left: 8px; }
.mdict-entry .pron { color: #007bff; font-family: "Segoe UI", sans-serif; margin-left: 6px; }
.mdict-entry x-gram { display: inline-block; background: #f0f0f0; color: #555; padding: 1px 6px; border-radius: 4px; font-size: 0.9em; margin: 8px 0 4px; }
.mdict-entry dt { margin: 6px 0 4px 0; }
.mdict-entry dd { margin: 0 0 6px 16px; color: #444; }
.mdict-entry .num { color: #888; margin-right: 4px; }
.mdict-entry .chn { color: #2b2b2b; }
.mdict-entry x-source { display: block; color: #555; font-style: italic; margin: 2px 0; }
.mdict-entry .s-dot, .mdict-entry .s-squre { color: #007bff; margin-right: 4px; }
.mdict-entry a { color: #007bff; text-decoration: none; }
.mdict-entry a:hover { text-decoration: underline; }
</style>
"""


def inject_default_css(html: str) -> str:
    """移除外部 link 标签，注入兜底 CSS"""
    html = re.sub(
        r'<link[^>]*?href=["\'][^"\']*\.css["\'][^>]*?>', "", html, flags=re.IGNORECASE
    )
    if "<style" not in html:
        html = DEFAULT_CSS + html
    return html


def parse_mdx(file_path):
    from mdict_utils.reader import MDX

    m = MDX(str(file_path))
    header = m.header or {}
    title = header.get("Title", "")
    version = header.get("GeneratedByEngineVersion", "")

    entries = []
    for key, value in m.items():
        keyword = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        content = value.decode("utf-8") if isinstance(value, bytes) else str(value)
        entries.append({"keyword": keyword, "content_html": content})

    return {
        "title": title,
        "version": version,
        "entry_count": len(entries),
        "entries": entries,
    }


@app.route("/")
def index():
    return render_template("mdict.html")


@app.route("/api/dictionaries", methods=["GET"])
def list_dictionaries():
    return jsonify({"success": True, "dictionaries": Dictionary.list_all()})


@app.route("/api/dictionaries", methods=["POST"])
def upload_dictionary():
    if "mdx_file" not in request.files:
        return jsonify({"success": False, "error": "没有上传文件"}), 400

    file = request.files["mdx_file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "没有选择文件"}), 400

    ext = Path(file.filename).suffix.lower()
    if ext != ".mdx":
        return jsonify({"success": False, "error": "仅支持 .mdx 格式文件"}), 400

    try:
        stored_path = UPLOAD_FOLDER / file.filename
        file.save(stored_path)

        parsed = parse_mdx(stored_path)

        dictionary = Dictionary.create(
            name=Path(file.filename).stem,
            filename=file.filename,
            title=parsed.get("title") or Path(file.filename).stem,
            version=parsed.get("version"),
            entry_count=parsed.get("entry_count", 0),
        )
        dict_id = dictionary["id"]

        # batch insert with dict_id
        batch_size = 500
        raw_entries = parsed["entries"]
        for i in range(0, len(raw_entries), batch_size):
            batch = [
                {
                    "dict_id": dict_id,
                    "keyword": e["keyword"],
                    "content_html": e["content_html"],
                }
                for e in raw_entries[i : i + batch_size]
            ]
            Entry.insert_many(batch)

        Dictionary.update_entry_count(dict_id, len(raw_entries))

        return jsonify({"success": True, "dictionary": dictionary})
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[UPLOAD ERROR] {error_detail}")
        return jsonify({"success": False, "error": str(e), "detail": error_detail}), 500


@app.route("/api/dictionaries/<dict_id>", methods=["DELETE"])
def delete_dictionary(dict_id):
    dictionary = Dictionary.get_by_id(dict_id)
    if not dictionary:
        return jsonify({"success": False, "error": "字典不存在"}), 404

    try:
        # delete db entries
        Entry.delete_by_dict(dict_id)
        Dictionary.delete(dict_id)

        # delete uploaded file
        file_path = UPLOAD_FOLDER / dictionary["filename"]
        if file_path.exists():
            file_path.unlink()

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dictionaries/<dict_id>/entries", methods=["GET"])
def list_entries(dict_id):
    dictionary = Dictionary.get_by_id(dict_id)
    if not dictionary:
        return jsonify({"success": False, "error": "字典不存在"}), 404

    keyword = request.args.get("keyword", "").strip()
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 50))
    except ValueError:
        page = 1
        page_size = 50

    offset = (page - 1) * page_size

    if keyword:
        result = Entry.search(dict_id, keyword, limit=page_size, offset=offset)
    else:
        result = Entry.list_by_dict(dict_id, limit=page_size, offset=offset)

    return jsonify(
        {
            "success": True,
            "entries": result["items"],
            "total": result["total"],
            "page": page,
            "page_size": page_size,
        }
    )


@app.route("/api/entries/<entry_id>", methods=["GET"])
def get_entry(entry_id):
    entry = Entry.get_by_id(entry_id)
    if not entry:
        return jsonify({"success": False, "error": "词条不存在"}), 404
    entry["content_html"] = inject_default_css(entry["content_html"])
    return jsonify({"success": True, "entry": entry})


if __name__ == "__main__":
    port = 5004
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"错误: 无效的端口号 '{sys.argv[1]}'，使用默认端口 5004")

    print(f"启动 MDict 字典浏览服务，访问 http://localhost:{port}")
    app.run(debug=True, host="0.0.0.0", port=port)
