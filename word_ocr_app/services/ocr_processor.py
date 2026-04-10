"""
OCR 处理器
处理图片识别和数据整理
"""

from pathlib import Path
from services.ai_service import AIService
from models import Image, WordEntry

# 应用根目录
APP_DIR = Path(__file__).parent.parent


class OCRProcessor:
    """OCR 处理器"""

    def __init__(self, ai_service: AIService = None):
        self.ai_service = ai_service or AIService()

    def process_image(self, image_id: str) -> bool:
        """
        处理单张图片

        Args:
            image_id: 图片 ID

        Returns:
            是否成功
        """
        # 获取图片信息
        image = Image.get_by_id(image_id)
        if not image:
            print(f"[ERROR] 图片不存在: {image_id}")
            return False

        print(f"[INFO] 开始处理图片: {image['filename']} (ID: {image_id})")
        print(f"[DEBUG] stored_path: {image['stored_path']}")
        
        try:
            # 调用 AI 识别 (stored_path 是相对路径，需要拼接完整路径)
            full_path = APP_DIR / image["stored_path"]
            print(f"[DEBUG] 完整路径: {full_path}")
            
            # 检查文件是否存在
            if not full_path.exists():
                print(f"[ERROR] 文件不存在: {full_path}")
                Image.update_status(image_id, "failed")
                return False
            
            print(f"[INFO] 调用 AI 识别...")
            ocr_result = self.ai_service.recognize_image(str(full_path))
            print(f"[INFO] 识别成功: {ocr_result}")

            # 保存 OCR 结果
            Image.update_status(image_id, "completed", ocr_result)

            # 解析并保存单词条目
            self._save_word_entries(image["task_id"], image_id, ocr_result)

            return True

        except Exception as e:
            print(f"[ERROR] 处理图片失败: {str(e)}")
            import traceback
            traceback.print_exc()
            Image.update_status(image_id, "failed")
            return False

    def _save_word_entries(self, task_id: str, image_id: str, ocr_result: dict):
        """
        保存单词条目到数据库

        Args:
            task_id: 任务 ID
            image_id: 图片 ID
            ocr_result: OCR 识别结果
        """
        word = ocr_result.get("word", "")
        cet4_count = ocr_result.get("cet4_count", 0)
        examples = ocr_result.get("examples", [])

        if not word:
            print(f"[WARN] 未识别到单词")
            return

        # 为每个例句创建条目（按图片从上到下顺序，seq_num 从 1 开始递增）
        for index, example in enumerate(examples, start=1):
            # seq_num 是顺序号（1, 2, 3...），不是真题题号
            seq_num = index
            original_text = example.get("original_text", "")
            source = example.get("source", "")

            if not original_text:
                continue

            # 创建条目（翻译暂时为空，后续补充）
            WordEntry.create(
                task_id=task_id,
                image_id=image_id,
                word=word,
                cet4_count=cet4_count,
                seq_num=seq_num,
                original_text=original_text,
                source=source,
                translation=None,
            )
            print(f"[INFO] 保存条目: {word} - 顺序号 {seq_num}")
