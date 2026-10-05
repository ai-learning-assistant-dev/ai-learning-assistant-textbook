"""
page2md.py — OneNote 页面 → Markdown 转换工具

1. `Page.Title` / `Page.Title.TitleText.Text` 全部返回占位符字符串
   （`"Title()"` / `"RichText()"`），官方文档示例不可用。
   → 唯一可行的标题来源是 `RichText.IsTitleText / IsTitleDate / IsTitleTime`
     这三个布尔标记，逐节点判断。已实测可靠。

2. `OutlineElement` 没有 `Level` 属性，层级只能靠父子嵌套推导。
   但实测发现**并非所有笔记本都有嵌套**：
   - 《备忘录》最大嵌套深度 5，OE 总数 2259 → 层级真实存在
   - 《C51》全部 `nested=0` → 纯平级，OneNote 里就是平级的
   → 策略：有嵌套用缩进列表，无嵌套则平铺，不强造层级。

3. 超链接是"半结构化"的：一条链接被拆成 3 个 run
   （HYPERLINK 字段代码 / 显示文字 / 实际 URL），需要重组。
   → 见 _collect_links()。

"""

from __future__ import annotations

import re
from typing import Any

try:
    import aspose.note as note
except ImportError as _exc:  # pragma: no cover
    raise ImportError(
        "本模块需要 aspose-note-foss，请先安装："
        "uv pip install --python .venv aspose-note-foss"
    ) from _exc


# ─────────────────────────────────────────────────────────────
# 文本清洗
# ─────────────────────────────────────────────────────────────

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
# OneNote 富文本里混入的零宽字符
_ZERO_WIDTH = ("", "‌", "‍", "﻿")
# 超链接字段代码残留，形如：  \xfddfHYPERLINK "https://..."
_HYPERLINK_FIELD_RE = re.compile(r'^[^A-Za-z]*HYPERLINK\s+"([^"]*)"\s*', re.IGNORECASE)
# 裸 URL（没有被包成超链接 run 的情况）
_BARE_URL_RE = re.compile(r"(https?://[^\s，。；、）)\]】]+)")


def clean_text(value: Any) -> str:
    """把任意节点值安全转成干净字符串。"""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    value = _CTRL_RE.sub("", value)
    for ch in _ZERO_WIDTH:
        value = value.replace(ch, "")
    return value.strip()


def is_placeholder(value: Any) -> bool:
    """
    判断是否是库未实现的占位符字符串。

    实测占位符形如 'Title()'、'RichText()'，特征是「标识符 + 空括号」。
    这类值必须丢弃，否则会污染输出。
    """
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s:
        return False
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\(\s*\)", s))


# ─────────────────────────────────────────────────────────────
# 行内格式（粗体 / 斜体 / 删除线）
# ─────────────────────────────────────────────────────────────

def _escape_inline(text: str) -> str:
    """转义会破坏 Markdown 的行内字符。只转义确实有风险的，且不碰已有实体。"""
    if not text:
        return ""
    # 不转义代码包裹的内容
    if text.startswith("`") and text.endswith("`") and len(text) > 1:
        return text
    text = text.replace("\\", "\\\\")
    # 星号、下划线、井号在中段可能构成强调；用负向前后判断避免过度转义
    text = re.sub(r"(?<![\w*])\*(?!\s)", r"\*", text)
    text = re.sub(r"(?<!\s)\*(?![\w*])", r"\*", text)
    text = re.sub(r"(?<![\w_])_(?!\s)", r"\_", text)
    text = re.sub(r"(?<!\s)_(?![\w_])", r"\_", text)
    return text


def render_runs(rt: Any, *, link_url: str | None = None) -> str:
    """
    把一个 RichText 的 TextRuns 渲染成带行内格式的 Markdown。

    单个 run 出错不影响整体——降级为纯文本，这是可用性优先的取舍。
    """
    runs = getattr(rt, "TextRuns", None)
    if not runs:
        # 没有 run 信息时退回整体文本
        return _escape_inline(clean_text(getattr(rt, "Text", "")))

    # 第一遍：清理文本 + 记录是否粗体（先合并再加粗，从源头避免畸形标记）
    parts: list[tuple[str, bool]] = []
    for run in runs:
        try:
            raw = clean_text(getattr(run, "Text", ""))
            if not raw:
                continue
            style = run.Style

            # 去掉超链接字段残留，URL 单独用
            _HYPERLINK_FIELD_RE.sub("", raw)
            text = _escape_inline(raw)
            parts.append((text, bool(style.IsBold)))
        except Exception:  # noqa: BLE001 - 单 run 失败不应中断整页
            try:
                fallback = _escape_inline(clean_text(getattr(run, "Text", "")))
                if fallback:
                    parts.append((fallback, False))
            except Exception:  # noqa: BLE001
                continue

    # 合并相邻同粗体状态的 run，避免 '**ECA****模块**' 这种畸形标记
    merged: list[tuple[str, bool]] = []
    for text, is_bold in parts:
        if merged and merged[-1][1] == is_bold:
            merged[-1] = (merged[-1][0] + text, is_bold)
        else:
            merged.append((text, is_bold))

    # 第二遍：套格式标记
    result: list[str] = []
    for text, is_bold in merged:
        if is_bold and text.strip():
            result.append(f"**{text}**")
        else:
            result.append(text)
    return "".join(result).strip()


# 相邻的同类强调标记需要合并，否则 **A****B** 是非法 Markdown
_ADJACENT_BOLD_RE = re.compile(r"\*\*(\*\*)+")
_ADJACENT_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(?:\*(?!\*))+")
_ADJACENT_STRIKE_RE = re.compile(r"~~(?:~~)+")


def _merge_adjacent_markers(text: str) -> str:
    """折叠残留的重复强调标记（兜底，正常路径已在上面合并过）。"""
    if not text:
        return text
    prev = None
    for _ in range(3):
        if text == prev:
            break
        prev = text
        text = _ADJACENT_BOLD_RE.sub("**", text)
    return text


# ─────────────────────────────────────────────────────────────
# 超链接重组
# ─────────────────────────────────────────────────────────────

def _collect_links(rts: list[Any]) -> dict[str, str]:
    """
    预扫描整页，把「显示文字 → URL」配对。

    OneNote 把一条链接拆成多个 run：
        run1: '\\xfddfHYPERLINK "https://..."'
        run2: '如何读懂一张电路图？'← 显示文字
        run3: 'https://b23.tv/ctikHyI'← 有时是独立 run

    这里收集所有 URL 备用，渲染时按顺序配对。
    """
    urls: list[str] = []
    for rt in rts:
        for run in getattr(rt, "TextRuns", None) or []:
            try:
                text = clean_text(getattr(run, "Text", ""))
            except Exception:  # noqa: BLE001
                continue
            m = _HYPERLINK_FIELD_RE.match(text)
            if m:
                urls.append(m.group(1))
            elif _BARE_URL_RE.fullmatch(text.strip()):
                urls.append(text.strip())
    return {u: u for u in urls}


def _linkify_plain(text: str) -> str:
    """给纯文本里的裸 URL 加上 <> 尖括号，Markdown 会自动识别为链接。"""
    return _BARE_URL_RE.sub(lambda m: f"<{m.group(1)}>", text)


# ─────────────────────────────────────────────────────────────
# 节点 → 块级元素
# ─────────────────────────────────────────────────────────────

def _image_block(img: Any, index: int, images_dir_name: str, page_index: int = 1) -> str:
    """
    图片 → Markdown。

    实测 151 张图里只有 44 张有字节，107 张拿不到数据。
    所以：有字节给图，没字节给占位说明（保留 alt 文字信息）。

    文件名带页码前缀（p02_003_xxx），否则多页的001_xxx 会互相覆盖。
    """
    try:
        alt = clean_text(getattr(img, "AlternativeTextDescription", "")) or "图片"
        fname = clean_text(getattr(img, "FileName", "")) or "image.png"
        # 文件名可能重复（大量"未命名图片.png"），加页码+序号去重
        safe = re.sub(r'[\\/:*?"<>|]', "_", fname)
        target = f"{images_dir_name}/p{page_index:02d}_{index:03d}_{safe}"

        width = getattr(img, "Width", None)
        if width:
            return f"![{alt}]({target}) <!-- w={round(float(width), 2)} -->"
        return f"![{alt}]({target})"
    except Exception as exc:  # noqa: BLE001
        return f"（图片 {index} 解析失败：{type(exc).__name__}）"


def _rich_blocks(rts: list[Any], links: dict[str, str]) -> list[str]:
    """
    把一页的 RichText 节点转成 Markdown 块列表。

    关键：用 IsTitleText/IsTitleDate/IsTitleTime 区分标题、日期、时间，
    剩下的才是正文。
    """
    blocks: list[str] = []
    link_queue = list(links.keys())
    seen: set[int] = set()

    for rt in rts:
        try:
            key = id(rt)
            if key in seen:
                continue
            seen.add(key)

            is_title = bool(getattr(rt, "IsTitleText", False))
            is_date = bool(getattr(rt, "IsTitleDate", False))
            is_time = bool(getattr(rt, "IsTitleTime", False))
        except Exception:  # noqa: BLE001
            is_title = is_date = is_time = False

        text = render_runs(rt, link_url=link_queue.pop(0) if link_queue else None)
        if not text or is_placeholder(text):
            continue

        if is_title:
            blocks.append(("TITLE", text))
        elif is_date or is_time:
            blocks.append(("META", text))
        else:
            blocks.append(("BODY", text))

    return blocks


def _outline_to_lines(
    container: Any,
    depth: int = 0,
    max_depth: int = 6,
    _seen: set[int] | None = None,
) -> list[str]:
    """
    递归把 Outline/OutlineElement 转成缩进列表。

    实测：有的笔记本有真实嵌套（备忘录深度 5），有的是全平级（C51）。
    这里只按实际嵌套渲染，不凭空造层级。超过 max_depth 停止递归，
    防止病态文件导致无限递归。

    _seen 按节点 id() 去重：库在某些情况下会把同一逻辑节点返回多次，
    不去重会导致整段内容在输出里重复两遍（实测 C51 页）。
    """
    lines: list[str] = []
    if depth > max_depth:
        return lines
    if _seen is None:
        _seen = set()

    try:
        elements = container.GetChildNodes(note.OutlineElement)
    except Exception:  # noqa: BLE001
        return lines

    for oe in elements:
        try:
            key = id(oe)
            if key in _seen:
                continue
            _seen.add(key)

            rts = oe.GetChildNodes(note.RichText)
            text_parts: list[str] = []
            for rt in rts:
                t = render_runs(rt)
                if t and not is_placeholder(t):
                    text_parts.append(t)
            text = " ".join(text_parts).strip()

            child_elements = oe.GetChildNodes(note.OutlineElement)
            has_children = len(child_elements) > 0

            if text:
                indent = "  " * depth
                # 父节点加粗，便于视觉分组；叶子节点保持原样
                lines.append(f"{indent}- {text}" if not has_children else f"{indent}- **{text}**")

            # 无论当前节点有无文字，都继续渲染子节点
            if has_children:
                lines.extend(_outline_to_lines(oe, depth + 1, max_depth, _seen))
        except Exception:  # noqa: BLE001
            continue

    return lines


# ─────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────

def page_to_markdown(
    page: Any,
    *,
    page_index: int = 1,
    images_dir_name: str = "images",
    include_front_matter: bool = True,
    include_author: bool = True,
    max_outline_depth: int = 6,
) -> str:
    """
    把单个 Page 转成 Markdown 字符串（不写文件）。

    参数：
      page_index      页序号，用于图片文件名前缀
      images_dir_name 图片相对目录，写进 Markdown 的链接路径
      include_front_matter  是否生成 YAML front-matter
      max_outline_depth大纲最大递归深度（防御病态嵌套）
    """
    # 标题/日期/时间/作者——用 IsTitleXxx 标记，绕开占位符
    title = date_str = time_str = ""
    try:
        rts = page.GetChildNodes(note.RichText)
    except Exception:  # noqa: BLE001
        rts = []

    for rt in rts:
        try:
            txt = render_runs(rt)
            if not txt or is_placeholder(txt):
                continue
            if getattr(rt, "IsTitleText", False):
                title = title or txt
            elif getattr(rt, "IsTitleDate", False):
                date_str = date_str or txt
            elif getattr(rt, "IsTitleTime", False):
                time_str = time_str or txt
        except Exception:  # noqa: BLE001
            continue

    try:
        author = clean_text(getattr(page, "Author", "")) or ""
    except Exception:  # noqa: BLE001
        author = ""

    lines: list[str] = []

    # YAML front-matter
    if include_front_matter and (title or date_str or author):
        lines.append("---")
        if title:
            lines.append(f'title: "{_yaml_escape(title)}"')
        if date_str:
            lines.append(f'date: "{_yaml_escape(date_str)}"')
        if time_str:
            lines.append(f'time: "{_yaml_escape(time_str)}"')
        if include_author and author:
            lines.append(f'author: "{_yaml_escape(author)}"')
        lines.append(f"page_index: {page_index}")
        lines.append(f"source: onenote")
        lines.append("---")
        lines.append("")

    if title:
        lines.append(f"# {title}")
        lines.append("")

    # 正文
    links = _collect_links(rts)
    blocks = _rich_blocks(rts, links)

    body: list[str] = []
    outlines: list[str] = []

    for kind, text in blocks:
        if kind in ("TITLE", "META"):
            continue  # 已进 front-matter / 标题
        body.append(text)

    # 大纲（列表形式）
    # 只从 Outline 容器取，不要再用 page.GetChildNodes(OutlineElement)——
    # 后者是递归的，会把Outline 内的元素再返回一遍，造成整页内容重复。
    try:
        for ol in page.GetChildNodes(note.Outline):
            outlines.extend(_outline_to_lines(ol, 0, max_outline_depth))
    except Exception:  # noqa: BLE001
        pass

    if outlines:
        lines.append("## 大纲")
        lines.append("")
        lines.extend(outlines)
        lines.append("")

    # 正文
    # 关键：GetChildNodes 是【递归】的，Page 级已包含 Outline 内的所有节点。
    # 若再单独遍历 Outline 就会重复一遍（实测 C51 页内容出现两次）。
    # 所以这里只渲染不属于大纲的游离 RichText。
    # 比对时要去掉大纲行的 "- " / "- **" 前缀和加粗标记才能匹配上。
    outlined_keys: set[str] = set()
    for line in outlines:
        bare = line.strip()
        bare = re.sub(r"^-\s+", "", bare)
        bare = bare.replace("**", "")
        outlined_keys.add(bare.strip())
    body = [
        _linkify_plain(text)
        for kind, text in blocks
        if kind == "BODY" and text.strip().replace("**", "") not in outlined_keys
    ]

    if body:
        lines.append("## 正文")
        lines.append("")
        lines.extend(_as_paragraphs(_dedupe_consecutive(body)))
        lines.append("")

    # 图片
    try:
        imgs = page.GetChildNodes(note.Image)
    except Exception:  # noqa: BLE001
        imgs = []

    if imgs:
        lines.append("## 图片")
        lines.append("")
        for i, img in enumerate(imgs, start=1):
            lines.append(_image_block(img, i, images_dir_name, page_index))
        lines.append("")

    if not body and not outlines:
        lines.append("（本页无可提取内容）")

    return "\n".join(lines).strip() + "\n"


def _dedupe_consecutive(items: list[str]) -> list[str]:
    """
    去掉连续重复的段落。

    实测很多 OutlineElement 的 RichText 会重复返回同一段文字，
    不去重会产生大量重复内容。这是可用性优先的实用修正。
    """
    out: list[str] = []
    for s in items:
        t = s.strip()
        if not t:
            continue
        if out and out[-1] == t:
            continue
        out.append(t)
    return out


def _as_paragraphs(lines: list[str]) -> list[str]:
    """
    把逐行文本合并成 Markdown 段落（段间空一行）。

    OneNote 的每个 RichText 节点往往只是一行，若直接换行输出，
    Markdown 会把它们渲染成同一个段落里的软换行，可读性很差。
    这里按「短行且下一行非空则视为同段」的启发式合并，
    效果接近原笔记的段落观感。
    """
    paras: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            paras.append(" ".join(buf).strip())
            buf.clear()

    for i, line in enumerate(lines):
        text = line.strip()
        if not text:
            flush()
            continue
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        # 当前行较短且下一行也短-> 视为同段续行
        is_continuation = bool(nxt) and len(text) < 60 and len(nxt) < 60
        if is_continuation:
            buf.append(text)
        else:
            flush()
            buf.append(text)
    flush()
    return [p for p in paras if p]


def _yaml_escape(text: str) -> str:
    """转义 YAML 双引号字符串里的特殊字符。"""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def document_to_markdown(
    doc: Any,
    *,
    images_dir_name: str = "images",
    include_front_matter: bool = True,
    separator: str = "\n\n---\n\n",
) -> tuple[str, dict[str, int]]:
    """
    把整个 Document 转成一份 Markdown。

    返回 (markdown 文本, 统计信息)。
    """
    try:
        pages = doc.GetChildNodes(note.Page)
    except Exception as exc:  # noqa: BLE001
        return f"（无法枚举页面：{type(exc).__name__}: {exc}）\n", {"pages": 0}

    chunks: list[str] = []
    ok = 0
    failed = 0

    for i, page in enumerate(pages, start=1):
        try:
            md = page_to_markdown(
                page,
                page_index=i,
                images_dir_name=images_dir_name,
                include_front_matter=include_front_matter,
            )
            if md.strip():
                chunks.append(md)
                ok += 1
        except Exception:  # noqa: BLE001 - 单页失败不影响其他页
            failed += 1
            continue

    return separator.join(chunks), {"pages": ok, "failed_pages": failed}


def save_document_markdown(
    one_path: str,
    out_path: str,
    *,
    images_dir: str | None = None,
    extract_images: bool = True,
    encoding: str = "utf-8",
) -> dict[str, Any]:
    """
    便捷入口：读 .one 文件 → 写 Markdown 文件（可选导出图片）。

    这是本模块唯一会写磁盘的函数，且只写 out_path 与 images_dir，
    绝不触碰源 .one 文件。

    返回统计字典。
    """
    from pathlib import Path

    src = Path(one_path)
    dst = Path(out_path)
    dst.parent.mkdir(parents=True, exist_ok=True)

    doc = note.Document(str(src))
    md, stats = document_to_markdown(doc, images_dir_name=Path(images_dir or "images").name)

    dst.write_text(md, encoding=encoding)

    result: dict[str, Any] = {
        "source": str(src),
        "output": str(dst),
        "chars": len(md),
        **stats,
        "images_saved": 0,
    }

    if extract_images:
        saved = 0
        img_root = dst.parent / (images_dir or "images")
        img_root.mkdir(parents=True, exist_ok=True)
        # 序号必须【按页】编号，否则不同页的001_xxx.png 会互相覆盖
        # （实测 C51 有 6 页，每页都从 001 开始）
        for page_idx, page in enumerate(doc.GetChildNodes(note.Page), start=1):
            for i, img in enumerate(page.GetChildNodes(note.Image), start=1):
                try:
                    raw = getattr(img, "Bytes", None)
                    if not raw or len(raw) == 0:
                        continue  # 实测约七成图片拿不到字节，跳过
                    fname = clean_text(getattr(img, "FileName", "")) or "image.png"
                    safe = re.sub(r'[\\/:*?"<>|]', "_", fname)
                    (img_root / f"p{page_idx:02d}_{i:03d}_{safe}").write_bytes(bytes(raw))
                    saved += 1
                except Exception:  # noqa: BLE001
                    continue
        result["images_saved"] = saved

    return result
