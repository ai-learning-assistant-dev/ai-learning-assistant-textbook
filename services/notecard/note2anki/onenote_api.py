"""OneNote 源适配层：目录浏览 / 扫描分区树 / 列页 / 渲染 Markdown。

  - onenote/          只负责「.one 二进制 → 结构化数据 / Markdown」的转换
  - onenote_api.py    负责「一个路径 → 一棵可交互的树」，以及解析结果的缓存

只读保证：本模块全程只 open(..., "rb") 读 16 字节魔数或交给 aspose 读文档，
不写任何 OneNote 源文件；onenote/ 里会写盘的两个函数（parse_all、
save_document_markdown）在这里一律不调用。

"""

from __future__ import annotations

import re
import string
import time
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

import aspose.note as note

from .onenote import discover_one_files, is_one_file
from .onenote.page2md import clean_text, is_placeholder, page_to_markdown

# 分区文件名形如「C51 (于 26-09-27 - 2).one」，尾巴是 OneNote 自动加的时间戳
_SECTION_SUFFIX_RE = re.compile(r"\s*[（(][^）)]*[）)]\s*$")


def _in_recycle_bin(path: Path) -> bool:
    """回收站判断。

    目录名是 OneNote_RecycleBin，用等值判断（testdsh 原实现那样）会漏掉，
    必须按子串匹配。实测不过滤的话「OneNote_DeletedPages」会混进分区树。
    """
    return any("RecycleBin" in part for part in path.parts)

# 解析过的分区：key 是绝对路径，value 是 _Section
# 一个 40MB 的 .one 解析要十几秒，不缓存的话点一次页面就等一次
_CACHE: OrderedDict[str, "_Section"] = OrderedDict()
_CACHE_MAX = 3

# 哪些文件必须靠容错补丁才能解析。独立于 _CACHE 记录：
# 分区被 LRU 挤掉后重新解析时补丁已经装好，会「悄悄成功」，
# 不记住的话同一个文件这次标降级、下次不标。
_DEGRADED: dict[str, bool] = {}


class OneNoteError(RuntimeError):
    """路径不存在 / 不是 .one / 解析失败。"""


class _Section:
    """一个 .one 分区的解析结果。doc 与 pages 都持有在内存里，供渲染复用。"""

    def __init__(self, doc: Any, pages: list[Any], degraded: bool = False) -> None:
        self.doc = doc
        self.pages = pages
        self.meta: list[dict[str, Any]] | None = None
        self.size_bytes = 0
        self.load_seconds = 0.0
        # True 表示这一份是靠容错补丁解析出来的，内容可能不完整
        self.degraded = degraded

    def page(self, index: int) -> Any:
        if not 1 <= index <= len(self.pages):
            raise OneNoteError(f"页序号越界：{index}（本分区共 {len(self.pages)} 页）")
        return self.pages[index - 1]

    def page_meta(self) -> list[dict[str, Any]]:
        if self.meta is None:
            self.meta = [
                {
                    "index": i,
                    "title": _page_title(page) or f"第 {i} 页",
                    "chars": _page_chars(page),
                    "images": _count_nodes(page, note.Image),
                }
                for i, page in enumerate(self.pages, start=1)
            ]
        return self.meta


def _resolve(raw: str) -> Path:
    p = Path(str(raw or "").strip().strip('"')).expanduser()
    if not str(raw or "").strip():
        raise OneNoteError("请先填写路径")
    if not p.exists():
        raise OneNoteError(f"路径不存在：{p}")
    return p


def _section_name(path: Path) -> str:
    return _SECTION_SUFFIX_RE.sub("", path.stem).strip() or path.stem


def _count_nodes(node: Any, node_type: Any) -> int:
    try:
        return len(node.GetChildNodes(node_type))
    except Exception:  # noqa: BLE001
        return 0


def _page_title(page: Any) -> str:
    """取页面标题。

    实测 Page.Title 返回占位符字符串，只能靠 RichText.IsTitleText 判断
    （onenote/page2md.py 顶部注释里有完整说明）。
    """
    try:
        for rt in page.GetChildNodes(note.RichText):
            if not getattr(rt, "IsTitleText", False):
                continue
            text = clean_text(getattr(rt, "Text", ""))
            if text and not is_placeholder(text):
                return text
    except Exception:  # noqa: BLE001
        pass
    return ""


def _page_chars(page: Any) -> int:
    try:
        return sum(
            len(clean_text(getattr(rt, "Text", "")))
            for rt in page.GetChildNodes(note.RichText)
        )
    except Exception:  # noqa: BLE001
        return 0


# ─────────────────────────────────────────────────────────────
# 缓存
# ─────────────────────────────────────────────────────────────

_TOLERANT_INSTALLED = False


def _install_tolerant_parser() -> None:
    """给 aspose 的 _parse_property_set 打「越界补零」补丁（只装一次）。

    实测：库在 read_value 里越界读 4 字节会抛 struct.error，且它自带的兜底
    只在「属性类型被覆盖过时」生效，等于没有。典型受害者是
    `编程 (于 26-09-22).one`（27.6MB）——打了补丁后能正常解出 6 页。

    做法不是丢弃整块属性，而是把缓冲区补零后重试：越界那次读到零值，
    同一组里其它属性仍然保真。实测对其余 6 个正常分区页数完全一致，无副作用。

    补丁一旦装上就是进程级的，所以只在【严格解析失败后】才装，
    正常文件走的仍是库的原始路径。
    """
    global _TOLERANT_INSTALLED
    if _TOLERANT_INSTALLED:
        return
    try:
        from aspose.note._internal.onestore import parser as _p
    except Exception:  # noqa: BLE001 - 库结构变了就放弃补丁，不影响主流程
        _TOLERANT_INSTALLED = True
        return

    if getattr(_p, "_n2a_tolerant", False):
        _TOLERANT_INSTALLED = True
        return

    original = _p._parse_property_set

    def tolerant(data: Any, offset: int, state: Any) -> Any:
        for pad in (0, 64, 4096):
            try:
                return original(data if pad == 0 else bytes(data) + b"\x00" * pad,
                                offset, state)
            except Exception:  # noqa: BLE001
                continue
        return {}, [], max(0, len(data) - offset)

    _p._parse_property_set = tolerant
    _p._n2a_tolerant = True
    _TOLERANT_INSTALLED = True


def _load(path: Path) -> _Section:
    key = str(path.resolve()).lower()
    hit = _CACHE.get(key)
    if hit is not None:
        _CACHE.move_to_end(key)
        return hit

    t0 = time.time()
    degraded = _DEGRADED.get(key, False)
    try:
        doc = note.Document(str(path))
        pages = list(doc.GetChildNodes(note.Page))
    except Exception as first:  # noqa: BLE001
        # 严格解析失败：装容错补丁再试一次
        _install_tolerant_parser()
        try:
            doc = note.Document(str(path))
            pages = list(doc.GetChildNodes(note.Page))
            degraded = True
            _DEGRADED[key] = True
        except Exception as exc:  # noqa: BLE001
            raise OneNoteError(f"{type(exc).__name__}: {exc}") from first

    sec = _Section(doc, pages, degraded)
    sec.size_bytes = path.stat().st_size
    sec.load_seconds = round(time.time() - t0, 1)

    _CACHE[key] = sec
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return sec


# ─────────────────────────────────────────────────────────────
# 对外接口
# ─────────────────────────────────────────────────────────────

def browse(raw: str = "") -> dict[str, Any]:
    """列出一个目录下的子目录，供前端逐层点选到笔记本目录。

    空路径时给出盘符列表，作为浏览的起点。
    """
    if not str(raw or "").strip():
        drives = []
        for letter in string.ascii_uppercase:
            d = Path(f"{letter}:/")
            if d.exists():
                drives.append({"name": f"{letter}:", "path": str(d), "sections": None})
        return {"path": "", "parent": None, "dirs": drives}

    p = _resolve(raw)
    if p.is_file():
        p = p.parent

    dirs: list[dict[str, Any]] = []
    try:
        children = sorted((c for c in p.iterdir() if c.is_dir()),
                          key=lambda c: c.name.lower())
    except OSError as exc:
        raise OneNoteError(f"无法读取目录：{p}（{exc}）") from exc

    for child in children:
        sections = None
        if not _in_recycle_bin(child):
            try:
                sections = sum(1 for f in child.rglob("*.one") if not _in_recycle_bin(f))
            except OSError:
                sections = None
        dirs.append({"name": child.name, "path": str(child), "sections": sections})

    parent = p.parent
    return {
        "path": str(p),
        "parent": str(parent) if parent != p else None,
        "dirs": dirs,
        "one_files": sum(1 for f in p.glob("*.one") if f.is_file()),
    }


def _section_node(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
        size, mtime = stat.st_size, stat.st_mtime
    except OSError:
        size, mtime = 0, 0.0
    return {
        "type": "section",
        "name": _section_name(path),
        "path": str(path),
        "size_mb": round(size / 1048576, 1),
        "modified": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M") if mtime else "",
        "valid": is_one_file(path),
    }


def scan(raw: str, include_recycle: bool = False) -> dict[str, Any]:
    """把用户给的路径展开成「笔记本 → 分区组 → 分区」树。

    只做文件枚举与 16 字节魔数校验，不解析内容，所以很快。
    真正的解析推迟到用户点开某个分区（list_pages）时才发生。
    """
    root = _resolve(raw)

    files = discover_one_files(root, True)
    if not include_recycle:
        files = [f for f in files if not _in_recycle_bin(f)]
    if not files:
        raise OneNoteError(f"该路径下没有发现 .one 分区文件：{root}")

    notebooks: dict[str, dict[str, Any]] = {}
    for path in files:
        if root.is_file():
            # 直接指向单个 .one：笔记本名取父目录
            nb_name, groups, nb_path = root.parent.name, [], str(root.parent)
        else:
            parts = path.relative_to(root).parts[:-1]
            nb_name = parts[0] if parts else root.name
            groups = list(parts[1:])
            nb_path = str(root / parts[0]) if parts else str(root)

        nb = notebooks.setdefault(
            nb_name,
            {"type": "notebook", "name": nb_name, "path": nb_path, "children": []},
        )
        node = nb["children"]
        for g in groups:
            found = next((c for c in node if c["type"] == "group" and c["name"] == g), None)
            if found is None:
                found = {"type": "group", "name": g, "path": "", "children": []}
                node.append(found)
            node = found["children"]
        node.append(_section_node(path))

    def sort_children(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nodes.sort(key=lambda n: (n["type"] != "group", n["name"].lower()))
        for n in nodes:
            if n["type"] == "group":
                sort_children(n["children"])
        return nodes

    for nb in notebooks.values():
        sort_children(nb["children"])
        nb["sections"] = _count_sections(nb)

    result = sorted(notebooks.values(), key=lambda n: n["name"].lower())
    return {
        "root": str(root),
        "notebooks": result,
        "section_count": sum(nb["sections"] for nb in result),
    }


def _count_sections(node: dict[str, Any]) -> int:
    if node["type"] == "section":
        return 1
    return sum(_count_sections(c) for c in node.get("children", []))


def list_pages(raw: str) -> dict[str, Any]:
    """解析一个分区，返回页清单（标题 / 字符数 / 图片数）。"""
    path = _resolve(raw)
    if not is_one_file(path):
        raise OneNoteError(f"不是有效的 .one 文件（容器魔数不匹配）：{path.name}")
    sec = _load(path)
    return {
        "section": str(path),
        "name": _section_name(path),
        "size_mb": round(sec.size_bytes / 1048576, 1),
        "load_seconds": sec.load_seconds,
        "degraded": sec.degraded,
        "pages": sec.page_meta(),
    }


def render_page(raw: str, index: int) -> dict[str, Any]:
    """渲染单页 Markdown。"""
    path = _resolve(raw)
    sec = _load(path)
    page = sec.page(index)
    try:
        md = page_to_markdown(page, page_index=index, images_dir_name="images")
    except Exception as exc:  # noqa: BLE001
        raise OneNoteError(f"第 {index} 页渲染失败：{type(exc).__name__}: {exc}") from exc

    meta = sec.page_meta()[index - 1]
    return {
        "markdown": md,
        "title": meta["title"],
        "source": f"{_section_name(path)} / {meta['title']}",
        "filename": _safe_filename(f"{_section_name(path)}-{meta['title']}.md"),
        "chars": len(md),
        "images": meta["images"],
        "degraded": sec.degraded,
    }


def render_section(raw: str) -> dict[str, Any]:
    """渲染整个分区：所有页的 Markdown 用分隔线拼成一份。"""
    path = _resolve(raw)
    sec = _load(path)
    metas = sec.page_meta()

    chunks: list[str] = []
    failed = 0
    for meta in metas:
        try:
            chunks.append(
                page_to_markdown(sec.page(meta["index"]), page_index=meta["index"],
                                 images_dir_name="images")
            )
        except Exception:  # noqa: BLE001 - 单页失败不拖垮整分区
            failed += 1

    if not chunks:
        raise OneNoteError(f"分区内没有可渲染的页面：{path.name}")

    md = "\n\n---\n\n".join(chunks)
    name = _section_name(path)
    return {
        "markdown": md,
        "title": name,
        "source": f"{name}（整分区 {len(chunks)} 页）",
        "filename": _safe_filename(f"{name}.md"),
        "chars": len(md),
        "page_count": len(chunks),
        "failed_pages": failed,
        "degraded": sec.degraded,
    }


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip(" .")[:80] or "onenote.md"
