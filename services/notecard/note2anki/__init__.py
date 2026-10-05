"""Note2Anki：Markdown / TXT 笔记 -> Basic 闪卡 -> .apkg。

各模块职责：
    preprocess    笔记清洗：剥离 YAML frontmatter、Markdown 转 HTML
    schema        BasicCard 模型与校验层
    extract_rule  规则提取（无 LLM 时的兜底）
    extract_llm   OpenAI 兼容调用 + Mock
    apkg          打包为 .apkg（ID 稳定，可重复导入）
    server        本地 HTTP 服务与 JSON API
"""
