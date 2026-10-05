# 笔记制卡（notecard）

首页第三个功能栏背后的服务。把笔记（OneNote 页面 / Markdown 文件 / 直接粘贴）
变成 Anki 的 Basic 卡片（正面问句 + 反面答案），逐条校验修改后导出 `.apkg`。

引擎由独立项目 **Note2Anki** 迁入 `note2anki/`，解析与校验逻辑保持原样；
只把 HTTP 层换成 Flask Blueprint（`routes.py`），前端换成 React 面板。

## 目录结构

```
services/notecard/
├── routes.py        Flask Blueprint，挂在 /api/notecard 下
└── note2anki/       迁入的引擎（逻辑与原项目一致）
    ├── server.py        do_* 业务函数（不含 HTTP 服务器）
    ├── schema.py        BasicCard 模型与校验层
    ├── preprocess.py    笔记清洗（剥离 frontmatter、MD → HTML）
    ├── extract_rule.py  规则提取（兜底）
    ├── extract_llm.py   OpenAI 兼容调用 + 离线回落（SYSTEM_PROMPT 在这里）
    ├── apkg.py          打包 .apkg（ID 按内容哈希，可重复导入）
    ├── onenote_api.py   OneNote 适配层（浏览 / 扫描 / 列页 / 渲染）
    └── onenote/         OneNote .one 解析（只读，不改源文件）
```

## 使用流程

左栏三种来源，从上到下优先级递减：

### ① OneNote（默认展开）

1. **路径框**填 OneNote 存储目录，比如 `G:\Software\OneNoteFiles\16.0\备份\电子维修`。
   记不清路径就点「浏览」——浏览器选不了本地文件夹，所以这个按钮由服务端列目录，
   空路径先出盘符，逐级点进去，「选定」回填。
2. **扫描笔记本** → 出树：笔记本 → 分区组 → 分区。这一步只读文件名和魔数，很快。
3. **点分区才解析页**（19MB 的分区也是秒开）。顶部有一条「整分区 · 全部 N 页」。
4. **点某页** → 弹层预览（渲染 / 源码切换）→ 「用此内容制卡」，内容灌进管线。

> 也可以直接把某个 `.one` 文件的完整路径粘进路径框，会自动一路展开到页列表。

> 分区如果出现橙色提示「容错解析」，说明该文件有截断数据、内容可能不完整，
> 是 aspose 库的边界检查缺陷，已打补丁尽力救回，但自己判断可信度。

### ② Markdown 文件

选一个本地 `.md` / `.txt` 文件，内容直接进管线（浏览器本地读取，不上传）。

### ③ 手动输入（默认折叠）

直接粘贴 Markdown 或纯文本。不常用所以折叠起来了，点标题展开。

## 出卡之后

1. **提取**：选提取方式 → 点「提取卡片」。
   - **LLM**：质量最好，推荐。OneNote 页面基本是列表大纲，只有 LLM 能问出像样的问题。
   - **规则提取**：无网 / 无 Key 时的兜底，靠「术语：定义」「Q/A」「标题+列表」这些正则挖。
     对 OneNote 大纲类内容效果很差，别用。
2. **校验**：中间列表标出每张卡的问题。红色 `error` 会阻断导出，黄色 `warning` 只提示。
   常见：`front_not_question`、`yes_no_card`、`duplicate_front`、`md_table_residue`。
   有「剔除问题卡」按钮，但你手动点才生效——**不会静默丢弃**。
3. **编辑**：点卡片，右侧表单改正面 / 反面 / 标签。
4. **导出**：填牌组名 → 导出 `.apkg` → 文件落在 `out/`，浏览器直接下载。
   然后在 Anki 里「文件 → 导入」选中它。

> 导出的牌组 **ID 是稳定的**（按内容哈希，不是随机数），同一批卡重复导入不会产生重复笔记。

## 接口

服务是无状态的，卡片列表由前端持有，每次校验 / 导出整份回传。

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/notecard/health` | 健康检查（含依赖是否可用） |
| POST | `/api/notecard/extract` | 提取卡片（rule / llm） |
| POST | `/api/notecard/compare` | 规则 + 多模型并排对比（并发）。UI 未暴露，调 Prompt 时可直连 |
| POST | `/api/notecard/validate` | 重新校验编辑后的卡片 |
| POST | `/api/notecard/export` | 导出 .apkg |
| GET | `/api/notecard/out/<filename>` | 下载导出的 .apkg |
| POST | `/api/notecard/onenote/browse` | 浏览服务端目录 |
| POST | `/api/notecard/onenote/scan` | 扫描笔记本 / 分区树 |
| POST | `/api/notecard/onenote/pages` | 列出分区下的页 |
| POST | `/api/notecard/onenote/page` | 渲染单页 Markdown |
| POST | `/api/notecard/onenote/section` | 渲染整个分区 Markdown |

错误码沿用迁移前的约定：`onenote_error` / `llm_not_configured`（400）、
`llm_error`（502）、`bad_request`（400）。

## 测试

```bash
python tests/run.py        # 全部（含本服务的 36 个用例）
python tests/run.py -v     # 带用例名
```

不需要真 Key、不需要网络。`tests/notecard/` 里覆盖了四样**界面上已移除、但代码完整保留**
的能力：章节汇总卡（默认关闭）、Mock 离线路径、多模型对比、内置样例（现为 fixtures）。
详见 `tests/notecard/README.md`。

## 已知限制

- **没接 AnkiConnect**，最后一步导入要手动在 Anki 里点。
- **图片不导出**。OneNote 页面里的图片在 Markdown 中只留 `![图片](images/...)` 占位，
  apkg 目前不支持 media。
- `SYSTEM_PROMPT`（`note2anki/extract_llm.py` 顶部）还是初版，改完需要重启服务生效。
- LLM 的 Key 不落盘，只走请求体或环境变量 `SILICONFLOW_API_KEY` / `OPENAI_API_KEY`。
