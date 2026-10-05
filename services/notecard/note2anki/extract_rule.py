"""规则提取器 —— 无 LLM 时的兜底路径。

  1. 章节汇总卡（「X 的关键要点有哪些？」「请解释：X」）默认关闭。
     实测它们是重复卡的最大来源——与同章节拆出的细粒度定义卡高度重叠。
     需要时可通过 include_section_cards=True 打开。

  2. 术语过短或纯数字时，问句里补上所属章节作为上下文。
     实测 `80：HTTP 明文网页服务` 被硬套成 `What is 80?`，
     补上下文后变成 `什么是 80（常见端口）？`。

  3. 通用词黑名单扩充（概念/定义/示例/注意/小结 等），减少伪术语。

  4. 字段统一走 to_field_html，表格转 <table>、粗体转 <b>，不再把管道符原样塞进背面。
  
"""

from __future__ import annotations

import re

from .preprocess import strip_frontmatter, to_field_html
from .schema import Card

# ---------------------------------------------------------------------------
# Markdown 解析
# ---------------------------------------------------------------------------

_RE_HEADING = re.compile(r"^(#{1,6})\s+(.+)$")
_RE_DEFINITION = [
    re.compile(r"^[*\-•]?\s*\*{0,2}(.+?)\*{0,2}\s*[：:]\s*(.+)$"),
    re.compile(r"^[*\-•]?\s*\*{0,2}(.+?)\*{0,2}\s*[—–]\s*(.+)$"),
]
_RE_QA_Q = re.compile(r"^[QqＱ问]\s*[：:.]\s*(.+)$")
_RE_QA_A = re.compile(r"^[AaＡ答]\s*[：:.]\s*(.+)$")
_RE_LIST_ITEM = re.compile(r"^[\-*•]\s+(.+)$")
_RE_ORDERED_ITEM = re.compile(r"^\d+[.)]\s+(.+)$")

_GENERIC_LABELS = frozenset({
    "场所", "条件", "原料", "产物", "时间", "地点", "方法", "目的", "特点",
    "结果", "步骤", "功能", "过程", "对象", "类型", "分类", "来源", "用途", "意义",
    "概念", "定义", "例子", "示例", "注意", "说明", "总结", "小结", "备注",
    "参考", "前言", "附录", "引言", "背景", "概述", "简介", "要点", "问题",
})


def _is_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _needs_context(term: str) -> bool:
    """术语过短或偏数字时，问句需要补上下文才可读。"""
    if len(term) <= 3:
        return True
    return bool(re.fullmatch(r"[\d\s.:%-]+", term))


def _make_def_question(term: str, context: str = "") -> str:
    # 术语是英文但上下文是中文时也要走中文模板，否则会得到
    # 「What is TCP (TCP 与 UDP 的区别)?」这种中英混排的怪句子。
    zh = _is_chinese(f"{term} {context}")
    if context and _needs_context(term):
        return f"什么是 {term}（{context}）？" if zh else f"What is {term} ({context})?"
    return f"什么是{term}？" if zh else f"What is {term}?"


def parse_markdown(text: str) -> dict:
    """把 Markdown 解析成嵌套 section 树。"""
    root: dict = {"title": "", "level": 0, "content": [], "subsections": []}
    stack = [root]
    for line in text.split("\n"):
        hdr = _RE_HEADING.match(line)
        if hdr:
            level = len(hdr.group(1))
            node = {"title": hdr.group(2).strip(), "level": level, "content": [], "subsections": []}
            while len(stack) > 1 and stack[-1]["level"] >= level:
                stack.pop()
            stack[-1]["subsections"].append(node)
            stack.append(node)
        else:
            stripped = line.strip()
            if stripped:
                stack[-1]["content"].append(stripped)
    return root


# ---------------------------------------------------------------------------
# 抽取器
# ---------------------------------------------------------------------------

def _clean_term(term: str) -> str:
    return term.strip().strip("*").strip("_").strip("`").strip()


def extract_definitions(text: str, context: str = "") -> list[Card]:
    cards: list[Card] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        for pat in _RE_DEFINITION:
            m = pat.match(line)
            if m:
                term = _clean_term(m.group(1))
                defn = m.group(2).strip()
                if len(term) > 1 and len(defn) > 5 and term not in _GENERIC_LABELS:
                    cards.append(Card(
                        front=_make_def_question(term, context),
                        back=defn,
                        tags=["definition"],
                        source="rule",
                    ))
                break
    return cards


def extract_qa_pairs(text: str) -> list[Card]:
    cards: list[Card] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        qm = _RE_QA_Q.match(lines[i].strip())
        if qm and i + 1 < len(lines):
            am = _RE_QA_A.match(lines[i + 1].strip())
            if am:
                cards.append(Card(
                    front=qm.group(1).strip(),
                    back=am.group(1).strip(),
                    tags=["qa"],
                    source="rule",
                ))
                i += 2
                continue
        i += 1
    return cards


def extract_list_items(section: dict, include_summary: bool) -> list[Card]:
    cards: list[Card] = []
    title = section.get("title", "")
    items: list[str] = []
    for line in section.get("content", []):
        m = _RE_LIST_ITEM.match(line) or _RE_ORDERED_ITEM.match(line)
        if m:
            items.append(m.group(1).strip())

    if include_summary and title and len(items) >= 2:
        zh = _is_chinese(title)
        front = f"{title}的关键要点有哪些？" if zh else f"What are the key points of {title}?"
        back = "<ul>" + "".join(f"<li>{it}</li>" for it in items) + "</ul>"
        cards.append(Card(front=front, back=back, tags=["list"], source="rule"))

    for item in items:
        sep = "：" if "：" in item else (":" if ":" in item else None)
        if not sep:
            continue
        term, defn = item.split(sep, 1)
        term = _clean_term(term)
        defn = defn.strip()
        if len(term) > 1 and len(defn) > 5 and term not in _GENERIC_LABELS:
            cards.append(Card(
                front=_make_def_question(term, title),
                back=defn,
                tags=["definition"],
                source="rule",
            ))
    return cards


def extract_from_paragraphs(section: dict) -> list[Card]:
    """章节标题 + 段落 -> 概念卡。默认关闭（重复来源之一）。"""
    title = section.get("title", "")
    paras = [
        line for line in section.get("content", [])
        if not _RE_LIST_ITEM.match(line)
        and not _RE_ORDERED_ITEM.match(line)
        and not _RE_QA_Q.match(line)
        and not _RE_QA_A.match(line)
    ]
    if not title or not paras:
        return []
    # 必须用换行拼接：用空格会把表格的多行压成一行，
    # 后面的 convert_tables 就再也认不出分隔线，管道符会原样漏进卡片背面。
    content = "\n".join(paras)
    if len(content) <= 20:
        return []
    zh = _is_chinese(title)
    front = f"请解释：{title}" if zh else f"Explain: {title}"
    return [Card(front=front, back=content, tags=["concept"], source="rule")]


def _walk(section: dict, include_section_cards: bool) -> list[Card]:
    cards: list[Card] = []
    full_text = "\n".join(section.get("content", []))
    title = section.get("title", "")
    cards.extend(extract_definitions(full_text, context=title))
    cards.extend(extract_qa_pairs(full_text))
    cards.extend(extract_list_items(section, include_summary=include_section_cards))
    if include_section_cards:
        cards.extend(extract_from_paragraphs(section))
    for sub in section.get("subsections", []):
        cards.extend(_walk(sub, include_section_cards))
    return cards


def _dedupe(cards: list[Card]) -> list[Card]:
    seen: set[str] = set()
    out: list[Card] = []
    for c in cards:
        key = re.sub(r"\s+", "", c.front).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def extract_cards(
    text: str,
    *,
    include_section_cards: bool = False,
    extra_tags: list[str] | None = None,
    as_markdown: bool = True,
) -> list[Card]:
    """规则提取入口。

    include_section_cards=True 时额外产出章节汇总卡（默认关闭，实测重复率高）。
    extra_tags 通常传入 YAML frontmatter 里声明的 tags。
    """
    body, fm_tags = strip_frontmatter(text)
    root = parse_markdown(body)

    # _walk 已经递归覆盖了整棵树（含 root.content，也就是首个标题之前的内容），
    # 不能再对全文重复跑一次抽取器：那会生成「带上下文 / 不带上下文」两套问句，
    # 字面去重挡不住，于是每张卡都出现两遍。
    cards = _dedupe(_walk(root, include_section_cards))

    merged = list(extra_tags or []) + list(fm_tags)
    for c in cards:
        c.front = to_field_html(c.front, as_markdown)
        c.back = to_field_html(c.back, as_markdown)
        if merged:
            c.tags = list(dict.fromkeys(list(c.tags) + merged))
    return cards
