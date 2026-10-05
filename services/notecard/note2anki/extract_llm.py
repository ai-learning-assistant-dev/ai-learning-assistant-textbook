"""LLM 提取层：OpenAI 兼容调用 + 离线回落。

两种提取路径：
    - extract_cards_llm   真实调用，填 LLMConfig 的 base_url / api_key / model 即用，
                          覆盖 OpenAI、DeepSeek、硅基流动、Ollama、OpenRouter 等兼容端点。
    - extract_cards_mock  不联网的离线路径，回落到规则提取；可选的 presets 由调用方注入。

本模块不内置任何样例卡片内容，测试数据一律放在 tests/ 下。
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from .preprocess import strip_frontmatter
from .schema import Card, normalize_tags

SYSTEM_PROMPT = """你是一名闪卡设计专家，负责把学习材料转换成 Anki 的 Basic 卡片（正面问题 + 反面答案）。

严格遵守以下规则：
1. 每张卡片只覆盖一个知识点（最小信息原则）。不要把多个概念塞进同一张卡。
2. 正面必须是一个精确的问句，能从反面唯一确定答案，避免「请解释：XXX」这种模糊问法。
3. 反面简洁但完整，控制在 200 字以内。
4. 覆盖材料中的核心概念、定义、因果、对比、数字与例外。
5. 不要生成与已有内容重复的卡片。
6. 不要为 YAML frontmatter（title/tags/date 等元信息）生成卡片。
7. 表格类内容转成 HTML 的 <table>，行内标记用 <b> / <i> / <code>。
8. 只输出 JSON，不要任何解释文字、不要 Markdown 代码围栏。

输出格式（JSON 数组）：
[{"front": "问句", "back": "答案", "tags": ["标签"]}]"""

USER_TEMPLATE = """请把下面的学习材料转换成 Basic 闪卡。

{extra}

材料正文：
---
{text}
---"""


class LLMNotConfigured(RuntimeError):
    """未提供 api_key 或 base_url。"""


class LLMError(RuntimeError):
    """调用失败或返回无法解析。"""


@dataclass
class LLMConfig:
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.2
    timeout: int = 180


def extract_cards_mock(
    text: str,
    filename: str = "",
    presets: dict[str, list[Card]] | None = None,
) -> list[Card]:
    """离线提取：命中 presets 就返回预置卡片，否则回落到规则提取。

    本模块不内置任何卡片内容 —— presets 由调用方注入（生产侧不传，
    测试侧传 tests/mock_data.MOCK_CARDS）。这样「好卡片长什么样」的样板
    数据留在测试里，生产模块只保留提取逻辑本身。
    """
    if presets and filename in presets:
        return [
            Card(front=c.front, back=c.back, tags=list(c.tags), source="mock")
            for c in presets[filename]
        ]
    from .extract_rule import extract_cards as rule_extract
    cards = rule_extract(text)
    for c in cards:
        c.source = "mock"
    return cards


# ---------------------------------------------------------------------------
# 真实调用
# ---------------------------------------------------------------------------

_RE_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def _parse_json_response(raw: str) -> list[dict]:
    """从模型返回里抠出 JSON 数组，容忍代码围栏和前后废话。"""
    cleaned = raw.strip()
    m = _RE_FENCE.search(cleaned)
    if m:
        cleaned = m.group(1).strip()
    if not cleaned.startswith("["):
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start == -1 or end == -1:
            raise LLMError("模型返回中没有找到 JSON 数组")
        cleaned = cleaned[start: end + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError(f"模型返回的 JSON 无法解析：{exc}") from exc
    if isinstance(data, dict):
        for key in ("cards", "data", "items", "result"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise LLMError("模型返回的不是卡片数组")
    return data


def _to_cards(items: list[dict]) -> list[Card]:
    cards: list[Card] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        tags = normalize_tags(it.get("tags"))
        cards.append(Card(
            front=str(it.get("front") or it.get("question") or it.get("q") or ""),
            back=str(it.get("back") or it.get("answer") or it.get("a") or ""),
            tags=tags if tags is not None else [],
            source="llm",
        ))
    return cards


def _chat(cfg: LLMConfig, system: str, user: str) -> str:
    if not cfg.api_key or not cfg.base_url:
        raise LLMNotConfigured("未配置 api_key / base_url，无法调用模型")

    url = cfg.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg.model,
        "temperature": cfg.temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise LLMError(f"模型返回 HTTP {exc.code}：{detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(f"无法连接模型服务：{exc.reason}") from exc

    try:
        return body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"模型返回结构异常：{str(body)[:300]}") from exc


def extract_cards_llm(
    text: str,
    cfg: LLMConfig,
    *,
    hint: str = "",
    extra_tags: list[str] | None = None,
) -> list[Card]:
    """调用 OpenAI 兼容端点提取卡片。"""
    body, _ = strip_frontmatter(text)
    user = USER_TEMPLATE.format(text=body, extra=hint or "（无额外要求）")
    raw = _chat(cfg, SYSTEM_PROMPT, user)
    cards = _to_cards(_parse_json_response(raw))
    if extra_tags:
        for c in cards:
            c.tags = list(dict.fromkeys(list(c.tags) + list(extra_tags)))
    return cards
