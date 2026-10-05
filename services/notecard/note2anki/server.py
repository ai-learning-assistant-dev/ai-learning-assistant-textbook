"""

Note2Anki 的业务函数层（与 HTTP 无关）。

无状态：卡片列表由浏览器持有，每次校验 / 导出都整份回传。
这样刷新页面不会丢状态之外的东西，也省掉了服务端会话管理。

"""

from __future__ import annotations

import os
import re
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from .apkg import build_apkg
from .extract_llm import LLMConfig, LLMError, LLMNotConfigured, extract_cards_llm, extract_cards_mock
from .extract_rule import extract_cards as rule_extract
from .onenote_api import OneNoteError, browse, list_pages, render_page, render_section, scan
from .schema import Card, validate

# 迁出独立项目后层级变了：
# services/notecard/note2anki/server.py → 上溯四级才是项目根（原来是两级）
ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "out"

# 导出文件的下载前缀，由 routes.py 的 Blueprint 提供
OUT_URL_PREFIX = "/api/notecard/out/"

_MAX_BODY = 8 * 1024 * 1024


def _as_markdown(filename: str) -> bool:
    return Path(filename or "").suffix.lower() in {".md", ".markdown", ".mdown"}


def _json_cards(cards) -> list[dict]:
    return [c.to_dict() for c in cards]


def _read_cards(payload: dict) -> list[Card]:
    raw = payload.get("cards")
    if not isinstance(raw, list):
        raise ValueError("cards 必须是数组")
    return [Card.from_dict(d) for d in raw if isinstance(d, dict)]


def _llm_config(payload: dict) -> LLMConfig:
    """构造 LLM 配置。Key 优先取请求体，其次回落环境变量（不落盘）。"""
    cfg = payload.get("llm") or {}
    return LLMConfig(
        base_url=str(cfg.get("base_url") or "https://api.siliconflow.cn/v1"),
        api_key=str(cfg.get("api_key") or os.environ.get("SILICONFLOW_API_KEY")
                    or os.environ.get("OPENAI_API_KEY") or ""),
        model=str(cfg.get("model") or "deepseek-ai/DeepSeek-V3.2"),
        temperature=float(cfg.get("temperature") or 0.2),
    )


def do_extract(payload: dict) -> dict:
    text = str(payload.get("text") or "")
    filename = str(payload.get("filename") or "note.md")
    mode = str(payload.get("mode") or "rule").lower()
    include_section = bool(payload.get("include_section_cards", False))

    if not text.strip():
        raise ValueError("输入内容为空")

    if mode == "mock":
        # 离线路径：不联网，等价于规则提取但 source 标为 "mock"。
        # 预置卡片（presets）不内置于服务，只在测试里注入。
        cards = extract_cards_mock(text, filename)
    elif mode == "rule":
        cards = rule_extract(text, include_section_cards=include_section,
                             as_markdown=_as_markdown(filename))
    elif mode == "llm":
        cards = extract_cards_llm(text, _llm_config(payload), hint=str(payload.get("hint") or ""))
    else:
        raise ValueError(f"未知的提取模式：{mode}")

    cards, report = validate(cards)
    return {"cards": _json_cards(cards), "report": report}


def _run_llm(text: str, model: str, base: LLMConfig, hint: str = "") -> dict:
    t0 = time.time()
    cards, report = validate(extract_cards_llm(text, replace(base, model=model), hint=hint))
    return {
        "label": model,
        "cards": _json_cards(cards),
        "report": report,
        "seconds": round(time.time() - t0, 1),
    }


def do_compare(payload: dict) -> dict:
    """同一份笔记跑规则提取 + 若干个模型，结果并列返回，供调 Prompt 时对照。"""
    text = str(payload.get("text") or "")
    filename = str(payload.get("filename") or "note.md")
    if not text.strip():
        raise ValueError("输入内容为空")

    raw_models = payload.get("models")
    if isinstance(raw_models, str):
        models = [m.strip() for m in re.split(r"[,，]", raw_models) if m.strip()]
    else:
        models = [str(m).strip() for m in (raw_models or []) if str(m).strip()]

    # 规则提取很快，直接跑
    t0 = time.time()
    rule_cards, rule_report = validate(
        rule_extract(text, include_section_cards=bool(payload.get("include_section_cards", False)),
                     as_markdown=_as_markdown(filename))
    )
    rule = {
        "label": "规则提取（兜底）",
        "cards": _json_cards(rule_cards),
        "report": rule_report,
        "seconds": round(time.time() - t0, 2),
    }

    llm_results: list[dict] = []
    if models:
        base = _llm_config(payload)
        hint = str(payload.get("hint") or "")
        # 多个模型并发跑，否则串行要等 N 倍时间
        with ThreadPoolExecutor(max_workers=min(len(models), 4)) as pool:
            futures = [pool.submit(_run_llm, text, m, base, hint) for m in models]
            for m, fut in zip(models, futures):
                try:
                    llm_results.append(fut.result())
                except Exception as exc:  # noqa: BLE001
                    llm_results.append({"label": m, "error": f"{type(exc).__name__}: {exc}",
                                        "cards": [], "report": None, "seconds": 0})

    return {"rule": rule, "llm": llm_results}


# ---------- OneNote 源 ----------
#
# 这一组接口只做「路径 → 可交互的树 → Markdown」，产出的 Markdown
# 直接交给上面的提取管线，所以卡片生成那一段完全不用感知来源。


def do_onenote_browse(payload: dict) -> dict:
    return browse(str(payload.get("path") or ""))


def do_onenote_scan(payload: dict) -> dict:
    return scan(str(payload.get("path") or ""),
                include_recycle=bool(payload.get("include_recycle", False)))


def do_onenote_pages(payload: dict) -> dict:
    return list_pages(str(payload.get("section") or ""))


def do_onenote_page(payload: dict) -> dict:
    return render_page(str(payload.get("section") or ""), int(payload.get("index") or 1))


def do_onenote_section(payload: dict) -> dict:
    return render_section(str(payload.get("section") or ""))


def do_validate(payload: dict) -> dict:
    cards, report = validate(_read_cards(payload))
    return {"cards": _json_cards(cards), "report": report}


def do_export(payload: dict) -> dict:
    cards = _read_cards(payload)
    cards, report = validate(cards)
    if report["blocking"]:
        raise ValueError(f"存在 {report['error']} 处结构性错误，请先修复后再导出")

    deck_name = str(payload.get("deck_name") or "Note2Anki").strip() or "Note2Anki"
    stamp = datetime.now().strftime("%H%M%S")
    safe = re.sub(r'[\\/:*?"<>|\s]+', "-", deck_name).strip("-") or "Note2Anki"
    filename = f"{safe}-{stamp}.apkg"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stats = build_apkg(cards, deck_name, str(OUT_DIR / filename))
    stats["filename"] = filename
    stats["url"] = OUT_URL_PREFIX + urllib.parse.quote(filename)
    stats["report"] = report
    return stats


