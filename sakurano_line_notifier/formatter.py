from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from urllib.parse import urlparse

from .extractor import clean_text_lines


@dataclass(frozen=True)
class MessageDocument:
    title: str
    kind: str
    url: str
    reason: str
    text: str


KIND_LABELS = {
    "grade_news": "学年だより",
    "school_news": "学校だより",
    "after_school": "学童クラブ",
    "city_info": "市・教育委員会",
    "document": "関連資料",
}


def _is_subject_line(line: str) -> bool:
    return bool(re.match(r"^(国語|算数|生活|音楽|図工|体育|道徳|社会|理科|家庭科|外国語|総合|安全指導|DC)(?:\s|$)", line))


def categorize_text(text: str, kind: str) -> OrderedDict[str, list[str]]:
    sections: OrderedDict[str, list[str]] = OrderedDict()
    default_category = "保護者への連絡" if kind == "grade_news" else "学校全体への連絡"
    current_category = default_category
    for line in clean_text_lines(text):
        if len(line) <= 40 and "学年だより" in line:
            continue
        if "学年からの連絡" in line:
            current_category = "保護者への連絡"
            remainder = line.replace("学年からの連絡", "", 1).strip()
            if remainder and remainder != "学習予定":
                sections.setdefault(current_category, []).append(remainder)
            continue
        if line == "学習予定" or line.startswith("学習予定 "):
            current_category = "学習予定"
            remainder = line[len("学習予定") :].strip()
            if remainder:
                sections.setdefault(current_category, []).append(remainder)
            continue
        if _is_subject_line(line):
            current_category = "学習予定"

        if re.search(r"持ち物|持ちもの|準備|用意|持たせ|持ってき|道具|材料", line):
            category = "持ち物・準備"
        elif re.search(r"提出|締切|〆切|期限|までに", line):
            category = "提出物・締切"
        elif re.search(r"行事|予定|日程|始業式|終業式|下校|授業|給食|運動会|音楽会", line):
            category = "行事・予定"
        elif re.search(r"保護者|ご家庭|お願い|連絡|お知らせ|ご確認", line):
            category = "保護者への連絡"
        else:
            category = current_category
        sections.setdefault(category, []).append(line)
    return sections


def _bullet(line: str) -> str:
    if line.startswith(("・", "〇", "◯", "○", "※", "-", "—")):
        return line
    return f"・{line}"


def _reason_label(reason: str) -> str:
    return {
        "new_link": "新しいリンク",
        "content_changed": "PDF内容変更",
        "title_changed": "リンク情報変更",
        "existing_baseline": "初回登録",
    }.get(reason, reason)


def _document_sort_key(document: MessageDocument) -> tuple[int, str, str]:
    # The current school site uses a timestamp in PDF filenames. Showing the
    # newest document first makes a first-run preview useful without requiring
    # any site-specific date parser. Unknown URL formats retain a stable order.
    filename = urlparse(document.url).path.rsplit("/", 1)[-1]
    match = re.search(r"(?<!\d)(\d{12,14})(?!\d)", filename)
    timestamp = int(match.group(1)) if match else 0
    return (-timestamp, document.title, document.url)


def format_document(document: MessageDocument) -> str:
    lines = [f"■ {KIND_LABELS.get(document.kind, '関連資料')}：{document.title}", f"検知：{_reason_label(document.reason)}"]
    for category, items in categorize_text(document.text, document.kind).items():
        if not items:
            continue
        lines.append(f"【{category}】")
        lines.extend(_bullet(item) for item in items)
    return "\n".join(lines)


def format_notification(grade: str, documents: list[MessageDocument], max_chars: int = 4_800) -> str:
    if not documents:
        raise ValueError("at least one document is required")
    if max_chars < 100:
        raise ValueError("max_chars is too small for a useful notification")

    header = f"【桜野小学校・{grade} 新着情報】"
    ordered_documents = sorted(documents, key=_document_sort_key)
    body = "\n\n".join(format_document(document) for document in ordered_documents)
    footer = "\n\n原文リンク：\n" + "\n".join(f"・{document.url}" for document in ordered_documents)
    complete = f"{header}\n\n{body}{footer}"
    if len(complete) <= max_chars:
        return complete

    marker = "\n…（長文のため一部省略）"
    body_budget = max_chars - len(header) - len(footer) - 4 - len(marker)
    if body_budget < 0:
        return (header + footer)[:max_chars]
    trimmed_body = body[:body_budget].rstrip()
    return f"{header}\n\n{trimmed_body}{marker}{footer}"[:max_chars]
