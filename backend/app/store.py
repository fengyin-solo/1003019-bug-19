"""数据仓库：给每个业务模块准备一份可筛选、可流转的数据，改动会落盘保存。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
首次启动用示例数据初始化并写入本地 JSON，之后登记与流转都落在同一份文件上，
退出再进来读到的还是离开时的次序与状态，不会跳回初始样例。
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from app.seed import SEED_ROWS

DATA_FILE = Path(
    os.environ.get("APP_STORE_FILE")
    or Path(__file__).resolve().parent.parent / "data" / "store.json"
)


class Store:
    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self._data_file = data_file
        self._lock = threading.Lock()
        tables = self._read_disk()
        if tables is None:
            tables = {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}
            self._tables = tables
            self.save()
        else:
            self._tables = tables

    def _read_disk(self) -> dict[str, list[dict[str, Any]]] | None:
        try:
            raw = json.loads(self._data_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        return {
            str(name): [dict(row) for row in rows]
            for name, rows in raw.items()
            if isinstance(rows, list)
        }

    def save(self) -> None:
        """把当前所有模块整体落盘；先写临时文件再替换，避免留下半截文件。"""
        with self._lock:
            self._data_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self._data_file.with_suffix(".tmp")
            tmp_file.write_text(
                json.dumps(self._tables, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp_file.replace(self._data_file)

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
