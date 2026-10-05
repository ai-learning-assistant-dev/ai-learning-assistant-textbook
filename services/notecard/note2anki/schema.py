"""BasicCard 数据模型与校验层。

    校验不做静默丢弃，也不做静默放行。所有可疑之处变成结构化的 issue 挂在卡片上，
    连同校验报告一起交给界面，由用户决定改、删还是保留。

    error   结构性错误，必须修掉才能导出（字段缺失、类型错误）
    warning 质量可疑，可以保留，但界面会标出来提示用户
    
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

MAX_FRONT = 120
MAX_BACK = 600
MIN_FRONT = 4
MIN_BACK = 2

_Q_WORDS_ZH = ("什么", "为什么", "为何", "如何", "怎样", "怎么", "哪些", "哪些", "谁", "何时", "是否", "吗", "列举", "解释", "区别", "关系", "指的是", "对应")
_Q_WORDS_EN = ("what", "why", "how", "which", "who", "when", "where", "explain", "define", "describe", "difference")

_RE_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.M)
_RE_HEADING = re.compile(r"^\s*#{1,6}\s+\S", re.M)
_RE_FENCE = re.compile(r"```")
_RE_BOLD_RESIDUE = re.compile(r"\*\*")
_RE_PURE_NUM = re.compile(r"^[\d\s.:]+$")
_RE_WS = re.compile(r"\s+")

# 是非题：答案是「是的 / 否」这类退化回答，正面提供的回忆线索太弱，
# 背下来只能记住一个布尔值，记不住真正的知识点。
_RE_YESNO_Q = re.compile(
    r"(吗\s*[？?]\s*$|是不是|有没有|能否|^(?:is|are|was|were|do|does|did|can|could|"
    r"will|would|should|has|have|had)\b.*\?$)",
    re.IGNORECASE,
)
_RE_YESNO_A = re.compile(r"^(?:是的|不是|对[。，,、]|不对|否|当然|没错|yes|no)\b", re.IGNORECASE)


def new_id() -> str:
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# 卡片模型
# ---------------------------------------------------------------------------

@dataclass
class Card:
    """只保留 Basic 类型：正面问题 + 反面答案。"""

    id: str = field(default_factory=new_id)
    front: str = ""
    back: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "unknown"
    issues: list[dict] = field(default_factory=list)

    @property
    def has_error(self) -> bool:
        return any(i["level"] == "error" for i in self.issues)

    @property
    def has_warning(self) -> bool:
        return any(i["level"] == "warning" for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "front": self.front,
            "back": self.back,
            "tags": list(self.tags),
            "source": self.source,
            "issues": list(self.issues),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Card":
        return cls(
            id=str(d.get("id") or new_id()),
            front=str(d.get("front") or ""),
            back=str(d.get("back") or ""),
            tags=normalize_tags(d.get("tags")) or [],
            source=str(d.get("source") or "unknown"),
            issues=list(d.get("issues") or []),
        )


# ---------------------------------------------------------------------------
# 归一化
# ---------------------------------------------------------------------------

def normalize_tags(value) -> list[str] | None:
    """把各种写法的 tags 归一化成 list[str]。返回 None 表示类型无法接受。"""
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[,，;；\s]+", value)
    elif isinstance(value, (list, tuple, set)):
        parts: list[str] = []
        for v in value:
            if not isinstance(v, (str, int, float)):
                return None
            parts.extend(re.split(r"[,，;；\s]+", str(v)))
    else:
        return None
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        p = p.strip().lstrip("#")
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _norm(text: str) -> str:
    return _RE_WS.sub("", str(text)).lower()


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", str(text))


def _looks_like_question(front: str) -> bool:
    f = front.strip()
    if f.endswith("?") or f.endswith("？"):
        return True
    low = f.lower()
    return any(w in low for w in _Q_WORDS_EN) or any(w in f for w in _Q_WORDS_ZH)


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------

def _issue(level: str, code: str, message: str) -> dict:
    return {"level": level, "code": code, "message": message}


def validate_card(card: Card) -> list[dict]:
    """校验单张卡，返回 issue 列表。"""
    issues: list[dict] = []

    # --- 结构性错误 ---
    if not isinstance(card.front, str) or not card.front.strip():
        issues.append(_issue("error", "empty_front", "正面为空，这张卡无法导入 Anki"))
    if not isinstance(card.back, str) or not card.back.strip():
        issues.append(_issue("error", "empty_back", "反面为空，这张卡无法导入 Anki"))

    front = card.front.strip()
    back = card.back.strip()

    # --- 长度 ---
    if len(front) > MAX_FRONT:
        issues.append(_issue("warning", "front_too_long", f"正面 {len(front)} 字，超过建议的 {MAX_FRONT} 字，记忆负担偏重"))
    if len(_strip_tags(back)) > MAX_BACK:
        issues.append(_issue("warning", "back_too_long", f"反面 {len(_strip_tags(back))} 字，超过建议的 {MAX_BACK} 字，建议拆分"))

    # --- 问句形态 ---
    if front and not _looks_like_question(front):
        issues.append(_issue("warning", "front_not_question", "正面不像一个问句，检查一下是不是提取模板硬套出来的"))
    if front and len(front) < MIN_FRONT:
        issues.append(_issue("warning", "front_too_short", "正面过短，缺少可回忆的线索"))
    if front and _RE_PURE_NUM.match(front.strip("？?。. ")) :
        issues.append(_issue("warning", "front_is_number", "正面几乎是纯数字，这类卡背下来没有意义"))
    if front and _RE_YESNO_Q.search(front) and _RE_YESNO_A.match(back):
        issues.append(_issue("warning", "yes_no_card", "是非题卡：答案退化成「是/否」，回忆线索太弱，建议改成「X 的特点是什么？」"))

    # --- 残留 Markdown（说明清洗没做干净）---
    if _RE_TABLE_ROW.search(back):
        issues.append(_issue("warning", "md_table_residue", "反面残留 Markdown 表格管道符，在 Anki 里会显示成乱码"))
    if _RE_HEADING.search(back) or _RE_HEADING.search(front):
        issues.append(_issue("warning", "md_heading_residue", "残留 Markdown 标题符号 #"))
    if _RE_FENCE.search(back):
        issues.append(_issue("warning", "md_fence_residue", "反面残留代码块围栏 ```"))
    if _RE_BOLD_RESIDUE.search(back):
        issues.append(_issue("warning", "md_bold_residue", "反面残留 ** 粗体标记，未转成 <b>"))

    # --- 标签 ---
    for t in card.tags:
        if re.search(r"\s", t):
            issues.append(_issue("warning", "tag_has_space", f"标签「{t}」含空格，Anki 会把它切成两个标签"))
            break

    return issues


def _cross_check(cards: list[Card]) -> None:
    """跨卡片检查：完全重复、语义包含。就地给卡片追加 issue。"""
    seen: dict[str, str] = {}
    for c in cards:
        key = _norm(_strip_tags(c.front))
        if not key:
            continue
        if key in seen:
            c.issues.append(_issue("warning", "duplicate_front", f"正面与另一张卡（id={seen[key]}）重复"))
        else:
            seen[key] = c.id

    # 语义包含：A 的反面被 B 的反面完整包含，且长度差明显 -> A 大概率是 B 的子集
    texts = [(c, _norm(_strip_tags(c.back))) for c in cards]
    for i, (ca, ta) in enumerate(texts):
        if len(ta) < 20:
            continue
        for j, (cb, tb) in enumerate(texts):
            if i == j or len(tb) <= len(ta) + 15:
                continue
            if ta in tb:
                ca.issues.append(
                    _issue("warning", "back_contained", f"反面内容被另一张卡（id={cb.id}）完整包含，可能是冗余卡")
                )
                break


def validate(cards: list[Card]) -> tuple[list[Card], dict]:
    """校验一批卡片。返回 (带上 issues 的卡片, 汇总报告)。"""
    for c in cards:
        c.issues = validate_card(c)
    _cross_check(cards)

    errors = sum(1 for c in cards for i in c.issues if i["level"] == "error")
    warnings = sum(1 for c in cards for i in c.issues if i["level"] == "warning")
    by_code: dict[str, int] = {}
    for c in cards:
        for i in c.issues:
            by_code[i["code"]] = by_code.get(i["code"], 0) + 1

    report = {
        "total": len(cards),
        "clean": sum(1 for c in cards if not c.issues),
        "error": errors,
        "warning": warnings,
        "by_code": by_code,
        "blocking": errors > 0,
    }
    return cards, report
