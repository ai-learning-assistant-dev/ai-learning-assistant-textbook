"""测试用的模拟数据：笔记样例 + 模拟模型返回 + 假 Key。

放在这里的目的是让后来的人在没有真 Key、没有网络的情况下，
也能把「LLM 提取 → 校验 → 编辑 → apkg」整条流程跑一遍。

这里的 Key 是假的，不会、也不需要真的发出请求：
fake_llm.py 会把 urllib.request.urlopen 换掉，请求根本不出本机。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.notecard.note2anki.schema import Card  # noqa: E402

# ---------------------------------------------------------------------------
# 真实笔记样例（fixtures）
#
# 这两份笔记原本是界面上的「内置样例」，现在搬到 tests/fixtures/：
# 不再作为产品的一部分分发，只作为开发者跑流程用的可执行样例。
# mock_data 里的内联文本是「小而精的测试输入」，
# fixtures 是「真实形态的完整笔记」，两者用途不同，都需要。
# ---------------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"

#: 可用的样例文件名
FIXTURES: tuple[str, ...] = ("note-network.md", "note-plain.txt")


def load_fixture(name: str) -> str:
    """读取一份真实笔记样例。"""
    path = FIXTURE_DIR / name
    if not path.is_file():
        raise FileNotFoundError(
            f"没有这份样例：{name}，可用的是 {', '.join(FIXTURES)}")
    return path.read_text(encoding="utf-8")


def load_all_fixtures() -> dict[str, str]:
    return {name: load_fixture(name) for name in FIXTURES}


# ---------------------------------------------------------------------------
# 假的 LLM 凭据（模拟「用户填了 Key」的情形）
# ---------------------------------------------------------------------------

FAKE_API_KEY = "sk-mock-00000000000000000000000000000000"
FAKE_BASE_URL = "https://api.siliconflow.cn/v1"
FAKE_MODEL = "deepseek-ai/DeepSeek-V3.2"
FAKE_MODEL_B = "Qwen/Qwen3-32B"

# ---------------------------------------------------------------------------
# 笔记样例
# ---------------------------------------------------------------------------

# 带标题 / 列表 / 段落 / 问答对，用来观察章节汇总卡的开关效果
NOTE_SECTIONED = """---
title: 计算机网络速记
tags: [networking, cs]
---

# 计算机网络

## 常见端口

- 80：HTTP 明文网页服务
- 443：HTTPS 加密网页服务
- 22：SSH 远程登录服务

## TCP 与 UDP

TCP 是面向连接的协议，通过三次握手建立连接并确认重传。
UDP 无连接、不保证送达，但开销小、延迟低。

## DNS 查询

Q: 递归查询和迭代查询的区别是什么？
A: 递归查询由服务器代查到底，客户端只等结果；迭代查询每次只返回下一级服务器地址。

MTU：链路层一次能传输的最大数据包大小，以太网通常为 1500 字节。
"""

# 纯文本，无 Markdown 结构
NOTE_PLAIN = """细胞呼吸

有氧呼吸：需要氧气参与，一分子葡萄糖约产 30-32 个 ATP。
无氧呼吸：不需要氧气，只产 2 个 ATP，产物是乳酸或酒精。
糖酵解：发生在细胞质基质，是有氧与无氧呼吸共同的第一阶段。
"""

# OneNote 风格的大纲笔记：列表为主，规则提取在这里基本抓不到东西
NOTE_OUTLINE = """# 打孔编程

## 大纲

- 注意，第四个的部分，前两个是 ALU 模式，后面的 4 是 ADD Branch
- 这个难道不应该是随着自己的设计变化而变化吗
- 需要确认跳转表的实现方式
"""

# ---------------------------------------------------------------------------
# 模拟模型返回（OpenAI 兼容的响应体）
# ---------------------------------------------------------------------------


def chat_response(content: str) -> dict:
    """包一个 OpenAI 兼容的 /chat/completions 响应体。"""
    return {
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "model": FAKE_MODEL,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": content},
             "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


# DeepSeek 风格：问句精确，会用 HTML 标记
RESPONSE_GOOD = """```json
[
  {"front": "TCP 和 UDP 在可靠性上的核心区别是什么？",
   "back": "TCP 面向连接，通过确认与重传保证<b>可靠、按序</b>到达；UDP 无连接、不保证送达，但延迟低。",
   "tags": ["networking"]},
  {"front": "80 端口通常对应什么服务？", "back": "HTTP 明文网页服务。", "tags": ["port"]},
  {"front": "443 端口通常对应什么服务？", "back": "HTTPS 加密网页服务。", "tags": ["port"]},
  {"front": "22 端口通常对应什么服务？", "back": "SSH 远程登录服务。", "tags": ["port"]},
  {"front": "什么是 MTU？", "back": "链路层一次能传输的最大数据包大小，以太网通常 1500 字节。", "tags": []},
  {"front": "DNS 递归查询与迭代查询的区别是什么？",
   "back": "递归由服务器代查到底，客户端只等结果；<br>迭代每次只返回下一级服务器地址。",
   "tags": ["dns"]}
]
```"""

# Qwen 风格：爱出是非题，用来验证 yes_no_card 校验项能被命中
RESPONSE_YESNO = """[
  {"front": "TCP 是面向连接的协议吗？", "back": "是的，TCP 是面向连接的协议，通信前要三次握手。", "tags": []},
  {"front": "UDP 传输是否可靠？", "back": "否，UDP 是无连接、不可靠的传输协议。", "tags": []},
  {"front": "80 端口是 HTTP 吗？", "back": "是的，80 端口默认承载 HTTP 明文服务。", "tags": []}
]"""

# 模型正常响应，但内容不是 JSON —— 用来验证解析失败会被转成 LLMError
RESPONSE_BROKEN = "抱歉，我无法处理这个请求。"

# 空数组：模型认为没有可提取的知识点
RESPONSE_EMPTY = "[]"

# 按模型名索引的模拟返回，供对比用例使用。
# 注意：不在这个字典里的模型名，会被 fake_llm 当成「模型不存在」处理，
# 那是另一条错误路径（HTTP 层），不要和 RESPONSE_BROKEN（解析层）混淆。
MOCK_RESPONSES: dict[str, str] = {
    FAKE_MODEL: RESPONSE_GOOD,
    FAKE_MODEL_B: RESPONSE_YESNO,
    "broken-model": RESPONSE_BROKEN,
    "empty-model": RESPONSE_EMPTY,
}


# ---------------------------------------------------------------------------
# Mock 预置卡片（extract_cards_mock 的 presets）
#
# 这一组数据原本写死在 note2anki/extract_llm.py 里，属于生产模块混入了测试数据。
# 现在搬到这里：它是「好卡片」的样板，用例子说明 BasicCard 应该长什么样，
# 同时让 extract_cards_mock 这条离线路径在没有真 Key 时也能被验证。
# 生产代码不再内置任何卡片内容，presets 由调用方（测试）注入。
# ---------------------------------------------------------------------------


def _network_cards() -> list[Card]:
    tags = ["networking", "cs"]
    raw = [
        ("TCP 和 UDP 在可靠性上的核心区别是什么？",
         "TCP 面向连接、通过确认与重传保证数据按序可靠到达；UDP 无连接、不保证送达，但开销小、延迟低。"),
        ("TCP 三次握手的三个报文依次是什么？",
         "客户端发 SYN，服务端回 SYN-ACK，客户端再回 ACK，连接建立完成。"),
        ("为什么 UDP 更适合音视频流媒体？",
         "UDP 无连接、无重传，延迟低；偶尔丢包对观感的影响小于重传带来的卡顿。"),
        ("80 端口通常对应什么服务？",
         "HTTP 明文网页服务。"),
        ("443 端口通常对应什么服务？",
         "HTTPS 加密网页服务。"),
        ("22 端口通常对应什么服务？",
         "SSH 远程登录。"),
        ("3306 端口通常对应什么服务？",
         "MySQL 数据库默认端口。"),
        ("HTTP 4xx 状态码表示什么？",
         "客户端错误，请求本身有问题，例如 404 表示资源不存在。"),
        ("HTTP 5xx 状态码表示什么？",
         "服务端错误，服务端处理请求时失败，例如 500 表示内部错误。"),
        ("什么是 MTU？",
         "Maximum Transmission Unit，链路层一次能传输的最大数据包大小，以太网通常为 1500 字节。"),
        ("DNS 递归查询与迭代查询的区别是什么？",
         "递归查询由 DNS 服务器代为完成全部查询，客户端只等最终结果；迭代查询中服务器只返回下一级服务器地址，由客户端继续查询。"),
        ("DNS 解析为什么要做本地缓存？",
         "避免每次都向上级服务器递归查询，降低延迟和上游负载。"),
    ]
    return [Card(front=f, back=b, tags=list(tags), source="mock") for f, b in raw]


def _respiration_cards() -> list[Card]:
    tags = ["biology"]
    raw = [
        ("有氧呼吸和无氧呼吸的 ATP 产量差多少？",
         "有氧呼吸一分子葡萄糖约产 30-32 个 ATP；无氧呼吸仅产 2 个 ATP。"),
        ("有氧呼吸的三个阶段依次是什么？",
         "糖酵解（细胞质基质）、柠檬酸循环（线粒体基质）、氧化磷酸化（线粒体内膜）。"),
        ("糖酵解发生在细胞的什么部位？",
         "细胞质基质，葡萄糖在此分解为丙酮酸，净产 2 个 ATP。"),
        ("柠檬酸循环发生在什么部位？",
         "线粒体基质，丙酮酸在此彻底分解，产生 CO₂ 和还原型辅酶。"),
        ("氧化磷酸化发生在什么部位？",
         "线粒体内膜，还原型辅酶经电子传递链传递电子，驱动 ATP 合成。"),
        ("线粒体为什么被称为细胞的动力工厂？",
         "因为它是有氧呼吸第二、三阶段的场所，细胞中绝大部分 ATP 在此产生。"),
        ("为什么糖酵解之后的阶段必须依赖线粒体？",
         "柠檬酸循环的酶系在线粒体基质、氧化磷酸化的电子传递链在线粒体内膜，"
         "这两个结构在细胞质基质里都不存在，所以糖酵解之后必须进入线粒体。"),
        ("有氧呼吸和无氧呼吸的第一阶段是否相同？",
         "完全相同，都是糖酵解，区别从丙酮酸之后的去路开始。"),
        ("无氧呼吸的产物是什么？",
         "乳酸或酒精，因生物种类而异，葡萄糖分解不彻底。"),
    ]
    return [Card(front=f, back=b, tags=list(tags), source="mock") for f, b in raw]


# 文件名 -> 预置卡片。键名与 tests/fixtures/ 里的样例文件名对应。
MOCK_CARDS: dict[str, list[Card]] = {
    "note-network.md": _network_cards(),
    "note-plain.txt": _respiration_cards(),
}
