"""用例：章节汇总卡（include_section_cards）

背景：这个功能已从界面移除（实测与列表项 / 定义卡高度重复），
但提取逻辑完整保留在 extract_rule.extract_cards 里，随时可以打开。

它做两件事：
    1. 标题 + ≥2 个列表项  -> 「X 的关键要点有哪些？」背面是 <ul><li> 汇总
    2. 标题 + 段落(>20字)  -> 「请解释：X」背面是整段原文
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.notecard.note2anki.extract_rule import extract_cards  # noqa: E402
from services.notecard.note2anki.schema import validate  # noqa: E402
from services.notecard.note2anki.server import do_extract  # noqa: E402
from tests.notecard.mock_data import NOTE_PLAIN, NOTE_SECTIONED  # noqa: E402

SUMMARY_MARKERS = ("的关键要点有哪些？", "请解释：")


def is_summary_card(front: str) -> bool:
    return any(m in front for m in SUMMARY_MARKERS)


class TestSectionCards(unittest.TestCase):
    def test_off_by_default(self):
        """默认（不传参）不产章节汇总卡。"""
        cards = extract_cards(NOTE_SECTIONED)
        self.assertTrue(cards, "基础抽取应当有产出")
        summaries = [c for c in cards if is_summary_card(c.front)]
        self.assertEqual(summaries, [], "默认应当不含章节汇总卡")

    def test_on_adds_summary_cards(self):
        """打开开关后，汇总卡出现，且总量增加。"""
        off = extract_cards(NOTE_SECTIONED, include_section_cards=False)
        on = extract_cards(NOTE_SECTIONED, include_section_cards=True)

        summaries = [c for c in on if is_summary_card(c.front)]
        self.assertTrue(summaries, "打开开关后应当出现章节汇总卡")
        self.assertGreater(len(on), len(off),
                           f"开启后应更多：off={len(off)} on={len(on)}")

    def test_summary_card_shapes(self):
        """两种汇总卡各自的形态：列表型背面是 <ul>，段落型背面是原文。"""
        on = extract_cards(NOTE_SECTIONED, include_section_cards=True)
        fronts = {c.front: c.back for c in on if is_summary_card(c.front)}

        list_cards = {f: b for f, b in fronts.items() if "关键要点" in f}
        para_cards = {f: b for f, b in fronts.items() if "请解释" in f}

        self.assertTrue(list_cards, "应当有列表型汇总卡")
        for front, back in list_cards.items():
            self.assertTrue(back.startswith("<ul>"), f"列表汇总卡背面应是 <ul>：{front}")
            self.assertIn("<li>", back)
            self.assertNotIn("|", back, "汇总卡背面不该残留 Markdown 表格管道符")

        if para_cards:
            for front, back in para_cards.items():
                self.assertGreater(len(back), 20, f"段落汇总卡背面太短：{front}")

    def test_summary_cards_survive_validation(self):
        """汇总卡能通过校验：允许 warning，但不能有阻断导出的 error。"""
        on = extract_cards(NOTE_SECTIONED, include_section_cards=True)
        _, report = validate(on)
        self.assertEqual(report["error"], 0,
                         f"不该有结构性错误：{report['by_code']}")
        self.assertFalse(report["blocking"])

    def test_switch_reachable_from_api(self):
        """接口层仍然接受这个开关——UI 不暴露，但服务端能力没被删掉。"""
        base = {"text": NOTE_SECTIONED, "filename": "note.md", "mode": "rule"}
        off = do_extract({**base, "include_section_cards": False})
        on = do_extract({**base, "include_section_cards": True})
        self.assertGreater(on["report"]["total"], off["report"]["total"])

    def test_no_structure_note_produces_nothing_extra(self):
        """纯文本没有 Markdown 标题树，开关开不开都一样（不会凭空造卡）。"""
        off = extract_cards(NOTE_PLAIN, include_section_cards=False)
        on = extract_cards(NOTE_PLAIN, include_section_cards=True)
        self.assertEqual(len(off), len(on))
        self.assertEqual([c.front for c in off], [c.front for c in on])


if __name__ == "__main__":
    unittest.main()
