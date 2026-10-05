"""打包层：卡片列表 -> .apkg。

相对 Skill A 的关键修正：ID 稳定化。
Skill A 每次运行都用 random 生成 model_id 与 deck_id，导致同一份笔记重复导出再导入时，
Anki 认为是全新的笔记类型与牌组，必然产生重复卡。
这里改成对「模型名 / 牌组名」做哈希，ID 恒定，重复导入会命中已有笔记而不是新建。
"""

from __future__ import annotations

import hashlib
import os
import re

import genanki

from .schema import Card

MODEL_KEY = "note2anki.basic.v1"
MODEL_NAME = "Note2Anki Basic"

CSS = """
.card {
  font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif;
  font-size: 20px;
  line-height: 1.6;
  text-align: center;
  color: #24292f;
  background: #ffffff;
  padding: 24px;
}
.card .cloze { font-weight: bold; color: #0969da; }
hr#answer { margin: 16px 0; border: none; border-top: 1px solid #d0d7de; }
code {
  font-family: Consolas, Monaco, monospace;
  background: #f6f8fa;
  padding: 1px 5px;
  border-radius: 4px;
}
table { border-collapse: collapse; margin: 8px auto; }
th, td { border: 1px solid #d0d7de; padding: 4px 10px; }
"""

_QUESTION = '<div class="card">{{Front}}</div>'
_ANSWER = '<div class="card">{{FrontSide}}<hr id="answer">{{Back}}</div>'


def _stable_id(key: str) -> int:
    """把字符串映射成 genanki 需要的稳定正整数 ID。"""
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return (1 << 30) + (int(digest[:10], 16) % (1 << 30))


def basic_model() -> genanki.Model:
    return genanki.Model(
        _stable_id(MODEL_KEY),
        MODEL_NAME,
        fields=[{"name": "Front"}, {"name": "Back"}],
        templates=[{"name": "Card 1", "qfmt": _QUESTION, "afmt": _ANSWER}],
        css=CSS,
    )


def _safe_tag(tag: str) -> str:
    """Anki 用空格分隔标签，含空格的标签会被切开。"""
    return re.sub(r"\s+", "_", str(tag).strip())


def _safe_deck_name(name: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", (name or "").strip())
    return cleaned or "Note2Anki"


def build_apkg(cards: list[Card], deck_name: str, out_path: str) -> dict:
    """把卡片打包成 .apkg，返回统计信息。

    空正面 / 空反面的卡片会被跳过（Anki 导入它们没有意义）。
    """
    deck_name = _safe_deck_name(deck_name)
    deck = genanki.Deck(_stable_id(f"deck::{deck_name}"), deck_name)
    model = basic_model()

    used, skipped = 0, 0
    for c in cards:
        front = (c.front or "").strip()
        back = (c.back or "").strip()
        if not front or not back:
            skipped += 1
            continue
        deck.add_note(genanki.Note(
            model=model,
            fields=[front, back],
            tags=[_safe_tag(t) for t in c.tags if str(t).strip()],
        ))
        used += 1

    if used == 0:
        raise ValueError("没有可打包的卡片（正面或反面为空）")

    parent = os.path.dirname(os.path.abspath(out_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    genanki.Package(deck).write_to_file(out_path)

    return {
        "deck": deck_name,
        "path": out_path,
        "written": used,
        "skipped": skipped,
        "bytes": os.path.getsize(out_path),
    }
