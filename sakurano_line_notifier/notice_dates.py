"""Keep publication, event and application dates separate; never guess publication."""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from html.parser import HTMLParser


def calendar_date(value: str) -> str:
    value = unicodedata.normalize("NFKC", value)
    match = re.search(r"(?<!\d)(20\d{2})\s*[年/.-]\s*(\d{1,2})\s*[月/.-]\s*(\d{1,2})(?:\s*日)?", value)
    if not match:
        era = re.search(r"令和\s*(元|\d+)\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", value)
        if era:
            parts = (2018 + (1 if era[1] == "元" else int(era[1])), int(era[2]), int(era[3]))
        else:
            return ""
    else:
        parts = tuple(int(part) for part in match.groups())
    try:
        return date(*parts).strftime("%Y/%m/%d")
    except ValueError:
        return ""


def labelled_date(text: str, label: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    # A label owns only the immediately following date, not a later paragraph.
    for match in re.finditer(rf"(?:{label})\s*[:：]?\s*((?:20\d{{2}}|令和)[^\n]{{4,32}})", normalized):
        value = calendar_date(match[1])
        if value:
            return value
    return ""


class _DateMetaParser(HTMLParser):
    # Attribute order is immaterial in HTMLParser, unlike an order-sensitive regex.
    # https://docs.python.org/3/library/html.parser.html#html.parser.HTMLParser.handle_starttag
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        key = (attributes.get("name") or attributes.get("property") or attributes.get("itemprop") or "").lower()
        if tag == "meta" and key in {"modified_date", "datemodified", "datepublished", "article:published_time", "article:modified_time"}:
            self.values.append(attributes.get("content") or "")


def publication_date(html: str, text: str) -> str:
    parser = _DateMetaParser()
    parser.feed(html)
    for value in parser.values:
        parsed = calendar_date(value)
        if parsed:
            return parsed
    return labelled_date(text, r"更新日") or labelled_date(text, r"公開日|掲載日|発行日|投稿日|配信日")


def activity_dates(text: str) -> tuple[str, str]:
    event = labelled_date(text, r"開催日(?:時)?|実施日(?:時)?|期日|(?<![一-龯ぁ-んァ-ヶ])日時")
    normalized = unicodedata.normalize("NFKC", text)
    # A recurring list is not one event on its first (possibly past) date.
    # Leave it undated and preserve the original schedule instead of archiving
    # future sessions or exporting an arbitrary first session to a calendar.
    if re.search(r"(?:開催日(?:時)?|実施日(?:時)?)\s*[:：]?\s*(?:20\d{2}年|令和\s*\d+年)\s*\d{1,2}月\s*\d{1,2}日[^\n、,]{0,20}\s*[、,]\s*(?:(?:20\d{2}|令和\d+)年)?\s*\d{1,2}月\s*\d{1,2}日", normalized):
        event = ""
    return (
        event,
        labelled_date(text, r"申込み締め切り日|申込締切日|申込締切|申込締め切り|申込期限|応募締切|提出期限"),
    )
