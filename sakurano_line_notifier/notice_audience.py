"""Conservative audience checks from explicit Japanese notice titles.

These are display/delivery filters, never collection filters. Body navigation,
related links and an upstream source's default `全学年` are not target evidence.
Unknown audiences remain visible; the rules do not claim universal inference.
"""
from __future__ import annotations

import re
import unicodedata

from .extractor import normalize_grade


def matches_audience(title: str, level: str | None, grade: str | None) -> bool:
    if level not in {"小学校", "中学校", "高等学校"}:
        return True
    value = unicodedata.normalize("NFKC", title)
    value = re.sub(r"\s+", "", value)
    normalized_grade = normalize_grade(grade) if grade else "全学年"
    elementary = bool(re.search(r"小学|小[・･]?中学", value))
    middle = bool(re.search(r"中学", value))
    high = bool(re.search(r"高校|高等学校", value))
    admission = bool(re.search(r"入学|進学|新1年生", value))
    # Explicit pre-entry procedures are for incoming pupils, not the current
    # first grade. Keep school-issued entrance-ceremony/term notices intact.
    if level == "小学校" and normalized_grade != "全学年":
        if re.search(r"[【〖]小学校・入学[】〗]|新小学1年生.*入学準備金", value):
            return False
        if re.search(r"[【〖]小[・･]?中学校・入学[】〗]", value):
            return normalized_grade == "6年生"
    # Admission to middle school is relevant to elementary sixth-graders,
    # not to a first-grader just because both grades are called `1年生`.
    if middle and not elementary and not high and level == "小学校":
        return admission and normalized_grade in {"6年生", "全学年"}
    if high and not middle and not elementary and level != "高等学校":
        return level == "中学校" and admission and normalized_grade in {"3年生", "全学年"}
    if elementary and not middle and not high and level != "小学校":
        return False
    if middle and not elementary and not high and level == "高等学校":
        return False
    if normalized_grade == "全学年":
        return True
    if sum((elementary, middle, high)) > 1:
        return True  # cross-school ranges require richer explicit metadata
    # Only an explicit grade attached to a school type is evidence. Avoid
    # confusing a fiscal year, school number or an incoming middle grade.
    prefix = {"小学校": r"小学(?:校)?", "中学校": r"中学(?:校)?", "高等学校": r"高校|高等学校"}[level]
    match = re.search(rf"(?:{prefix})([1-6])(?:([〜～~\-・、,])([1-6]))?年生", value)
    if match and not admission:
        start, separator, end = match.groups()
        allowed = {int(start)}
        if end:
            if separator in "〜～~-":
                if int(start) > int(end):
                    return True  # malformed range: do not invent an audience
                allowed.update(range(int(start), int(end) + 1))
            else:
                allowed.add(int(end))
        return normalized_grade in {f"{number}年生" for number in allowed}
    return True
