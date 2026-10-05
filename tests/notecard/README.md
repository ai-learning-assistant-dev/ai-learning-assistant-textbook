# tests/

跑法（项目根目录）：

```bash
python tests/run.py        # 全部用例
python tests/run.py -v     # 带用例名
python -m unittest discover -s tests -v
```

不需要真 Key，不需要网络。35 个用例约 5 秒跑完。

## 为什么有这个目录

界面上移除了四样东西，但**代码都没删**，它们的说明书就是这里的用例：

| 界面上 | 代码还在哪 | 用例 |
|---|---|---|
| 「生成章节汇总卡」复选框 | `extract_rule.extract_cards(include_section_cards=...)`、`/api/extract` | `test_section_cards.py` |
| 「Mock · 预置数据」选项 | `extract_llm.extract_cards_mock`（presets 由测试注入）、`/api/extract` 的 `mode=mock` | `test_mock_extract.py` |
| 「对比」Tab | `server.do_compare`、`/api/compare` | `test_compare.py` |
| 「内置样例」下拉 | 笔记搬到了 `fixtures/`，不再随产品分发 | `test_fixtures.py` |

想重新启用任何一个，直接改回 UI 即可，逻辑一行都不用动——用例会告诉你它现在是什么行为。

## fixtures/：真实笔记样例

`fixtures/note-network.md`（带 frontmatter / 标题 / 列表 / 表格的 Markdown）
和 `fixtures/note-plain.txt`（纯文本，含 Q/A 对）原本是界面上的内置样例，
现在只服务于开发者。想看它们在规则提取下的实际产出：

```bash
python tests/test_fixtures.py --demo
```

`mock_data.py` 里的内联笔记是**小而精的测试输入**（快、无文件依赖），
`fixtures/` 是**真实形态的完整笔记**，两者用途不同。

## 文件

- **`fixtures/`** —— 两份真实笔记，原本是界面上的内置样例。
- **`mock_data.py`** —— 模拟笔记样例 + 模拟模型返回 + **假 Key** + **预置卡片** `MOCK_CARDS`，
  另含 `load_fixture()`。`FAKE_API_KEY` 是假的，`fake_llm.py` 会把请求拦在本机，不会真的发出去。
- **`fake_llm.py`** —— 假的 OpenAI 兼容端点。按 model 名返回预设内容，
  并把每次请求（Bearer Key / model / system / user）记下来供断言。
- **`test_fixtures.py`** —— 真实笔记样例跑规则提取，`--demo` 可打印产出供肉眼检查。
- **`test_section_cards.py`** —— 章节汇总卡开关的开关前后对比、两种汇总卡形态、通过校验。
- **`test_mock_extract.py`** —— 预置库命中 / 未命中回落规则 / 打包进 apkg，
  外加一条 `test_production_has_no_builtin_presets`：不传 presets 时绝不能返回预置卡片
  （守的是「测试数据别混进生产模块」）。
- **`test_compare.py`** —— 规则基线列、多模型并列、坏模型只污染自己那一列。
- **`test_llm_pipeline.py`** —— 带（假）Key 的完整链路：提取 → 校验 → 编辑 → 导出 → 解包核对。

## 想接真模型验证

改 `mock_data.py` 里的 `FAKE_API_KEY` / `FAKE_BASE_URL` / `FAKE_MODEL` 为真值，
然后把 `fake_llm_endpoint` 去掉即可——其余代码路径完全一致。
反过来，日常的回归请保持用假端点，避免依赖网络和额度。
