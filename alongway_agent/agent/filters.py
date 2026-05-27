from __future__ import annotations

import re
from datetime import datetime, time
from typing import Optional

from agent.models import Deal


def is_within_budget(deal: Optional[Deal], budget: Optional[float]) -> bool:
    if deal is None or budget is None:
        return True
    return deal.price <= budget


def assess_availability(
    deal: Optional[Deal],
    departure_time: Optional[datetime],
) -> tuple[bool, list[str], list[str]]:
    if deal is None:
        return True, [], []
    if departure_time is None:
        return True, ["营业时间未知"], ["部分商家缺少营业时间信息"]

    reasons: list[str] = []
    warnings: list[str] = []
    known = False
    available = True

    if deal.business_time:
        known = True
        if not _time_range_contains(deal.business_time, departure_time.time()):
            available = False
            reasons.append("当前不在商家营业时间内")
    else:
        warnings.append("部分商家缺少营业时间信息")

    if deal.valid_time:
        known = True
        if not _time_range_contains(deal.valid_time, departure_time.time()):
            available = False
            reasons.append("当前不在团购可用时间内")

    if not known:
        reasons.append("营业时间未知")
        warnings.append("部分商家缺少营业时间信息")

    return available, reasons, warnings


def _time_range_contains(time_range: str, current: time) -> bool:
    parsed = _parse_time_range(time_range)
    if parsed is None:
        return True
    start, end = parsed
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def _parse_time_range(time_range: str) -> Optional[tuple[time, time]]:
    match = re.match(
        r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$",
        time_range,
    )
    if not match:
        return None
    start_hour, start_minute, end_hour, end_minute = map(int, match.groups())
    if start_hour > 23 or end_hour > 23 or start_minute > 59 or end_minute > 59:
        return None
    return time(start_hour, start_minute), time(end_hour, end_minute)
