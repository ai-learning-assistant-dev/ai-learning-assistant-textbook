"""笔记制卡服务（notecard）：笔记 → Anki Basic 卡片 → .apkg。

内部结构
--------
- ``note2anki/``  制卡引擎（由独立项目 Note2Anki 迁入，逻辑保持原样）
  - ``onenote/``         OneNote `.one` 解析（只读）
  - ``schema.py``        BasicCard 模型与校验
  - ``extract_rule.py`` / ``extract_llm.py``  规则 / LLM 两条提取路径
  - ``apkg.py``          打包 `.apkg`（ID 按内容哈希，可重复导入）
  - ``server.py``        与 HTTP 无关的 do_* 业务函数
- ``routes.py``    Flask Blueprint，把 do_* 暴露在 ``/api/notecard`` 下

对外只暴露 ``bp``；后续功能建议在本子包内扩展，不要外泄到 app.py。
"""

from .routes import bp

__all__ = ["bp"]
