"""用例：Mock 离线路径（extract_cards_mock）

对于没有 Key、不想等模型、只想验证「提取 → 校验 → 编辑 → 导出」的人来说，
它仍然是最快的一条路。逻辑保留在 extract_llm.extract_cards_mock。

预置卡片数据放在 tests/mock_data.MOCK_CARDS，由调用方通过 presets 注入：
生产模块里不再写死任何卡片内容（见 test_production_has_no_builtin_presets）。

行为约定：
    - 传入 presets 且文件名命中 -> 返回预置的高质量卡片
    - 未命中 / 未传 presets     -> 回落到规则提取，但 source 仍标记为 "mock"
"""

from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.notecard.note2anki.apkg import build_apkg  # noqa: E402
from services.notecard.note2anki.extract_llm import extract_cards_mock  # noqa: E402
from services.notecard.note2anki.schema import validate  # noqa: E402
from services.notecard.note2anki.server import do_extract  # noqa: E402
from tests.notecard.mock_data import MOCK_CARDS, NOTE_OUTLINE, NOTE_PLAIN  # noqa: E402


class TestMockExtract(unittest.TestCase):
    def test_production_has_no_builtin_presets(self):
        """生产模块不内置任何卡片：不传 presets 时必须走规则提取回落。

        这条守的是「测试数据不该混进生产代码」——曾经 MOCK_DB 写死在
        extract_llm.py 里，即使界面已经没有 Mock 选项也仍然随产品分发。
        """
        cards = extract_cards_mock("随便什么内容", "note-network.md")
        preset_fronts = [c.front for c in MOCK_CARDS["note-network.md"]]
        self.assertNotEqual([c.front for c in cards], preset_fronts,
                            "不传 presets 就不该返回预置卡片")

    def test_preset_cards_for_known_filenames(self):
        """注入 presets 后，样例文件名 -> 直接返回预置卡片，不跑抽取逻辑。"""
        for name in MOCK_CARDS:
            with self.subTest(filename=name):
                cards = extract_cards_mock("随便什么内容", name, presets=MOCK_CARDS)
                self.assertTrue(cards, f"{name} 应当有预置卡片")
                self.assertTrue(all(c.front and c.back for c in cards),
                                "预置卡片不该有空字段")
                self.assertTrue(all(c.source == "mock" for c in cards))

    def test_preset_is_deterministic(self):
        """同一个文件名每次返回同样的卡片——流程验证才可比。"""
        a = extract_cards_mock("", "note-network.md", presets=MOCK_CARDS)
        b = extract_cards_mock("", "note-network.md", presets=MOCK_CARDS)
        self.assertEqual([c.front for c in a], [c.front for c in b])
        self.assertGreaterEqual(len(a), 10, "预置库应当有足够多张卡覆盖界面")

    def test_unknown_filename_falls_back_to_rule(self):
        """未命中预置库时回落到规则提取，source 依然标成 mock。"""
        cards = extract_cards_mock(NOTE_PLAIN, "some-unknown-note.md", presets=MOCK_CARDS)
        self.assertTrue(cards, "回落路径也要能出卡")
        self.assertTrue(all(c.source == "mock" for c in cards))

    def test_fallback_on_outline_note_may_be_empty(self):
        """OneNote 风格的大纲笔记规则提取基本抓不到——这正是要改用 LLM 的原因。

        这里不断言「必须为空」，只断言不抛错、且结果仍然合法，
        因为规则提取器的行为会随内容微调。
        """
        cards = extract_cards_mock(NOTE_OUTLINE, "outline.md", presets=MOCK_CARDS)
        _, report = validate(cards)
        self.assertIsInstance(report["total"], int)
        self.assertEqual(report["total"], len(cards))

    def test_preset_cards_pass_validation(self):
        """预置数据是「好卡片」的样板：零错误、零警告。

        两份都要查——曾经 note-plain.txt 里混了一张是非题（yes_no_card），
        只有覆盖全部预置库才能发现。
        """
        for name in MOCK_CARDS:
            with self.subTest(filename=name):
                cards = extract_cards_mock("", name, presets=MOCK_CARDS)
                _, report = validate(cards)
                self.assertEqual(report["error"], 0, f"{name} 不该有错误：{report['by_code']}")
                self.assertEqual(report["warning"], 0, f"{name} 不该有警告：{report['by_code']}")

    def test_mode_still_accepted_by_api(self):
        """接口层仍认 mode=mock——UI 不暴露，但服务端能力没被删掉。"""
        data = do_extract({"text": NOTE_PLAIN, "filename": "note-plain.txt", "mode": "mock"})
        self.assertTrue(data["cards"])
        self.assertEqual(data["report"]["error"], 0)

    def test_preset_cards_pack_into_apkg(self):
        """预置卡片能一路走到导出：apkg 是合法 zip，笔记数与卡片数一致。"""
        cards = extract_cards_mock("", "note-network.md", presets=MOCK_CARDS)
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "mock.apkg")
            stats = build_apkg(cards, "Mock 牌组", out)
            self.assertEqual(stats["written"], len(cards))
            self.assertEqual(stats["skipped"], 0)

            with zipfile.ZipFile(out) as z:
                self.assertIn("collection.anki2", z.namelist())
                self.assertEqual(z.read("collection.anki2")[:2], b"SQ",
                                 "apkg 里的 collection 应以 SQLite 魔数开头")


if __name__ == "__main__":
    unittest.main()
