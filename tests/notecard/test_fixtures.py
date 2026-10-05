"""用例：真实笔记样例（tests/fixtures/）

想验证管线在真实形态的笔记上表现如何，就跑这一组。

    note-network.md   带 YAML frontmatter、多级标题、列表、表格的 Markdown
    note-plain.txt    没有 Markdown 结构的纯文本（含 Q/A 对）

它们同时充当「可执行样例」：直接 python 跑这个文件，
会打印每份笔记在规则提取下的产出，方便肉眼检查。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.notecard.note2anki.extract_llm import extract_cards_mock  # noqa: E402
from services.notecard.note2anki.extract_rule import extract_cards  # noqa: E402
from services.notecard.note2anki.schema import validate  # noqa: E402
from tests.notecard.mock_data import (  # noqa: E402
    FIXTURES,
    MOCK_CARDS,
    load_all_fixtures,
    load_fixture,
)


class TestFixtures(unittest.TestCase):
    def test_every_fixture_is_readable(self):
        """每份样例都在，且读出来非空。"""
        data = load_all_fixtures()
        self.assertEqual(tuple(data.keys()), FIXTURES)
        for name, text in data.items():
            with self.subTest(fixture=name):
                self.assertGreater(len(text.strip()), 100, f"{name} 内容太短")

    def test_missing_fixture_raises(self):
        """读不存在的样例要明确报错，而不是静默返回空。"""
        with self.assertRaises(FileNotFoundError):
            load_fixture("no-such-note.md")

    def test_markdown_fixture_produces_cards(self):
        """Markdown 样例：规则提取应当能挖出定义卡与端口卡。"""
        cards = extract_cards(load_fixture("note-network.md"), as_markdown=True)
        self.assertTrue(cards, "Markdown 样例不该一张都提不出来")

        fronts = " ".join(c.front for c in cards)
        self.assertIn("端口", fronts, "列表项应当被抽成定义卡")

        _, report = validate(cards)
        self.assertEqual(report["error"], 0, f"不该有结构性错误：{report['by_code']}")
        self.assertNotIn("md_table_residue", report["by_code"], "表格应当已被转成 HTML")

    def test_plain_fixture_produces_cards(self):
        """纯文本样例：没有标题树，靠「术语：定义」和 Q/A 行出题。"""
        cards = extract_cards(load_fixture("note-plain.txt"), as_markdown=False)
        self.assertTrue(cards, "纯文本样例不该一张都提不出来")

        fronts = " ".join(c.front for c in cards)
        self.assertTrue(any("有氧呼吸" in f or "糖酵解" in f for f in [fronts]),
                        f"应当问到呼吸相关的概念：{fronts[:120]}")

    def test_frontmatter_is_not_turned_into_cards(self):
        """frontmatter 里的 title / tags 不该变成「什么是 title？」这种废卡。"""
        cards = extract_cards(load_fixture("note-network.md"), as_markdown=True)
        for c in cards:
            self.assertNotIn("title", c.front.lower(), f"frontmatter 泄漏成卡片：{c.front}")
            self.assertNotIn("tags", c.front.lower(), f"frontmatter 泄漏成卡片：{c.front}")

    def test_fixture_names_match_mock_presets(self):
        """两份样例的文件名正好是 Mock 预置库的 key —— 便于用它们走通流程。"""
        for name in FIXTURES:
            with self.subTest(fixture=name):
                self.assertIn(name, MOCK_CARDS)
                cards = extract_cards_mock(load_fixture(name), name, presets=MOCK_CARDS)
                _, report = validate(cards)
                self.assertEqual(report["warning"], 0, f"{name} 预置卡不该有警告")
                self.assertEqual(report["error"], 0)


def _demo() -> None:
    """直接跑这个文件时的演示输出：每份样例产出什么。"""
    for name in FIXTURES:
        text = load_fixture(name)
        md = name.endswith(".md")
        cards, report = validate(extract_cards(text, as_markdown=md))
        print(f"\n===== {name} （{len(text)} 字符）=====")
        print(f"规则提取 {report['total']} 张 | 无问题 {report['clean']} "
              f"| 错误 {report['error']} | 警告 {report['warning']} {report['by_code'] or ''}")
        for i, c in enumerate(cards, 1):
            flag = "!" if any(x["level"] == "error" for x in c.issues) else (
                "?" if c.issues else " ")
            print(f"  {flag}{i:>2}. {c.front[:56]}")
            print(f"        -> {c.back[:70]}")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        _demo()
    else:
        unittest.main()
