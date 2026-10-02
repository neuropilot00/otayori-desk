from __future__ import annotations

import unittest
from collections import Counter

from sakurano_line_notifier.extractor import clean_text_lines
from sakurano_line_notifier.formatter import (
    KIND_LABELS,
    MessageDocument,
    categorize_text,
    format_document,
    format_notification,
)


# Exact cleaned first-grade text from the official October newsletter,
# 20260918181117.pdf, retrieved on 2026-10-02. Keep the PDF's word wraps.
OCTOBER_PARENT_BLOCKS = [
    """〇さつまいもほりについて
日時:10月23日(金) 予備日10月29日(木)
持ち物:リュックサック 水とう 軍手
汗拭きタオル 雨具
ビニールぶくろ(2まいがさね)
※さつまいもを入れて持ち帰ります。
連絡帳 連絡袋 筆箱 帽子
長ぐつ
(はきたい人だけ、学校で長ぐつにはきかえます。)
★もちものすべてに、名前を書きます。
(ビニールぶくろにもお願いします。)""",
    """〇連絡帳について
連絡帳の残りが少なくなってきましたら、同じような
ノートを各ご家庭でご用意ください。""",
    """〇運動会について
1年生は、短距離走は『40メートル走』、団体競
技は『玉入れ』、表現運動はカラーポンポンを使
用して行います。 表現運動で使用するカラーポン
ポンは私費会計から、一括購入いたしました。
表現運動で使う衣装は、ご家庭にある好きな色
(柄あり可)のTシャツをご用意ください。体育着の
上から着脱ができる大きさのもので、紐やフード・
フリルなどの装飾がついているものはご遠慮くださ
い。詳細は後日、改めてお知らせいたします。""",
    """〇生活科「いきものとなかよし」の学習について
学習で昆虫を飼う予定です。そのため必要に応じ
て、ご家庭にある虫を飼育できるような虫かごやプラ
スチックの容器がある場合はご用意をお願いします。
持ってくる日にち等は後日連絡いたします。""",
    """〇なわとびについて
なわとびを私費会計から、一括購入いたします。
運動会終了後に一度持ち帰ります。持ち帰りました
ら長さを調整していただき、持たせてください。""",
]
OCTOBER_STUDY_BLOCKS = [
    "国 語\nくじらぐも まちがいをなおそう\nしらせたいな、見せたいな かん字のはなし\nことばをたのしもう",
    "算 数 どちらがおおい たしざん かたちあそび",
    "生 活 いきものとなかよし あきとともだち",
    "音 楽\nけんばんハーモニカ\nうたのもりあがりをいしきしてうたう\n(音楽会に向けて)",
    "図 工 運動会をもりあげよう おめでとう桜野小学校\nすきまちゃん",
    "体 育 走の運動あそび 表現リズムあそび",
    "道 徳\n公正、公平 社会正義 善悪の判断、自律、\n自由と責任、よりよい学校生活、集団生活の\n充実 勤労、公共の精神",
    "安 全 指 導 交通安全",
    "D C フォームでアンケートにこたえる",
]
OCTOBER_TEXT = "\n".join([
    "学 年 か ら の 連 絡 学 習 予 定",
    *OCTOBER_PARENT_BLOCKS,
    *OCTOBER_STUDY_BLOCKS,
    "学年だより(10月号)",
])


def document(text=OCTOBER_TEXT, kind="grade_news", url="https://example.test/20260918181117.pdf"):
    return MessageDocument("1年生 学年だより・10月号", kind, url, "new_link", text)


class FormatterBlockTests(unittest.TestCase):
    def test_actual_optional_boots_and_all_preparation_conditions_stay_in_complete_blocks(self):
        categories = categorize_text(OCTOBER_TEXT, "grade_news")
        self.assertEqual(categories["持ち物・準備"], OCTOBER_PARENT_BLOCKS)

    def test_actual_spaced_subjects_and_their_continuations_stay_in_study_schedule(self):
        categories = categorize_text(OCTOBER_TEXT, "grade_news")
        self.assertEqual(categories["学習予定"], OCTOBER_STUDY_BLOCKS)

    def test_every_cleaned_source_line_is_retained_once_and_blocks_keep_source_order(self):
        source_lines = clean_text_lines(OCTOBER_TEXT)
        categories = categorize_text(OCTOBER_TEXT, "grade_news")
        actual_lines = [line for items in categories.values() for block in items for line in block.splitlines()]
        self.assertEqual(Counter(actual_lines), Counter(source_lines))
        for items in categories.values():
            positions = []
            for block in items:
                self.assertIn(block, OCTOBER_TEXT)
                positions.append(OCTOBER_TEXT.index(block))
            self.assertEqual(positions, sorted(positions))

    def test_sentence_end_and_notes_are_not_boundaries_for_conditions(self):
        blocks = [
            "〇持ち物\n水筒を持ってきてください。\n(参加する人だけです。)\n※詳細は後日連絡します。",
            "〇提出について\n申込書を提出してください。\n該当する方のみ、10月5日までにお願いします。",
        ]
        self.assertEqual(dict(categorize_text("\n".join(blocks), "grade_news")), {
            "持ち物・準備": [blocks[0]], "提出物・締切": [blocks[1]],
        })

    def test_unmarked_paragraph_is_kept_whole_without_guessing_sentence_boundaries(self):
        paragraph = "参加する人だけ、\n容器をご用意ください。\n持ってくる日は後日お知らせします。"
        self.assertEqual(dict(categorize_text(paragraph, "grade_news")), {"持ち物・準備": [paragraph]})

    def test_keyword_wrapped_midword_is_classified_with_its_condition(self):
        paragraph = "〇容器について\nご家庭にある場合だけ、ご用\n意ください。"
        self.assertEqual(dict(categorize_text(paragraph, "grade_news")), {"持ち物・準備": [paragraph]})

    def test_parent_heading_with_inline_request_keeps_following_condition(self):
        paragraph = "学年からの連絡 持ち物:長ぐつ\n(はきたい人だけです。)"
        self.assertEqual(dict(categorize_text(paragraph, "grade_news")), {"持ち物・準備": [paragraph]})

    def test_study_keywords_do_not_reclassify_subjects_and_next_notice_exits_study(self):
        text = "学習予定\n図工 材料の準備\n体育 運動会\n〇保護者へのお願い\nご確認ください。"
        self.assertEqual(dict(categorize_text(text, "grade_news")), {
            "学習予定": ["学習予定", "図工 材料の準備", "体育 運動会"],
            "保護者への連絡": ["〇保護者へのお願い\nご確認ください。"],
        })

    def test_study_heading_remainder_and_parent_heading_keep_original_text(self):
        text = "学習予定 国語 音読\n学年からの連絡\n〇持ち物 水筒\n希望者のみです。"
        self.assertEqual(dict(categorize_text(text, "grade_news")), {
            "学習予定": ["学習予定 国語 音読"],
            "保護者への連絡": ["学年からの連絡"],
            "持ち物・準備": ["〇持ち物 水筒\n希望者のみです。"],
        })

    def test_non_school_documents_do_not_inherit_school_subject_boundaries(self):
        text = "国語 教室\n参加する場合は\nご家庭で材料をご用意ください。"
        for kind in ("city_info", "document", "gakudo_admissions", "gakudo_facility", "asobee_reference"):
            with self.subTest(kind=kind):
                self.assertEqual(dict(categorize_text(text, kind)), {KIND_LABELS[kind]: [text]})

    def test_non_school_keywords_do_not_promote_reference_text_to_action_categories(self):
        # Excerpts from the municipal pages checked during the read-only review:
        # 1054987.html (admissions) and 1006778.html (Asobee reference).
        paragraphs = [
            "令和9年度学童クラブ入会申請について\n"
            "4月1日入会を希望の場合は「令和9年3月11日(木曜日)」までに不備のない書類の提出が必要です。\n"
            "(注意)通信端末や通信環境に不安のある方は、市役所児童青少年課窓口にタブレット端末をご用意しております。ご活用ください。",
            "地域子ども館あそべえ\n"
            "回答8 原則として無料ですが、実施されるプログラムによっては材料費やイベント事業の参加費用がかかることがあります。\n"
            "回答11 土曜日や長期休業中に朝から午後まで参加するときは、お弁当を持たせてください。スタッフや参加児童が一緒に教室で食事をします。おやつの持参は禁止です。",
        ]
        for kind, label in KIND_LABELS.items():
            if kind in {"grade_news", "school_news"}:
                continue
            for text in paragraphs:
                with self.subTest(kind=kind, text=text[:20]):
                    self.assertEqual(dict(categorize_text(text, kind)), {label: [text]})

    def test_unknown_non_school_kind_uses_neutral_document_label(self):
        text = "利用案内\n道具は施設に用意してあります。"
        self.assertEqual(dict(categorize_text(text, "other")), {"関連資料": [text]})

    def test_optional_preamble_and_every_following_list_item_form_one_block(self):
        for preamble in (
            "参加を希望する方だけが対象です。",
            "次の持ち物は、参加を希望する方のみ必要です。",
            "参加を希\n望する方だけが対象です。\n以下をご確認ください。",
        ):
            for marker in ("〇", "◯", "○"):
                text = f"{preamble}\n{marker}持ち物:長ぐつ\n(学校ではきかえます。)\n{marker}持ち物:軍手"
                for kind in KIND_LABELS:
                    expected_category = "持ち物・準備" if kind in {"grade_news", "school_news"} else KIND_LABELS[kind]
                    with self.subTest(kind=kind, marker=marker, preamble=preamble):
                        # Exact equality also guards against duplicated conditions
                        # in different categories or changing the source order.
                        self.assertEqual(dict(categorize_text(text, kind)), {expected_category: [text]})

    def test_school_preamble_stays_with_list_and_stops_at_study_boundary(self):
        block = "参加を希望する方だけが対象です。\n〇持ち物:長ぐつ\n〇持ち物:軍手"
        text = "学年からの連絡\n" + block + "\n学習予定\n国 語 音読\n〇提出 申込書"
        for kind in ("grade_news", "school_news"):
            with self.subTest(kind=kind):
                self.assertEqual(dict(categorize_text(text, kind)), {
                    "保護者への連絡": ["学年からの連絡"],
                    "持ち物・準備": [block],
                    "学習予定": ["学習予定", "国 語 音読"],
                    "提出物・締切": ["〇提出 申込書"],
                })

    def test_list_merging_does_not_attach_study_text_to_next_parent_notice(self):
        text = "国 語 音読\n〇持ち物 水筒\n〇提出 申込書"
        self.assertEqual(dict(categorize_text(text, "grade_news")), {
            "学習予定": ["国 語 音読"],
            "持ち物・準備": ["〇持ち物 水筒"],
            "提出物・締切": ["〇提出 申込書"],
        })

    def test_reference_labels_and_original_text_are_retained(self):
        text = "施設の利用案内\n対象は市内の児童です。\n希望する方のみ利用できます。"
        for kind in ("gakudo_admissions", "gakudo_facility", "gakudo_daily", "asobee_reference", "asobee_letter"):
            with self.subTest(kind=kind):
                self.assertEqual(dict(categorize_text(text, kind)), {KIND_LABELS[kind]: [text]})

    def test_catalog_detail_keeps_original_body_and_exposes_complete_blocks(self):
        from sakurano_line_notifier.web_catalog import CatalogNotice

        notice = CatalogNotice(
            id="october", source_id="sakurano", source_name="桜野小学校", ward="武蔵野市",
            level="小学校", grade="1年生", title="10月号", kind="grade_news",
            url=document().url, text=OCTOBER_TEXT, content_hash="a" * 64,
            date_label="2026/10月号", published_label="2026/09/18",
            source_group="school", feed_group="notices",
        )
        detail = notice.to_detail()
        self.assertEqual(detail["text"], OCTOBER_TEXT)
        self.assertEqual(detail["categories"]["持ち物・準備"], OCTOBER_PARENT_BLOCKS)
        self.assertEqual(detail["categories"]["学習予定"], OCTOBER_STUDY_BLOCKS)

    def test_empty_text_remains_empty(self):
        self.assertEqual(categorize_text("\n \t", "grade_news"), {})


class FormatterLineTests(unittest.TestCase):
    def test_line_budget_keeps_or_omits_preamble_and_entire_list_together(self):
        text = "参加を希望する方だけが対象です。\n〇持ち物:長ぐつ\n〇持ち物:軍手"
        for kind in ("grade_news", "school_news", "asobee_letter"):
            doc = document(text, kind)
            complete = format_notification("1年生", [doc])
            self.assertIn(text, complete)
            for limit in range(150, len(complete) + 1):
                with self.subTest(kind=kind, limit=limit):
                    message = format_notification("1年生", [doc], max_chars=limit)
                    self.assertLessEqual(len(message), limit)
                    if any(line in message for line in text.splitlines()):
                        self.assertIn(text, message)
                    self.assertIn(doc.url, message)

    def test_unbounded_line_message_contains_each_complete_parent_block(self):
        message = format_notification("1年生", [document()])
        for block in OCTOBER_PARENT_BLOCKS:
            self.assertIn(block, message)
        self.assertIn(document().url, message)
        self.assertNotIn("一部省略", message)

    def test_line_budget_never_leaves_a_partial_parent_block(self):
        doc = document("\n".join(OCTOBER_PARENT_BLOCKS))
        complete = format_notification("1年生", [doc])
        for limit in range(150, len(complete) + 1):
            with self.subTest(limit=limit):
                message = format_notification("1年生", [doc], max_chars=limit)
                self.assertLessEqual(len(message), limit)
                self.assertIn(doc.url, message)
                for block in OCTOBER_PARENT_BLOCKS:
                    if block.splitlines()[0] in message:
                        self.assertIn(block, message)
                if message != complete:
                    self.assertIn("一部省略", message)

    def test_line_keeps_prior_blocks_but_does_not_skip_a_large_block_to_later_notices(self):
        first = "〇持ち物 水筒\n希望者のみです。"
        large = "〇持ち物の詳細\n" + "詳しい条件です。" * 100
        later = "〇提出 申込書"
        doc = document("\n".join([first, large, later]))
        message = format_notification("1年生", [doc], max_chars=240)
        self.assertIn(first, message)
        self.assertNotIn("〇持ち物の詳細", message)
        self.assertNotIn(later, message)
        self.assertIn("一部省略", message)
        self.assertIn(doc.url, message)

    def test_line_keeps_newest_document_order_and_complete_source_links(self):
        older = document("〇古い連絡\n希望者のみです。", url="https://example.test/20250801000000.pdf")
        newer = document("〇新しい連絡\n参加者のみです。")
        message = format_notification("1年生", [older, newer])
        self.assertIn(format_document(newer) + "\n\n" + format_document(older), message)
        self.assertTrue(message.endswith("・" + newer.url + "\n・" + older.url))


if __name__ == "__main__":
    unittest.main()
