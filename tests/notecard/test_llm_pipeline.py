"""用例：带 Key 的 LLM 全流程（用的是假 Key + 假端点）

这一组回答的是「新来的人怎么在没有真 Key 的情况下验证整条链路」：
tests/mock_data.py 里有一份假的 Key 和假的模型返回，
tests/fake_llm.py 把网络请求拦在本机，于是下面这条链可以完整跑一遍：

    笔记文本 -> LLM 提取 -> 校验 -> 编辑 -> 导出 apkg

真跑的时候只需要把 LLMConfig 里的 api_key / base_url / model 换成真的，
其余代码路径完全一样。
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.notecard.note2anki.apkg import build_apkg  # noqa: E402
from services.notecard.note2anki.extract_llm import (  # noqa: E402
    LLMConfig,
    LLMError,
    LLMNotConfigured,
    extract_cards_llm,
)
from services.notecard.note2anki.schema import Card, validate  # noqa: E402
from tests.notecard.fake_llm import fake_llm_endpoint  # noqa: E402
from tests.notecard.mock_data import (  # noqa: E402
    FAKE_API_KEY,
    FAKE_BASE_URL,
    FAKE_MODEL,
    FAKE_MODEL_B,
    MOCK_RESPONSES,
    NOTE_SECTIONED,
)

CFG = LLMConfig(base_url=FAKE_BASE_URL, api_key=FAKE_API_KEY, model=FAKE_MODEL)


def notes_in_apkg(path: str) -> tuple[int, list[str]]:
    """解包 apkg，返回 (笔记数, 前两条正面)。"""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "c.db"
        with zipfile.ZipFile(path) as z:
            db.write_bytes(z.read("collection.anki2"))
        con = sqlite3.connect(str(db))
        rows = con.execute("select flds from notes").fetchall()
        con.close()
    return len(rows), [r[0].split("\x1f")[0] for r in rows[:2]]


class TestLlmPipeline(unittest.TestCase):
    def test_requires_key(self):
        """没填 Key 时明确报 LLMNotConfigured，而不是发出一个无效请求。"""
        with self.assertRaises(LLMNotConfigured):
            extract_cards_llm(NOTE_SECTIONED, LLMConfig(base_url=FAKE_BASE_URL, api_key=""))

    def test_request_carries_key_and_prompt(self):
        """请求里应当带上 Bearer Key、model，以及系统提示词。"""
        with fake_llm_endpoint(MOCK_RESPONSES) as rec:
            extract_cards_llm(NOTE_SECTIONED, CFG)

        self.assertEqual(len(rec.calls), 1)
        call = rec.calls[0]
        self.assertTrue(call["auth"].startswith("Bearer "))
        self.assertIn(FAKE_API_KEY, call["auth"])
        self.assertEqual(call["model"], FAKE_MODEL)
        self.assertIn("闪卡", call["system"])
        self.assertIn("计算机网络", call["user"], "笔记正文应当被送进 user 消息")

    def test_extract_from_fake_response(self):
        """假端点返回的卡片能被正确解析成 Card。"""
        with fake_llm_endpoint(MOCK_RESPONSES):
            cards = extract_cards_llm(NOTE_SECTIONED, CFG)

        self.assertEqual(len(cards), 6)
        self.assertTrue(all(c.source == "llm" for c in cards))
        self.assertTrue(all(c.front.endswith("？") for c in cards), "正面都应是问句")
        self.assertTrue(any("<b>" in c.back for c in cards), "HTML 标记应当被保留")

    def test_tolerates_code_fence(self):
        """模型爱用 ```json 包一层，解析器要能抠出来。"""
        with fake_llm_endpoint(MOCK_RESPONSES):
            cards = extract_cards_llm(NOTE_SECTIONED, CFG)
        self.assertTrue(cards, "带代码围栏的响应不该被当成解析失败")

    def test_broken_response_raises_llm_error(self):
        """模型返回非 JSON 时报 LLMError，而不是抛一堆栈给调用方。"""
        with fake_llm_endpoint(MOCK_RESPONSES):
            with self.assertRaises(LLMError):
                extract_cards_llm(NOTE_SECTIONED, LLMConfig(
                    base_url=FAKE_BASE_URL, api_key=FAKE_API_KEY, model="broken-model"))

    def test_yes_no_cards_are_flagged(self):
        """是非题命中 yes_no_card —— 这条规则就是为这个场景加的。"""
        with fake_llm_endpoint(MOCK_RESPONSES):
            cards = extract_cards_llm(NOTE_SECTIONED,
                                      LLMConfig(base_url=FAKE_BASE_URL,
                                                api_key=FAKE_API_KEY, model=FAKE_MODEL_B))
        _, report = validate(cards)
        self.assertIn("yes_no_card", report["by_code"])
        self.assertEqual(report["error"], 0, "是非题只是警告，不该阻断导出")

    def test_full_pipeline_to_apkg(self):
        """提取 -> 校验 -> 编辑 -> 导出，并解包确认编辑真的进了 apkg。"""
        with fake_llm_endpoint(MOCK_RESPONSES):
            cards = extract_cards_llm(NOTE_SECTIONED, CFG)
        cards, report = validate(cards)
        self.assertFalse(report["blocking"], f"不该有阻断性错误：{report['by_code']}")

        # 模拟在界面上改第一张卡
        cards[0].front = "【已编辑】" + cards[0].front
        cards, report = validate(cards)

        with tempfile.TemporaryDirectory() as tmp:
            first = str(Path(tmp) / "a.apkg")
            second = str(Path(tmp) / "b.apkg")
            build_apkg(cards, "测试牌组", first)
            build_apkg(cards, "测试牌组", second)

            n1, fronts1 = notes_in_apkg(first)
            n2, fronts2 = notes_in_apkg(second)

        self.assertEqual(n1, len(cards))
        self.assertTrue(fronts1[0].startswith("【已编辑】"), "界面上的编辑应当进了 apkg")
        # ID 稳定：同一批卡导两次，内容一致（重复导入不会产生重复笔记）
        self.assertEqual(fronts1, fronts2)

    def test_empty_front_blocks_export(self):
        """空正面是 error，会被导出前的校验拦住。"""
        cards = [Card(front="", back="有答案没问题是没法背的", source="llm")]
        _, report = validate(cards)
        self.assertTrue(report["blocking"])
        self.assertIn("empty_front", report["by_code"])


if __name__ == "__main__":
    unittest.main()
