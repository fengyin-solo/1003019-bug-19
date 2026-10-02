"""空调管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "ac"
# 必填项缺一样就打回并点名；回风温度是判断正常运行的依据，空着不能记成正常。
REQUIRED_FIELDS = ["空调编号", "空调类型", "制冷量", "回风温度"]
# 登记内容整体落盘，列表和详情读同一份，不再只留必填项。
ENTRY_FIELDS = ["空调编号", "空调类型", "制冷量", "所属站点", "运行电流", "设定温度", "回风温度"]
STATUS_ORDER = ["正常", "制冷不足", "压缩机故障", "已更换"]
ACTION_RULES = {"登记不足": "制冷不足", "登记故障": "压缩机故障", "安排更换": "已更换"}
ABNORMAL_STATUSES = {"制冷不足", "压缩机故障"}


def _next_action(status: str) -> str | None:
    """当前档位唯一允许的动作；已到「已更换」就没有下一步。"""
    if status not in STATUS_ORDER or status == STATUS_ORDER[-1]:
        return None
    target = STATUS_ORDER[STATUS_ORDER.index(status) + 1]
    for action, action_target in ACTION_RULES.items():
        if action_target == target:
            return action
    return None


class AcService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
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
        entry.update({field: values.get(field) for field in ENTRY_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["空调状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        store.save()
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"空调 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于空调管理可执行范围"
        current = str(entry.get("status") or "")
        if current not in STATUS_ORDER:
            return None, f"空调 {entry_id} 的状态「{current}」不在允许的状态序列里，请先修正台账"
        expected = _next_action(current)
        if expected is None:
            return None, f"空调当前卡在「{STATUS_ORDER[-1]}」，流转已结束，不能再{action}"
        if action != expected:
            return None, (
                f"空调当前卡在「{current}」一档，只能按「{' → '.join(STATUS_ORDER)}」依次流转，"
                f"下一步应执行「{expected}」，不能跳着{action}"
            )
        target = ACTION_RULES[action]
        entry["status"] = target
        entry["空调状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = target in ABNORMAL_STATUSES
        store.save()
        return entry, f"空调已{action}，当前状态「{target}」"
