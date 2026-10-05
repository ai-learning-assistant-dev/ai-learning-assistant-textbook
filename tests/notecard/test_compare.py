"""用例：多模型对比（server.do_compare / /api/compare）

调 Prompt 的时候直接打 /api/compare 仍然是最方便的对照方式。

行为约定：
    - 规则提取总是跑（很快），作为基线列
    - 若干模型并发跑（ThreadPoolExecutor，上限 4）
    - 单个模型报错只污染自己那一列，其余照常出结果
    - 结果顺序与传入的 models 顺序一致

"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.notecard.note2anki.server import do_compare  # noqa: E402
from tests.notecard.fake_llm import fake_llm_endpoint  # noqa: E402
from tests.notecard.mock_data import (  # noqa: E402
    FAKE_API_KEY,
    FAKE_BASE_URL,
    FAKE_MODEL,
    FAKE_MODEL_B,
    MOCK_RESPONSES,
    NOTE_SECTIONED,
)


def payload(models, **extra):
    return {
        "text": NOTE_SECTIONED,
        "filename": "note.md",
        "models": models,
        "llm": {"base_url": FAKE_BASE_URL, "api_key": FAKE_API_KEY},
        **extra,
    }


class TestCompare(unittest.TestCase):
    def test_rule_only(self):
        """不填模型时只跑规则提取，基线列仍然完整。"""
        data = do_compare(payload([]))
        self.assertIn("rule", data)
        self.assertEqual(data["llm"], [])
        self.assertTrue(data["rule"]["cards"])
        self.assertIsNotNone(data["rule"]["report"])

    def test_rule_and_models_side_by_side(self):
        """规则 + 两个模型并列，每列都带上自己的报告与耗时。"""
        with fake_llm_endpoint(MOCK_RESPONSES) as rec:
            data = do_compare(payload([FAKE_MODEL, FAKE_MODEL_B]))

        self.assertEqual(len(data["llm"]), 2)
        self.assertEqual([c["label"] for c in data["llm"]], [FAKE_MODEL, FAKE_MODEL_B],
                         "结果顺序应与传入顺序一致")
        for col in data["llm"]:
            self.assertNotIn("error", col, f"{col['label']} 不该报错：{col.get('error')}")
            self.assertTrue(col["cards"], f"{col['label']} 应当有卡片")
            self.assertIsInstance(col["seconds"], float)
        self.assertEqual(rec.models, [FAKE_MODEL, FAKE_MODEL_B])

    def test_broken_model_only_poisons_its_own_column(self):
        """坏模型只让自己那一列变成 error，另一列照常出结果。"""
        with fake_llm_endpoint(MOCK_RESPONSES):
            data = do_compare(payload([FAKE_MODEL, "broken-model"]))

        good, bad = data["llm"]
        self.assertNotIn("error", good)
        self.assertTrue(good["cards"])
        self.assertIn("error", bad)
        self.assertEqual(bad["cards"], [])
        self.assertIn("JSON", bad["error"], "非 JSON 响应应报解析类错误")

    def test_unknown_model_reports_model_error(self):
        """模型名不存在 -> 「Model does not exist」，同样是只污染自己那一列。"""
        with fake_llm_endpoint(MOCK_RESPONSES):
            data = do_compare(payload([FAKE_MODEL, "no-such-model"]))

        good, bad = data["llm"]
        self.assertTrue(good["cards"])
        self.assertIn("Model does not exist", bad["error"])

    def test_empty_model_output_is_not_an_error(self):
        """模型合法地返回空数组 -> 是 0 张卡，不是错误。"""
        with fake_llm_endpoint(MOCK_RESPONSES):
            data = do_compare(payload(["empty-model"]))
        col = data["llm"][0]
        self.assertNotIn("error", col)
        self.assertEqual(col["report"]["total"], 0)

    def test_model_columns_get_validated(self):
        """每一列都过一遍校验，所以能直接看出哪个模型产了是非题。"""
        with fake_llm_endpoint(MOCK_RESPONSES):
            data = do_compare(payload([FAKE_MODEL, FAKE_MODEL_B]))

        codes = {c["label"]: c["report"]["by_code"] for c in data["llm"]}
        self.assertNotIn("yes_no_card", codes[FAKE_MODEL], "DeepSeek 模拟输出不该有是非题")
        self.assertIn("yes_no_card", codes[FAKE_MODEL_B], "Qwen 模拟输出应当命中 yes_no_card")

    def test_section_switch_applies_to_rule_column(self):
        """规则基线列同样受章节汇总卡开关影响。"""
        with fake_llm_endpoint(MOCK_RESPONSES):
            off = do_compare(payload([], include_section_cards=False))
            on = do_compare(payload([], include_section_cards=True))
        self.assertGreater(on["rule"]["report"]["total"], off["rule"]["report"]["total"])

    def test_models_accept_comma_string(self):
        """接口同时接受逗号分隔的字符串，这是 UI 原来的传法。"""
        with fake_llm_endpoint(MOCK_RESPONSES) as rec:
            data = do_compare(payload(f"{FAKE_MODEL}, {FAKE_MODEL_B}"))
        self.assertEqual(len(data["llm"]), 2)
        self.assertEqual(rec.models, [FAKE_MODEL, FAKE_MODEL_B])


if __name__ == "__main__":
    unittest.main()
