"""
翻译服务
为单词条目补充翻译
"""

from services.ai_service import AIService
from models import WordEntry


class Translator:
    """翻译服务"""

    def __init__(self, ai_service: AIService = None):
        self.ai_service = ai_service or AIService()

    def translate_entries(self, task_id: str) -> int:
        """
        为任务中所有未翻译的条目补充翻译

        Args:
            task_id: 任务 ID

        Returns:
            翻译的条目数量
        """
        # 获取所有需要翻译的条目
        entries = WordEntry.list_by_task(task_id)
        untranslated = [e for e in entries if not e.get("translation")]

        if not untranslated:
            print(f"[INFO] 没有需要翻译的条目")
            return 0

        print(f"[INFO] 开始翻译 {len(untranslated)} 个条目")
        count = 0

        for entry in untranslated:
            try:
                original_text = entry["original_text"]
                print(f"[INFO] 翻译: {original_text[:50]}...")

                translation = self.ai_service.translate_text(original_text)

                # 更新数据库
                WordEntry.update_translation(entry["id"], translation)
                count += 1

            except Exception as e:
                print(f"[ERROR] 翻译失败 (entry_id={entry['id']}): {str(e)}")
                continue

        print(f"[INFO] 翻译完成: {count}/{len(untranslated)}")
        return count

    def translate_single(self, entry_id: int) -> str:
        """
        翻译单个条目

        Args:
            entry_id: 条目 ID

        Returns:
            翻译结果
        """
        entry = WordEntry.get_by_id(entry_id)
        if not entry:
            raise Exception(f"条目不存在: {entry_id}")

        translation = self.ai_service.translate_text(entry["original_text"])
        WordEntry.update_translation(entry_id, translation)

        return translation
