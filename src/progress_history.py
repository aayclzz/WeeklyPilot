"""
Progress History — 学习进度历史记录与对比引擎

职责：
1. 将每次抓取的进度快照保存到 data/progress_history.json
2. 对比当前快照与历史快照，识别「本周新增完成」项
3. 提供进度趋势分析（可选，预留）
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

from src.logger import logger

# 历史数据文件路径
HISTORY_FILE = Path(__file__).parent.parent / "data" / "progress_history.json"


class ProgressHistory:
    """进度历史管理器"""

    def __init__(self, history_file: Optional[Path] = None):
        self.history_file = history_file or HISTORY_FILE
        self._ensure_file()

    # ----------------------------------------------------------
    # 公共方法
    # ----------------------------------------------------------

    def save_snapshot(self, progress_data: Dict[str, dict]) -> bool:
        """保存当前进度快照到历史记录

        Args:
            progress_data: {course_id: {completed_count, total_count, items, ...}}

        Returns:
            是否成功保存
        """
        try:
            history = self.load_all()
            today = date.today().isoformat()

            # 构建快照
            snapshot = {
                "date": today,
                "timestamp": datetime.now().isoformat(),
                "courses": {},
            }

            for cid, prog in progress_data.items():
                if "error" in prog:
                    continue
                # 记录已完成项的 ID 列表（用于后续对比）
                completed_ids = [
                    str(item.get("lab_id", item.get("id", item.get("name", ""))))
                    for item in prog.get("items", [])
                    if item.get("completed")
                ]
                snapshot["courses"][cid] = {
                    "completed_count": prog.get("completed_count", 0),
                    "total_count": prog.get("total_count", 0),
                    "completed_ids": completed_ids,
                    "course_name": prog.get("course_name", ""),
                }

            # 合并到历史（按日期去重：同一天只保留最后一次）
            # 移除同一天的旧记录
            history = [h for h in history if h.get("date") != today]
            history.append(snapshot)

            # 只保留最近 30 条
            if len(history) > 30:
                history = history[-30:]

            self._write_all(history)
            num_courses = len(snapshot.get("courses", {}))
            logger.info(f"进度快照已保存：{today} ({num_courses} 门课程)")
            return True

        except Exception as e:
            logger.warning(f"保存进度快照失败：{e}")
            return False

    def get_newly_completed(self, current_data: Dict[str, dict]) -> Dict[str, List[dict]]:
        """对比当前进度与上一次快照，返回「新增完成」的项

        Args:
            current_data: {course_id: {items: [{id, name, completed, type}], ...}}

        Returns:
            {course_id: [{id, name, type}, ...]}   — 每个课程新增完成的项目列表
        """
        history = self.load_all()
        if len(history) < 2:
            # 不足 2 条记录，无法对比 → 全部视为新增
            return self._all_as_new(current_data)

        # 取上一次快照（最近一次不等于今天的）
        today = date.today().isoformat()
        last_snapshot = None
        for h in reversed(history):
            if h.get("date") != today:
                last_snapshot = h
                break

        if last_snapshot is None:
            return self._all_as_new(current_data)

        # 对比
        newly_completed: Dict[str, List[dict]] = {}
        for cid, prog in current_data.items():
            if "error" in prog:
                continue
            course_new = []
            # 历史已完成 ID 集合
            historical_ids = set()
            if cid in last_snapshot.get("courses", {}):
                historical_ids = set(last_snapshot["courses"][cid].get("completed_ids", []))

            for item in prog.get("items", []):
                if item.get("completed"):
                    item_id = str(item.get("lab_id", item.get("id", item.get("name", ""))))
                    if item_id not in historical_ids:
                        course_new.append({
                            "id": item_id,
                            "name": item.get("name", ""),
                            "type": item.get("type", ""),
                        })

            if course_new:
                newly_completed[cid] = course_new

        return newly_completed

    def show_summary(self):
        """打印历史记录摘要"""
        history = self.load_all()
        if not history:
            print("\n📊 暂无历史进度记录")
            return

        print(f"\n📊 进度历史记录（共 {len(history)} 条）")
        print("-" * 60)
        for h in history[-10:]:  # 最近 10 条
            date_str = h.get("date", "?")
            courses_summary = []
            for cid, cinfo in h.get("courses", {}).items():
                done = cinfo.get("completed_count", 0)
                total = cinfo.get("total_count", 0)
                name = cinfo.get("course_name", cid)
                courses_summary.append(f"{name}={done}/{total}")
            print(f"  {date_str}: {', '.join(courses_summary)}")

    # ----------------------------------------------------------
    # 内部方法
    # ----------------------------------------------------------

    def _ensure_file(self):
        """确保历史数据文件存在"""
        if not self.history_file.exists():
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            self._write_all([])

    def load_all(self) -> List[dict]:
        """加载全部历史记录"""
        try:
            if self.history_file.exists() and self.history_file.stat().st_size > 0:
                with open(self.history_file, encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"读取历史文件失败，将重置：{e}")
        return []

    def _write_all(self, history: List[dict]):
        """写入全部历史记录"""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)

    def _all_as_new(self, current_data: Dict[str, dict]) -> Dict[str, List[dict]]:
        """没有历史对比时，将所有已完成项视为新增"""
        result = {}
        for cid, prog in current_data.items():
            if "error" in prog:
                continue
            items = [
                {
                    "id": str(item.get("lab_id", item.get("id", item.get("name", "")))),
                    "name": item.get("name", ""),
                    "type": item.get("type", ""),
                }
                for item in prog.get("items", [])
                if item.get("completed")
            ]
            if items:
                result[cid] = items
        return result
