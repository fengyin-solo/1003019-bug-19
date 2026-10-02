"""空调管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "ac"

# 登记时一并落盘的字段全集：列表和详情都读这同一份
ENTRY_FIELDS = ["空调编号", "空调类型", "制冷量", "所属站点", "运行电流", "设定温度", "回风温度"]
# 缺任何一项都不予登记；回风温度是判断制冷状态的依据，必须在列
REQUIRED_FIELDS = ["空调编号", "空调类型", "制冷量", "回风温度"]
# 执行动作时允许随单更新的测量值，和登记内容一起落盘
MEASURE_FIELDS = ["制冷量", "运行电流", "设定温度", "回风温度"]

STATUS_ORDER = ["正常", "制冷不足", "压缩机故障", "已更换"]
ACTION_RULES = {"登记不足": "制冷不足", "登记故障": "压缩机故障", "安排更换": "已更换"}
# 每一档只认一个下一步动作：正常→制冷不足→压缩机故障→已更换，跳档直接打回
NEXT_ACTION = {"正常": "登记不足", "制冷不足": "登记故障", "压缩机故障": "安排更换"}
ABNORMAL_STATUSES = {"制冷不足", "压缩机故障"}


class AcService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        # 按 id 稳定排序：退出再进来，列表次序不跳回旧样子
        rows = sorted(store.rows(MODULE), key=lambda row: int(row.get("id", 0)))
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("空调编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ENTRY_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip():
                entry[field] = value
        entry["status"] = STATUS_ORDER[0]
        entry["空调状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        store.save(MODULE)
        return entry, []

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"空调 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于空调管理可执行范围"
        current = str(entry.get("status") or STATUS_ORDER[0])
        if current == STATUS_ORDER[-1]:
            return None, f"空调已更换完毕，流程收口，不能再{action}"
        expected = NEXT_ACTION.get(current)
        if expected is None:
            return None, f"空调当前状态「{current}」不在允许的状态序列里"
        if action != expected:
            return None, f"空调当前在「{current}」一档，下一步只能{expected}，不能{action}"
        # 测量值随登记内容一起落盘，列表和详情读同一份
        for field in MEASURE_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip():
                entry[field] = value
        target = ACTION_RULES[action]
        entry["status"] = target
        entry["空调状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = target in ABNORMAL_STATUSES
        store.save(MODULE)
        return entry, f"空调已{action}"
