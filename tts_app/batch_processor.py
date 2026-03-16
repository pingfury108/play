"""
批量 TTS 处理模块
支持分页处理和进度跟踪
"""

import os
import json
import asyncio
import threading
import zipfile
from pathlib import Path
from datetime import datetime
import pandas as pd

# 导入 TTS 功能
from tts_core import text_to_speech

# 发音人配置
VOICE_AMANDA = "x4_enuk_amanda_education"
VOICE_GAVIN = "x4_enus_gavin_assist"
VOICE_CATHERINE = "x4_enus_catherine_profnews"

# 全局任务状态存储
batch_tasks = {}


class BatchProcessor:
    """批量处理器"""

    def __init__(self, task_id, vocab_file, examples_file, output_dir, limit=None):
        self.task_id = task_id
        self.vocab_file = vocab_file
        self.examples_file = examples_file
        self.output_dir = output_dir
        self.limit = limit  # 处理数量限制

        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)

        # 读取数据
        self.vocab_df = pd.read_excel(vocab_file)
        self.examples_df = pd.read_excel(examples_file)

        # 如果有数量限制，只取前N个
        if limit and limit > 0:
            self.vocab_df = self.vocab_df.head(limit)

        # 状态
        self.status = "pending"  # pending, running, paused, completed, error
        self.current_index = 0
        self.total_count = len(self.vocab_df)
        self.processed_words = []
        self.errors = []
        self.start_time = None
        self.end_time = None

        # 锁
        self._lock = threading.Lock()

    def get_status(self):
        """获取当前状态"""
        with self._lock:
            return {
                "task_id": self.task_id,
                "status": self.status,
                "current": self.current_index,
                "total": self.total_count,
                "progress": round(self.current_index / self.total_count * 100, 2)
                if self.total_count > 0
                else 0,
                "processed_words": self.processed_words,
                "errors": self.errors,
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
            }

    def process_word(self, idx, row):
        """处理单个单词"""
        word = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else None
        if not word:
            print(f"[DEBUG] 跳过空单词，行索引: {idx}")
            return None

        print(f"\n{'=' * 60}")
        print(f"[Task {self.task_id}] 处理单词 {idx + 1}/{self.total_count}: '{word}'")
        print(f"{'=' * 60}")

        result = {"word": word, "status": "success", "files": []}

        try:
            # 生成英音音频 (Amanda)
            print(f"[DEBUG] 单词 '{word}' -> 生成英音 (Amanda)...")
            uk_path = f"vocabulary/{word}/core/audio/{word}1.wav"
            uk_data = text_to_speech(word, VOICE_AMANDA)
            if uk_data:
                uk_file = os.path.join(self.output_dir, uk_path)
                os.makedirs(os.path.dirname(uk_file), exist_ok=True)
                with open(uk_file, "wb") as f:
                    f.write(uk_data)
                result["files"].append(uk_path)
                print(f"[DEBUG] ✓ 英音生成成功: {uk_file} ({len(uk_data)} bytes)")
            else:
                print(f"[DEBUG] ✗ 英音生成失败: {word}")

            # 生成美音音频 (Gavin)
            print(f"[DEBUG] 单词 '{word}' -> 生成美音 (Gavin)...")
            us_path = f"vocabulary/{word}/core/audio/{word}2.wav"
            us_data = text_to_speech(word, VOICE_GAVIN)
            if us_data:
                us_file = os.path.join(self.output_dir, us_path)
                os.makedirs(os.path.dirname(us_file), exist_ok=True)
                with open(us_file, "wb") as f:
                    f.write(us_data)
                result["files"].append(us_path)
                print(f"[DEBUG] ✓ 美音生成成功: {us_file} ({len(us_data)} bytes)")
            else:
                print(f"[DEBUG] ✗ 美音生成失败: {word}")

            # 处理该单词的所有例句
            print(f"[DEBUG] 查找单词 '{word}' 的例句...")
            word_examples = self.examples_df[
                self.examples_df.iloc[:, 1].astype(str).str.strip() == word
            ]
            print(f"[DEBUG] 找到 {len(word_examples)} 条例句")

            for ex_idx, ex_row in word_examples.iterrows():
                example_id = str(ex_row.iloc[0]) if pd.notna(ex_row.iloc[0]) else None
                sentence = (
                    str(ex_row.iloc[2]).strip() if pd.notna(ex_row.iloc[2]) else None
                )

                if example_id and sentence:
                    print(
                        f"[DEBUG] 例句 #{example_id}: '{sentence[:50]}...' -> 生成音频 (Catherine)..."
                    )
                    ex_path = (
                        f"vocabulary/{word}/definition/examples/audio/{example_id}.wav"
                    )
                    ex_data = text_to_speech(sentence, VOICE_CATHERINE)
                    if ex_data:
                        ex_file = os.path.join(self.output_dir, ex_path)
                        os.makedirs(os.path.dirname(ex_file), exist_ok=True)
                        with open(ex_file, "wb") as f:
                            f.write(ex_data)
                        result["files"].append(ex_path)
                        print(
                            f"[DEBUG] ✓ 例句音频生成成功: {ex_file} ({len(ex_data)} bytes)"
                        )
                    else:
                        print(f"[DEBUG] ✗ 例句音频生成失败: #{example_id}")

            # 汇总输出
            print(f"[DEBUG] 单词 '{word}' 处理完成，生成文件数: {len(result['files'])}")
            for f in result["files"]:
                print(f"  - {f}")

        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)
            print(f"[Task {self.task_id}] 错误: {word} - {e}")
            import traceback

            print(f"[DEBUG] 错误详情:\n{traceback.format_exc()}")

        return result

    def process_batch(self):
        """处理一批数据"""
        with self._lock:
            if self.status == "pending":
                self.status = "running"
                self.start_time = datetime.now()

            if self.status != "running":
                return

        # 计算本批次的范围（一次处理一个单词）
        start_idx = self.current_index
        end_idx = min(start_idx + 1, self.total_count)

        print(
            f"[Task {self.task_id}] 处理批次 {start_idx + 1} - {end_idx} / {self.total_count}"
        )

        # 处理本批次的单词
        for idx in range(start_idx, end_idx):
            with self._lock:
                if self.status != "running":
                    break
                self.current_index = idx

            row = self.vocab_df.iloc[idx]
            result = self.process_word(idx, row)

            if result:
                with self._lock:
                    if result["status"] == "success":
                        self.processed_words.append(result["word"])
                    else:
                        self.errors.append(
                            {"word": result["word"], "error": result.get("error")}
                        )

        # 检查是否完成
        with self._lock:
            if self.current_index >= self.total_count - 1:
                self.status = "completed"
                self.end_time = datetime.now()
                self._create_final_zip()
            elif self.status == "running":
                self.current_index = end_idx

    def _create_final_zip(self):
        """创建最终压缩包"""
        zip_path = os.path.join(self.output_dir, "vocabulary_audio.zip")
        print(f"[Task {self.task_id}] 创建压缩包: {zip_path}")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.output_dir):
                for file in files:
                    if file == "vocabulary_audio.zip":
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.output_dir)
                    zipf.write(file_path, arcname)

        print(f"[Task {self.task_id}] 压缩包创建完成")

    def create_partial_zip(self):
        """创建部分压缩包（用于分批下载）"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = os.path.join(
            self.output_dir, f"vocabulary_audio_partial_{timestamp}.zip"
        )

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.output_dir):
                for file in files:
                    if file.endswith(".zip"):
                        continue
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, self.output_dir)
                    zipf.write(file_path, arcname)

        return zip_path


def create_task(vocab_file, examples_file, output_dir, limit=None):
    """创建新任务"""
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{id(vocab_file)}"

    processor = BatchProcessor(task_id, vocab_file, examples_file, output_dir, limit)
    batch_tasks[task_id] = processor

    return task_id


def get_task_status(task_id):
    """获取任务状态"""
    if task_id not in batch_tasks:
        return None
    return batch_tasks[task_id].get_status()


def start_task(task_id):
    """启动任务"""
    if task_id not in batch_tasks:
        return False

    processor = batch_tasks[task_id]

    # 先设置状态为 running
    with processor._lock:
        if processor.status == "pending":
            processor.status = "running"
            processor.start_time = datetime.now()

    def run_batch():
        while True:
            with processor._lock:
                if processor.status != "running":
                    break

            processor.process_batch()

            with processor._lock:
                if processor.status == "completed":
                    break

            # 短暂休息，避免 CPU 占用过高
            import time

            time.sleep(0.5)

    # 启动后台线程
    thread = threading.Thread(target=run_batch)
    thread.daemon = True
    thread.start()

    return True


def process_next_batch(task_id):
    """处理下一批（手动模式）"""
    if task_id not in batch_tasks:
        return None

    processor = batch_tasks[task_id]
    processor.process_batch()

    return processor.get_status()


def pause_task(task_id):
    """暂停任务"""
    if task_id not in batch_tasks:
        return False

    with batch_tasks[task_id]._lock:
        if batch_tasks[task_id].status == "running":
            batch_tasks[task_id].status = "paused"

    return True


def resume_task(task_id):
    """恢复任务"""
    if task_id not in batch_tasks:
        return False

    processor = batch_tasks[task_id]

    with processor._lock:
        if processor.status == "paused":
            processor.status = "running"

    # 重新启动处理线程
    start_task(task_id)
    return True


def get_partial_zip(task_id):
    """获取部分压缩包路径"""
    if task_id not in batch_tasks:
        return None

    processor = batch_tasks[task_id]
    return processor.create_partial_zip()


def get_final_zip(task_id):
    """获取最终压缩包路径"""
    if task_id not in batch_tasks:
        return None

    processor = batch_tasks[task_id]
    zip_path = os.path.join(processor.output_dir, "vocabulary_audio.zip")

    if os.path.exists(zip_path):
        return zip_path
    return None
