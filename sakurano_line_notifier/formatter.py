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
    "gakudo_admissions": "入会・制度案内",
    "gakudo_facility": "学童の施設案内",
    "gakudo_daily": "学童の生活連絡",
    "asobee_reference": "あそべえの利用案内",
    "asobee_letter": "あそべえだより",
    "city_info": "市・教育委員会",
    "document": "関連資料",
}


_SUBJECT_PATTERN = re.compile(
    r"^(?:" + "|".join(
        r"\s*".join(subject)
        for subject in ("国語", "算数", "生活", "音楽", "図工", "体育", "道徳", "社会", "理科", "家庭科", "外国語", "総合", "安全指導", "DC")
    ) + r")(?:\s|$)"
)


def _is_subject_line(line: str) -> bool:
    return bool(_SUBJECT_PATTERN.match(line))


def categorize_text(text: str, kind: str) -> OrderedDict[str, list[str]]:
    sections: OrderedDict[str, list[str]] = OrderedDict()
    school_news = kind in {"grade_news", "school_news"}
    default_category = "保護者への連絡" if kind == "grade_news" else "学校全体への連絡"
    if not school_news:
        default_category = KIND_LABELS.get(kind, "関連資料")
    current_category = default_category
    block: list[str] = []

    def append_block() -> None:
        if not block:
            return
        # Classify the whole notice, including words wrapped across PDF lines.
        # Keep the original cleaned lines in the value; never paraphrase them.
        content = "".join(block)
        # Non-school text may describe provider supplies or general procedures;
        # keyword hits alone cannot establish a parent-facing action category.
        if not school_news or current_category == "学習予定":
            category = current_category
        elif re.search(r"持ち物|持ちもの|準備|用意|持たせ|持ってき|道具|材料", content):
            category = "持ち物・準備"
        elif re.search(r"提出|締切|〆切|期限|までに", content):
            category = "提出物・締切"
        elif re.search(r"行事|予定|日程|始業式|終業式|下校|授業|給食|運動会|音楽会", content):
            category = "行事・予定"
        elif re.search(r"保護者|ご家庭|お願い|連絡|お知らせ|ご確認", content):
            category = "保護者への連絡"
        else:
            category = current_category
        sections.setdefault(category, []).append("\n".join(block))
        block.clear()

    for line in clean_text_lines(text):
        compact = line.replace(" ", "")
        parent_heading = school_news and compact.startswith("学年からの連絡")
        study_heading = school_news and bool(re.match(r"^学\s*習\s*予\s*定(?:\s|$)", line))
        title = school_news and bool(re.fullmatch(r"学年だより(?:\([^)]*\))?", compact))
        subject = school_news and _is_subject_line(line)
        notice_heading = line.startswith(("〇", "◯", "○"))
        # Leading prose can qualify every item of a following list. Keep the
        # preamble and all its bullets together until an explicit section break;
        # a circle alone cannot establish that the condition no longer applies.
        list_continuation = (
            notice_heading and block and current_category != "学習予定"
            and not block[0].startswith(("〇", "◯", "○"))
        )
        if parent_heading or study_heading or title or subject or (notice_heading and not list_continuation):
            append_block()
            if parent_heading:
                current_category = "保護者への連絡"
            elif study_heading or subject:
                current_category = "学習予定"
            elif title or current_category == "学習予定":
                current_category = default_category
        block.append(line)
        if title or (parent_heading and compact in {"学年からの連絡", "学年からの連絡学習予定"}) or (study_heading and compact == "学習予定"):
            # Column headings and mastheads are not instructions. Preserve
            # them separately, including combined parent/study column labels.
            sections.setdefault(current_category, []).append("\n".join(block))
            block.clear()
        # Only explicit notice/subject headings establish a new block. Sentence
        # endings, lists, parentheses, ※ and ★ may introduce conditions on the
        # preceding request, so uncertain runs remain together.
    append_block()
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


def _document_blocks(document: MessageDocument) -> list[str]:
    blocks = [f"■ {KIND_LABELS.get(document.kind, '関連資料')}：{document.title}\n検知：{_reason_label(document.reason)}"]
    for category, items in categorize_text(document.text, document.kind).items():
        if not items:
            continue
        blocks.append(f"【{category}】\n{_bullet(items[0])}")
        blocks.extend(_bullet(item) for item in items[1:])
    return blocks


def format_document(document: MessageDocument) -> str:
    return "\n".join(_document_blocks(document))


def format_notification(grade: str, documents: list[MessageDocument], max_chars: int = 4_800) -> str:
    if not documents:
        raise ValueError("at least one document is required")
    if max_chars < 100:
        raise ValueError("max_chars is too small for a useful notification")

    header = f"【桜野小学校・{grade} 新着情報】"
    ordered_documents = sorted(documents, key=_document_sort_key)
    body_blocks: list[str] = []
    for document in ordered_documents:
        blocks = _document_blocks(document)
        if body_blocks:
            blocks[0] = "\n" + blocks[0]
        body_blocks.extend(blocks)
    body = "\n".join(body_blocks)
    footer = "\n\n原文リンク：\n" + "\n".join(f"・{document.url}" for document in ordered_documents)
    complete = f"{header}\n\n{body}{footer}"
    if len(complete) <= max_chars:
        return complete

    marker = "\n…（長文のため一部省略）"
    body_budget = max_chars - len(header) - len(footer) - 4 - len(marker)
    if body_budget < 0:
        return (header + footer)[:max_chars]
    kept_blocks: list[str] = []
    for block in body_blocks:
        cost = len(block) + bool(kept_blocks)
        if cost > body_budget:
            break
        kept_blocks.append(block)
        body_budget -= cost
    trimmed_body = "\n".join(kept_blocks)
    return f"{header}\n\n{trimmed_body}{marker}{footer}"[:max_chars]
