"""假的 OpenAI 兼容端点。

extract_llm._chat 走的是 urllib.request.urlopen，这里把它整个换掉，
于是「配了 Key 的 LLM 流程」可以在没有网络、没有真 Key 的情况下被完整验证。

用法：

    from tests.notecard.fake_llm import fake_llm_endpoint
    from tests import mock_data

    with fake_llm_endpoint(mock_data.MOCK_RESPONSES) as rec:
        cards = extract_cards_llm(text, cfg)
    assert rec.calls[0]["model"] == "deepseek-ai/DeepSeek-V3.2"
    assert rec.calls[0]["auth"].startswith("Bearer ")
"""

from __future__ import annotations

import io
import json
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class Recorder:
    """记录每次被拦下的请求，便于断言 Key / model / 消息体是否正确带上。"""

    calls: list[dict] = field(default_factory=list)

    @property
    def models(self) -> list[str]:
        return [c["model"] for c in self.calls]


class _FakeResp:
    """最小化的 urlopen 返回值：只要支持上下文管理器和 read() 就够。"""

    def __init__(self, payload: dict) -> None:
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def read(self) -> bytes:
        return self._buf.read()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@contextmanager
def fake_llm_endpoint(responses: dict[str, str], default: str | None = None):
    """按 model 名返回模拟内容；查不到时用 default，仍查不到就抛 LLMError。

    responses: {model: 模型返回的 content 字符串}
    """
    import services.notecard.note2anki.extract_llm as extract_llm

    rec = Recorder()
    original = urllib.request.urlopen

    def _fake(req, *args, **kwargs):
        body = json.loads(req.data.decode("utf-8"))
        model = body.get("model", "")
        rec.calls.append({
            "url": req.full_url,
            "model": model,
            "auth": req.headers.get("Authorization", ""),
            "system": next(
                (m["content"] for m in body.get("messages", []) if m["role"] == "system"), ""),
            "user": next(
                (m["content"] for m in body.get("messages", []) if m["role"] == "user"), ""),
        })

        content = responses.get(model, default)
        if content is None:
            # 让调用方看到和真实「模型不存在」一样的错误形态
            raise extract_llm.LLMError(f"Model does not exist: {model}")
        return _FakeResp({
            "choices": [{"message": {"role": "assistant", "content": content}}],
        })

    urllib.request.urlopen = _fake  # type: ignore[assignment]
    try:
        yield rec
    finally:
        urllib.request.urlopen = original  # type: ignore[assignment]
