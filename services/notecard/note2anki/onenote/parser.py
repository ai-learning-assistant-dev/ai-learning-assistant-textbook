"""
parser.py — 调度层：按配置批量提取笔记

只读保证：这里只读 .one 源文件，所有写操作都发生在 output_dir，
绝不会回写 OneNote 原始数据。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import AppConfig, ParserConfig
from .extractor import extract_file

# OneNote 的 16 字节容器魔数，用于快速跳过非 .one 文件
ONE_MAGIC = bytes.fromhex("e4525c7b8cd8a74daeb15378d02996d3")
ONETOC2_MAGIC = bytes.fromhex("a12fff43d9ef764c9ee210ea5722765f")


def is_one_file(path: str | Path) -> bool:
    """只读前 16 字节判断是否 .one / .onetoc2。"""
    try:
        with open(path, "rb") as fh:
            return fh.read(16) in (ONE_MAGIC, ONETOC2_MAGIC)
    except OSError:
        return False


def _to_markdown(file_result: dict[str, Any]) -> str:
    """把提取结果渲染为 Markdown，便于直接阅读或喂给 AI。"""
    lines: list[str] = []
    name = Path(file_result["source"]).name
    lines.append(f"# {name}\n")
    summary = file_result.get("summary", {})
    lines.append(
        f"> 页数 {summary.get('page_count', 0)} | "
        f"字符 {summary.get('total_chars', 0)} | "
        f"图片 {summary.get('image_count', 0)}\n"
    )
    for page in file_result.get("pages", []):
        title = page.get("title") or f"第 {page['index']} 页"
        lines.append(f"## {title}\n")
        if page.get("author"):
            lines.append(f"*作者：{page['author']}*\n")
        if page.get("text"):
            lines.append(page["text"] + "\n")
        for img in page.get("images", []):
            fname = img.get("filename") or "(未命名)"
            rel = img.get("saved_to")
            if rel:
                lines.append(f"![{fname}]({rel})\n")
            else:
                lines.append(f"（图片：{fname}，{img.get('bytes', 0)} 字节，未导出）\n")
    return "\n".join(lines)


def parse_source(src: ParserConfig) -> list[dict[str, Any]]:
    """解析一个来源（文件或目录）下的所有 .one。"""
    results: list[dict[str, Any]] = []

    for f in src.files():
        if not is_one_file(f):
            results.append(
                {
                    "ok": False,
                    "stage": "magic",
                    "source": str(f),
                    "error": "不是 .one 文件（容器魔数不匹配），已跳过",
                    "pages": [],
                    "summary": {},
                }
            )
            continue

        res = extract_file(
            f,
            extract_images=src.extract_images,
            image_dir=src.image_dir,
            include_empty_pages=src.include_empty_pages,
        )

        if src.max_pages_per_file is not None:
            res["pages"] = res["pages"][: src.max_pages_per_file]

        if src.min_chars and res.get("summary", {}).get("total_chars", 0) < src.min_chars:
            res["skipped"] = (
                f"字符数 {res['summary']['total_chars']} < min_chars {src.min_chars}"
            )

        results.append(res)

    return results


def parse_all(cfg: AppConfig) -> dict[str, Any]:
    """按配置解析所有来源并汇总。"""
    report: dict[str, Any] = {
        "output_dir": str(cfg.output_dir),
        "files": [],
        "summary": {},
    }

    total_pages = total_chars = total_images = 0
    ok = failed = 0

    for src in cfg.sources:
        for res in parse_source(src):
            report["files"].append(res)
            if res.get("ok"):
                ok += 1
                s = res.get("summary", {})
                total_pages += s.get("page_count", 0)
                total_chars += s.get("total_chars", 0)
                total_images += s.get("image_count", 0)
            else:
                failed += 1
                if cfg.fail_fast:
                    report["summary"] = {
                        "file_count": len(report["files"]),
                        "ok": ok,
                        "failed": failed,
                        "aborted": True,
                    }
                    return _write_outputs(cfg, report)

    report["summary"] = {
        "file_count": len(report["files"]),
        "ok": ok,
        "failed": failed,
        "page_count": total_pages,
        "total_chars": total_chars,
        "image_count": total_images,
    }
    return _write_outputs(cfg, report)


def _write_outputs(cfg: AppConfig, report: dict[str, Any]) -> dict[str, Any]:
    """把报告写到 output_dir（只写这里，不碰源文件）。"""
    if cfg.write_json:
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        out = cfg.output_dir / "notes.json"
        out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        report["written_json"] = str(out)

    if cfg.write_markdown:
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        for res in report["files"]:
            if not res.get("ok"):
                continue
            stem = Path(res["source"]).stem
            safe = "".join(c for c in stem if c.isalnum() or c in "._- ")[:80] or "note"
            (cfg.output_dir / f"{safe}.md").write_text(
                _to_markdown(res), encoding="utf-8"
            )
        report["written_markdown_dir"] = str(cfg.output_dir)

    return report
