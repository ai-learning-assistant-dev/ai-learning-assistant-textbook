"""笔记预处理：分两层，顺序不能颠倒。

文档层（提取之前调用）：
    strip_frontmatter()  剥离 YAML frontmatter，返回正文 + 其中声明的 tags
    规则提取器需要原始的 Markdown 结构（# 标题、- 列表、Q: / A: 行），
    所以文档层只做 frontmatter 剥离，绝不能提前转成 HTML。

字段层（提取之后、逐张卡调用）：
    to_field_html()      把某张卡的 front / back 转成可填入 Anki 字段的 HTML

关键修复（相对 Skill B 的问题）：
  1. 剥离 YAML frontmatter —— 否则 `title: xxx` 会被当成术语，产出 `What is title?` 这类垃圾卡。
  2. 把 Markdown 表格转成真正的 <table> —— 否则原始 `| a | b |` 管道符会原样进入卡片背面，
     在 Anki 里渲染成乱码。
"""

from __future__ import annotations

import re

_FRONTMATTER_RE = re.compile(r"\A\ufeff?---[ \t]*\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
_FRONTMATTER_TAGS_RE = re.compile(r"^\s*tags\s*:\s*(.+)$", re.M)

_RE_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_RE_CODE = re.compile(r"`([^`]+)`")
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_RE_ITALIC = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.S)
_RE_STRIKE = re.compile(r"~~(.+?)~~")


# ---------------------------------------------------------------------------
# 文档层
# ---------------------------------------------------------------------------

def strip_frontmatter(text: str) -> tuple[str, list[str]]:
    """剥离 YAML frontmatter。返回 (正文, frontmatter 中声明的 tags)。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return text, []
    block = m.group(0)
    body = text[m.end():]
    tags: list[str] = []
    tm = _FRONTMATTER_TAGS_RE.search(block)
    if tm:
        raw = tm.group(1).replace("[", " ").replace("]", " ")
        tags = [t.strip() for t in re.split(r"[,，]", raw) if t.strip()]
    return body, tags


# ---------------------------------------------------------------------------
# 字段层
# ---------------------------------------------------------------------------

def _row_cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _is_divider(cells: list[str]) -> bool:
    if not cells:
        return False
    return all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells if c)


def convert_tables(text: str) -> str:
    """把 Markdown 管道表格转成 HTML <table>。"""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        if "|" in lines[i] and _row_cells(lines[i]):
            block: list[str] = []
            j = i
            while j < len(lines) and "|" in lines[j]:
                block.append(lines[j])
                j += 1
            if len(block) >= 2 and _is_divider(_row_cells(block[1])):
                header = _row_cells(block[0])
                html = ["<table>", "<tr>" + "".join(f"<th>{c}</th>" for c in header) + "</tr>"]
                for raw in block[2:]:
                    row = _row_cells(raw)
                    if _is_divider(row):
                        continue
                    padded = (row + [""] * len(header))[: len(header)]
                    html.append("<tr>" + "".join(f"<td>{c}</td>" for c in padded) + "</tr>")
                html.append("</table>")
                out.extend(html)
                i = j
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out)


def inline_to_html(text: str) -> str:
    """行内 Markdown 标记转 HTML。"""
    text = _RE_IMAGE.sub("", text)
    text = _RE_LINK.sub(r"\1", text)
    text = _RE_CODE.sub(r"<code>\1</code>", text)
    text = _RE_BOLD.sub(r"<b>\1</b>", text)
    text = _RE_ITALIC.sub(r"<i>\1</i>", text)
    text = _RE_STRIKE.sub(r"<s>\1</s>", text)
    return text


def newlines_to_br(text: str) -> str:
    """剩余换行转 <br>，让 Anki 字段里的多行内容正常显示。

    HTML 块（如 <table>...</table>）内部不插 <br>，否则会得到
    `<table><br><tr>...` 这种被换行打散的表格结构。
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    depth = 0
    for raw in text.split("\n"):
        part = raw.strip()
        if not part:
            continue
        if depth == 0 and out:
            out.append("<br>")
        out.append(part)
        depth += part.count("<table>") - part.count("</table>")
        depth += part.count("<ul>") - part.count("</ul>")
        depth += part.count("<ol>") - part.count("</ol>")
        depth = max(depth, 0)
    return "".join(out)


def to_field_html(text: str, as_markdown: bool = True) -> str:
    """把单个卡片字段转成 Anki 可渲染的 HTML。"""
    if not text:
        return ""
    if as_markdown:
        text = convert_tables(text)
        text = inline_to_html(text)
    return newlines_to_br(text)
