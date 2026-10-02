"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
登记或流转过的模块会落盘到 backend/data/<module>.json，重启后按落盘内容恢复，
不会退回到种子数据的旧次序。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.seed import SEED_ROWS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {}

    def module_names(self) -> list[str]:
        return sorted(set(SEED_ROWS) | set(self._tables))

    def rows(self, module: str) -> list[dict[str, Any]]:
        if module not in self._tables:
            saved = self._read_saved(module)
            if saved is not None:
                self._tables[module] = saved
            else:
                self._tables[module] = [dict(row) for row in SEED_ROWS.get(module, [])]
        return self._tables[module]

    def save(self, module: str) -> None:
        """把某个模块的当前数据落盘；下次启动优先读这份，不回退到种子。"""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        path = DATA_DIR / f"{module}.json"
        path.write_text(
            json.dumps(self.rows(module), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_saved(self, module: str) -> list[dict[str, Any]] | None:
        path = DATA_DIR / f"{module}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return data if isinstance(data, list) else None

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
