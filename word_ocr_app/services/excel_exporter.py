"""
Excel 导出服务
导出单词数据为 Excel 格式
"""

import pandas as pd
from models import WordEntry


class ExcelExporter:
    """Excel 导出器"""

    @staticmethod
    def export_task(task_id: str, output_path: str = None) -> str:
        """
        导出任务数据为 Excel

        Args:
            task_id: 任务 ID
            output_path: 输出路径，默认为 {task_id}.xlsx

        Returns:
            输出文件路径
        """
        if output_path is None:
            output_path = f"{task_id}.xlsx"

        # 获取所有条目
        entries = WordEntry.list_by_task(task_id)

        if not entries:
            raise Exception("没有可导出的数据")

        # 准备数据
        data = []
        for entry in entries:
            data.append(
                {
                    "单词": entry["word"],
                    "CET4图片链接": "",  # 保持为空
                    "cet4出现次数": entry["cet4_count"],
                    "真题序号": entry["seq_num"],
                    "OCR识别题目原文": entry["original_text"],
                    "来源": entry["source"] or "",
                    "翻译": entry["translation"] or "",
                }
            )

        # 创建 DataFrame
        df = pd.DataFrame(data)

        # 导出 Excel
        df.to_excel(output_path, index=False, engine="openpyxl")

        return output_path

    @staticmethod
    def get_preview_data(task_id: str, limit: int = 100) -> list:
        """
        获取预览数据

        Args:
            task_id: 任务 ID
            limit: 限制条数

        Returns:
            数据列表
        """
        entries = WordEntry.list_by_task(task_id)

        data = []
        for entry in entries[:limit]:
            # 原文保留完整内容，点击后在模态框中查看
            data.append(
                {
                    "单词": entry["word"],
                    "CET4图片链接": "",  # 保持为空
                    "cet4出现次数": entry["cet4_count"],
                    "真题序号": entry["seq_num"],
                    "OCR识别题目原文": entry["original_text"],
                    "来源": entry["source"] or "",
                    "翻译": entry["translation"] or "",
                }
            )

        return data

    @staticmethod
    def get_export_stats(task_id: str) -> dict:
        """
        获取导出统计信息

        Args:
            task_id: 任务 ID

        Returns:
            统计信息
        """
        entries = WordEntry.list_by_task(task_id)

        total = len(entries)
        translated = len([e for e in entries if e.get("translation")])
        words = list(set([e["word"] for e in entries]))

        return {
            "total_entries": total,
            "translated_entries": translated,
            "unique_words": len(words),
            "words": words,
        }
