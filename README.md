# Bilibili 视频字幕下载与教程编写

一个功能强大的Python工具，用于下载Bilibili视频字幕（包括AI字幕），并调用大模型生成教程内容。

**提供两种使用方式：**
- 🌐 **Web界面**（推荐）- 简单易用的网页操作界面，支持所有功能
- 💻 **命令行工具** - 适合批处理和自动化

**✨ Web界面已全面更新！** 现在完全支持所有新增功能，包括：
- ✅ 下载字幕和封面
- ✅ 生成要点总结 (summary.json)
- ✅ 生成完整内容文档 (content.md)
- ✅ 生成练习题 (exercises.json)
- ✅ 生成预设问题 (questions.json)
- ✅ 实时显示处理进度和生成的所有文件

## 开发进度

- [ ] 通过url获取视频信息
  - [x] b站ai字幕/标题
  - [x] b站视频封面
  - [ ] 无ai字幕视频
  - [ ] 其他视频源
- [x] 知识要点总结
- [x] 知识完整内容（Markdown格式）
- [x] 预设问题（3个引导性问题）
- [x] 习题及答案（选择题+简答题）


## 快速开始

### 方式一：使用打包版本（需完成打包）

1. 下载 `release` 文件夹中的所有文件
2. 编辑 `cookies.txt` 填入你的SESSDATA（见下方获取方法）
3. 双击运行 `BilibiliSubtitleSummarizer.exe`（首次启动需10-30秒）
4. 在浏览器中打开提示的地址（默认 http://127.0.0.1:5000）
5. 在Web界面添加大模型配置后即可使用

### 方式二：使用源码

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 配置Cookie

编辑 `cookies.txt` 文件：

```
SESSDATA=你的SESSDATA值
```

**获取SESSDATA：**
1. 登录 https://www.bilibili.com
2. 按 `F12` 打开开发者工具
3. 点击 `Application` → `Cookies` → `https://www.bilibili.com`
4. 找到 `SESSDATA`，复制其值并粘贴到 `cookies.txt`

#### 3. 配置LLM模型

方式1：启动web页面后可视化配置（推荐）

方式2：手动编辑 `config/llm_models.json`：

```json
{
  "models": [
    {
      "id": "1",
      "name": "你的模型名称",
      "model_name": "模型标识",
      "api_base": "http://your-api-url/v1",
      "api_key": "your-api-key"
    }
  ]
}
```

#### 4. 开始使用

**Web界面（推荐）：**

```bash
python start_web.py
```

然后在浏览器中打开：http://127.0.0.1:5000

**命令行：**

```bash
# 一键下载并总结
python download_and_summarize.py "视频URL" -n 模型名称

# 使用流式输出
python download_and_summarize.py "视频URL" -n 模型名称 --stream

# 查看可用模型
python download_and_summarize.py --list-models

# 只下载字幕
python bilibili_subtitle_downloader.py "视频URL"
```

## 输出文件

新版本采用文件夹组织方式，每个视频的所有文件都存放在以视频标题命名的文件夹中：

```
subtitles/
└── 视频标题/                        # 视频标题同名文件夹
    ├── cover.jpg                    # 视频封面图片
    ├── subtitle_ai-zh.srt           # 字幕文件（SRT格式）
    ├── summary.json                 # 要点总结（JSON格式）
    ├── content.md                   # 完整内容（Markdown格式）
    ├── questions.json               # 预设问题（JSON格式）⭐新增
    └── exercises.json               # 练习题（JSON格式）
```

**文件说明：**
- `cover.jpg` - 视频封面图片
- `subtitle_ai-zh.srt` - 原始字幕文件
- `summary.json` - AI生成的要点总结（3-8个关键要点，JSON格式）
- `content.md` - AI生成的完整学习内容文档（详细、结构化）
- `questions.json` - AI生成的预设问题（3个引导性问题）⭐
- `exercises.json` - AI生成的练习题（5道选择题 + 5道简答题）

### 要点总结示例 (summary.json)

```json
{
  "key_points": [
    {
      "time": "00:07",
      "title": "电工入行分享：工种、证书与求职",
      "description": "本期分享电工入行知识，强调电工必须持证上岗..."
    },
    {
      "time": "04:28",
      "title": "电工入行与考证流程全解析",
      "description": "电工入行一般有老师傅带，可从物业电工、工厂学徒等..."
    }
  ]
}
```

### 完整内容示例 (content.md) ⭐新增

`content.md` 文件包含视频的完整学习内容，采用Markdown格式：

#### 🎯 生成特点
- 📚 **教学导向**：专门设计用于学习的教学文档
- 📝 **内容详尽**：充分展开每个知识点，包含详细解释、例子和应用
- 🎨 **格式专业**：使用丰富的Markdown元素（表格、引用块、代码块等）
- 📖 **易于理解**：书面语表达，逻辑清晰，适合自学
- ✨ **智能预处理**：自动去除时间标签、合并文本、智能添加标点

#### 🔧 技术优化
1. **字幕预处理**：
   - 自动去除SRT时间标签和序号
   - 去除重复内容和口语冗余（如"啊"、"呃"）
   - 智能合并文本并添加标点符号
   - 自动分段，提高可读性

2. **内容生成**：
   - 详细的概念定义和解释
   - 完整的方法步骤说明
   - 实际应用场景和案例
   - 常见问题与注意事项

#### 📚 适用场景
- 📖 学习复习材料
- 📄 知识库文档
- 🔍 全文搜索
- ✏️ 二次编辑整理
- 🎓 教学参考资料

### 预设问题示例 (questions.json) ⭐新增

`questions.json` 文件包含3个精心设计的引导性问题，帮助学习者抓住视频核心内容：

#### 🎯 设计特点
- **简短精炼**：每个问题15-25字，快速抓住重点
- **概括性强**：能够覆盖视频的核心主题
- **启发思考**：引导主动思考，而非简单问答
- **递进关系**：由浅入深，逐步深入理解

#### 📝 问题类型
1. **总体把握型**：关于整体主题、核心概念
2. **深入理解型**：关于原因、方法、关系
3. **应用扩展型**：关于实践、启发、延伸

#### 📊 JSON格式示例

```json
{
  "questions": [
    {
      "id": 1,
      "question": "这个视频主要讨论了什么核心概念？",
      "type": "总体把握"
    },
    {
      "id": 2,
      "question": "为什么这种方法在实际中很重要？",
      "type": "深入理解"
    },
    {
      "id": 3,
      "question": "如何将这些理论应用到实际场景中？",
      "type": "应用扩展"
    }
  ]
}
```

#### 💡 使用场景
- 📖 学习前预习引导
- 🎯 观看时思考方向
- 📝 学习后反思检查
- 💬 讨论交流话题

### 练习题示例 (exercises.json) ⭐新增

`exercises.json` 文件包含基于视频内容生成的练习题，用于学习者自我检测：

#### 📝 题目组成
- **选择题（5道）**：考查核心知识点的理解
- **简答题（5道）**：深度考查概念解释、原因分析、方法应用等

#### 🎯 设计特点
1. **知识覆盖全面**：题目覆盖视频主要知识点
2. **难度适中**：既有基础题也有综合题
3. **答案详细**：
   - 选择题包含答案解析
   - 简答题提供答案要点和参考答案
4. **实用性强**：题目贴近实际应用场景

#### 📊 JSON格式示例

```json
{
  "multiple_choice": [
    {
      "id": 1,
      "question": "关于XX概念，下列说法正确的是？",
      "options": {
        "A": "选项A的内容",
        "B": "选项B的内容",
        "C": "选项C的内容",
        "D": "选项D的内容"
      },
      "correct_answer": "B",
      "explanation": "正确答案是B，因为...。选项A错误是因为...。"
    }
  ],
  "short_answer": [
    {
      "id": 1,
      "question": "请简述XX的主要特点和应用场景。",
      "answer_points": [
        "要点1：具体说明",
        "要点2：具体说明",
        "要点3：具体说明"
      ],
      "reference_answer": "XX的主要特点包括...。在实际应用中，主要用于..."
    }
  ]
}
```

#### 🎓 使用场景
- ✅ 学习后自我检测
- ✅ 知识点复习巩固
- ✅ 教学课后作业
- ✅ 考前模拟练习

## 配置文件

### config/app_config.json
```json
{
  "output_directory": "subtitles",          // 输出目录
  "last_selected_model": "模型名称",        // 上次选择的模型
  "cookies_file": "cookies.txt",           // Cookie文件路径
  "auto_refresh_interval": 2000,           // 刷新间隔(毫秒)
  "web_port": 5000                         // Web服务端口
}
```

### config/llm_models.json
```json
{
  "models": [
    {
      "id": "唯一ID",
      "name": "显示名称",
      "model_name": "模型标识",
      "api_base": "API地址",
      "api_key": "API密钥"
    }
  ]
}
```

## 注意事项

1. **Cookie必需**：下载AI字幕必须配置SESSDATA，Cookie有效期约30天
2. **多P视频**：程序会自动下载所有分P的字幕并逐个生成总结
3. **无字幕视频**：如果视频没有字幕，程序会跳过并不创建任何文件
4. **反爬虫保护**：
   - 程序已内置请求延迟（默认2秒间隔）和重试机制（最多3次）
   - 自动轮换User-Agent，降低触发反爬虫风险
   - 建议不要连续下载大量视频，可以间隔一段时间
5. **安全提醒**：请妥善保管Cookie，不要分享给他人

## 故障排除

### 提示"此视频没有字幕"
- 检查 `cookies.txt` 是否正确配置SESSDATA
- 使用 `--debug` 参数查看详细信息
- 在B站播放器确认视频是否真的有字幕

### Cookie过期
- 重新获取SESSDATA并更新 `cookies.txt`
- Cookie有效期约30天

### 无法访问视频
- 检查网络连接
- 确认视频存在且无地区/权限限制

### 请求失败或被限流 ⚠️
如果遇到反爬虫限制或请求失败：
1. **等待一段时间**（建议10-30分钟）再继续
2. **更换Cookie**：重新登录B站获取新的SESSDATA
3. **减少请求频率**：不要连续下载太多视频
4. **检查网络**：确认网络连接正常，尝试访问 bilibili.com
5. 程序已内置自动重试机制（最多3次），如果仍失败建议稍后再试

## 常见问题

**Q: AI字幕必须登录吗？**  
A: 是的，B站AI字幕需要登录凭证（SESSDATA）才能下载。

**Q: 如何打包成exe？**  
A: Windows运行 `build.bat`，打包结果在 `release` 目录。

## 许可证

MIT License

## 免责声明

本工具仅供学习交流使用，请勿用于商业目的，请遵守Bilibili的服务条款和相关法律法规。
