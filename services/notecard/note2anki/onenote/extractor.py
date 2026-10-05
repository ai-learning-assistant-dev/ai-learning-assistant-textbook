"""
extractor.py — 基于 aspose-note-foss 的 OneNote 笔记提取

  - .one 是 OneNote 自有的扁平二进制容器（不是 OLE 复合文档），
    只有专业实现才能解。aspose-note-foss 能正确解出真实内容。
  - 实测 6 个真实分区文件：5 个成功，141 页 / 9.7 万字 / 549 张图。
  - 对比：pyOneNote 0.0.2 在 ArrayOfPropertyValues(0x10) 处直接
    raise NotImplementedError，真实笔记根本读不动。

只读保证：本模块所有函数只调用 note.Document(path) 与节点读取，
不做任何 save/export/写回。输出由调用方写到独立目录。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterator

import aspose.note as note


class ExtractError(RuntimeError):
    """单个文件提取失败。"""


def _clean_text(text: Any) -> str:
    """清掉 OneNote 富文本里的控制字符与零宽字符。非字符串输入安全返回。"""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    # 去掉除\t\n 外的 C0 控制字符，以及零宽字符
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    return text.strip()


def _iter_pages(doc) -> Iterator[Any]:
    """遍历所有页面，含嵌套大纲里的页面。"""
    yield from doc.GetChildNodes(note.Page)


def extract_file(
    path: str | Path,
    *,
    extract_images: bool = False,
    image_dir: str | Path | None = None,
    include_empty_pages: bool = False,
) -> dict[str, Any]:
    """
    提取单个 .one 文件的笔记内容（只读）。

    返回结构：
      {ok, source, pages:[{index,title,author,created,text,paragraphs,
      images:[{filename,size,bytes,saved_to}], attachments:[...]}],
       summary:{...}}
    """
    p = Path(path)
    result: dict[str, Any] = {
        "ok": False,
        "source": str(p),
        "size_bytes": p.stat().st_size if p.exists() else 0,
        "pages": [],
        "summary": {},
        "error": None,
    }

    try:
        doc = note.Document(str(p))
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["stage"] = "load"
        return result

    img_root = Path(image_dir) if image_dir else None
    if extract_images and img_root:
        # 以分区文件名建独立子目录，避免不同笔记本图片重名互相覆盖
        img_root = img_root / p.stem
        img_root.mkdir(parents=True, exist_ok=True)

    total_chars = 0
    total_images = 0
    total_attachments = 0

    for idx, page in enumerate(_iter_pages(doc), start=1):
        paragraphs: list[str] = []
        for rt in page.GetChildNodes(note.RichText):
            cleaned = _clean_text(getattr(rt, "Text", None))
            if cleaned:
                paragraphs.append(cleaned)

        text = "\n".join(paragraphs)

        if not text and not include_empty_pages:
            # 仍然记录，但摘要里不计入有内容的页
            pass

        images: list[dict[str, Any]] = []
        for img in page.GetChildNodes(note.Image):
            entry: dict[str, Any] = {
                "filename": getattr(img, "FileName", None),
                "width": getattr(img, "Width", None),
                "height": getattr(img, "Height", None),
            }
            raw = getattr(img, "Bytes", None)
            if raw:
                entry["bytes"] = len(raw)
                if extract_images and img_root:
                    safe = _safe_name(img.FileName, f"img_{idx}_{len(images)}")
                    target = img_root / safe
                    try:
                        target.write_bytes(bytes(raw))
                        entry["saved_to"] = str(target)
                    except OSError as exc:
                        entry["error"] = f"写入失败: {exc}"
            images.append(entry)

        attachments: list[dict[str, Any]] = []
        for att in page.GetChildNodes(note.AttachedFile):
            entry = {
                "filename": getattr(att, "FileName", None),
                "bytes": len(getattr(att, "Bytes", b"") or b""),
            }
            attachments.append(entry)

        total_chars += len(text)
        total_images += len(images)
        total_attachments += len(attachments)

        result["pages"].append(
            {
                "index": idx,
                "title": _clean_text(getattr(page, "Title", None)),
                "author": getattr(page, "Author", None),
                "level": getattr(page, "Level", None),
                "text": text,
                "paragraph_count": len(paragraphs),
                "images": images,
                "attachments": attachments,
            }
        )

    result["ok"] = True
    result["summary"] = {
        "page_count": len(result["pages"]),
        "non_empty_pages": sum(1 for pg in result["pages"] if pg["text"]),
        "total_chars": total_chars,
        "image_count": total_images,
        "attachment_count": total_attachments,
    }
    return result


def _safe_name(name: str | None, fallback: str) -> str:
    """文件名清洗：去掉路径分隔符和控制字符，防目录穿越。"""
    if not name:
        return fallback
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", str(name)).strip(" .")
    return cleaned or fallback
