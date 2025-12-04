# Bilibili 视频字幕下载与教程编写

TODO:分p的excel录入逻辑还存在问题，需要进一步修改下！

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
  - [x] 无ai字幕视频
  - [ ] 其他视频源(如抖音等)
- [x] 知识要点总结
- [x] 知识完整内容（Markdown格式）
- [x] 预设问题（3个引导性问题）
- [x] 习题及答案（选择题+简答题）


## ✨ 新功能亮点

### 🗂️ 收藏夹批量下载 (v2.0)
- 支持直接输入B站收藏夹URL，自动获取并处理收藏夹内所有视频
- 适合批量学习系列课程、整理主题资料
- 支持收藏夹URL与视频URL混合输入

### 📁 自定义输出文件夹
- 可自定义文件夹名称，方便按主题或项目分类
- 多个视频可放在同一文件夹内
- 所有文件带视频标题前缀，避免冲突

### ⚡ 并发控制 (v2.1)
- **智能任务队列**：使用任务队列机制，避免API并发过高
- **可配置并发数**：默认同时处理2个视频，可在Web界面调整（1-10）
- **防止API限流**：
  - 设置为 **1** - 串行处理，完全避免并发，适合有严格限流的API
  - 设置为 **2-3** - 平衡效率与API限制，推荐大多数场景
  - 设置为 **4+** - 高并发，需要API支持较高并发量
- **自动保存配置**：并发数设置自动保存，重启后保持

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

# 处理收藏夹（批量下载）⭐新增
python download_and_summarize.py "收藏夹URL" -n 模型名称

# 自定义输出文件夹⭐新增
python download_and_summarize.py "URL" -f "Python学习合集" -n 模型名称

# 下载所有分P视频⭐新增
python download_and_summarize.py "视频URL" -n 模型名称 --download-all-parts

# 使用流式输出
python download_and_summarize.py "视频URL" -n 模型名称 --stream

# 查看可用模型
python download_and_summarize.py --list-models

# 只下载字幕
python bilibili_subtitle_downloader.py "视频URL"
```

## 输出文件

### 基本结构

```
subtitles/
└── 视频标题/                                    # 文件夹（可自定义）
    ├── 视频标题_video_info.json                # 视频信息⭐
    ├── 视频标题_cover.jpg                       # 视频封面⭐
    ├── 视频标题.xlsx                            # Excel格式视频信息
    ├── 字幕标题_ai-zh.srt                       # 字幕文件（SRT格式）
    ├── 字幕标题_summary.json                    # 要点总结（JSON格式）
    ├── 字幕标题_exercises.json                  # 练习题（JSON格式）
    ├── 字幕标题_questions.json                  # 预设问题（JSON格式）
    └── markdown/                                # Markdown文件目录
        └── 字幕标题.md                          # 完整内容（Markdown格式）
```

⭐ **文件命名优化**：`video_info.json` 和 `cover` 现在都带视频标题前缀，方便多视频在同一文件夹时区分

### 自定义输出示例

**单个视频（默认）：**
```
subtitles/视频标题/  # 使用视频标题作为文件夹名
```

**多个视频（自定义文件夹）：**
```
subtitles/
└── Python学习合集/               # 自定义文件夹名称
    ├── 视频1_video_info.json
    ├── 视频1_cover.jpg
    ├── 视频1_ai-zh.srt
    ├── 视频2_video_info.json
    ├── 视频2_cover.jpg
    └── ...
```

**🎯 多分P视频支持：**⭐优化
- 默认只下载URL指定的视频（例如 ?p=2 只下载第2个分P）
- 开启"下载所有分P"开关后，下载该视频的所有分P
- 每个分P生成独立的字幕和AI处理文件
- 文件名使用各自标题，不会覆盖
- 视频信息文件只有一份

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

### 生成内容说明

#### 完整内容文档 (markdown/*.md)
- 详细的学习内容，Markdown格式
- 自动去除时间标签，智能分段
- 包含概念解释、方法步骤、应用案例
- 适合学习复习、知识库文档

#### 预设问题 (questions.json)
- 3个引导性问题，帮助理解核心内容
- 由浅入深，总体把握→深入理解→应用扩展
- 适合学习前预习、观看时思考、学后反思

#### 练习题 (exercises.json)
- 5道选择题 + 5道简答题
- 覆盖视频主要知识点，难度适中
- 包含详细答案和解析
- 适合自我检测、复习巩固

## 高级功能

### 🗂️ 收藏夹批量下载

支持直接输入B站收藏夹URL，自动获取并处理收藏夹内所有视频。

**收藏夹URL格式：**
```
https://space.bilibili.com/UID/favlist?fid=收藏夹ID
```

**使用示例：**

```bash
# 网页端：直接在URL输入框粘贴收藏夹URL

# 命令行：
python download_and_summarize.py "收藏夹URL" -n 模型名称

# 指定输出文件夹（推荐）
python download_and_summarize.py "收藏夹URL" -f "Python学习合集" -n 模型名称
```

**功能特点：**
- ✅ 自动识别收藏夹URL和视频URL
- ✅ 支持收藏夹与视频URL混合输入
- ✅ 自动获取收藏夹内所有视频（分页支持）
- ✅ 逐个处理，显示详细进度
- ✅ 单个失败不影响其他视频

**适用场景：**
- 系列课程批量学习
- 主题资料整理归档
- 知识库批量构建

### 📁 自定义输出文件夹

可以自定义输出文件夹名称，灵活管理生成的文件。

**使用示例：**

```bash
# 网页端：在"自定义文件夹名称"输入框填写

# 命令行：
python download_and_summarize.py "URL" -f "我的学习资料" -n 模型名称
```

**应用场景：**

1. **多视频放同一文件夹：**
   ```bash
   # 输入多个URL + 指定文件夹名称
   python download_and_summarize.py "URL1" -f "Python合集" -n 模型
   python download_and_summarize.py "URL2" -f "Python合集" -n 模型
   # 或在网页端输入多行URL，指定同一文件夹名
   ```
   所有视频文件都在 `subtitles/Python合集/` 下，文件名带视频标题前缀

2. **收藏夹整理：**
   ```bash
   python download_and_summarize.py "收藏夹URL" -f "数据结构课程" -n 模型
   ```
   收藏夹内所有视频整理到同一文件夹

3. **主题分类：**
   按项目、主题或课程创建不同文件夹

### 📺 分P视频下载控制 (v2.1)

新增分P视频下载开关，可精确控制下载内容。

**功能说明：**

- **开关关闭（默认）**：严格按照URL下载，一个URL只下载一个视频
  - `https://bilibili.com/video/BV1xx` → 下载第1个分P
  - `https://bilibili.com/video/BV1xx?p=3` → 只下载第3个分P
  
- **开关开启**：下载该视频的所有分P（保持原有行为）
  - `https://bilibili.com/video/BV1xx?p=3` → 下载所有分P（第1、2、3...所有）

**使用方法：**

**网页端：**
在任务配置区域勾选"下载所有分P视频"复选框

**命令行：**
```bash
# 只下载URL指定的分P（默认）
python download_and_summarize.py "https://bilibili.com/video/BV1xx?p=2" -n 模型

# 下载所有分P
python download_and_summarize.py "https://bilibili.com/video/BV1xx?p=2" -n 模型 --download-all-parts
```

**应用场景：**

1. **精确下载特定章节：**
   - 只想学习某个系列课程的第5节，URL添加 `?p=5`，开关关闭

2. **下载完整系列：**
   - 需要下载整个系列教程，开关开启

3. **批量下载多个指定分P：**
   ```
   https://bilibili.com/video/BV1xx?p=1
   https://bilibili.com/video/BV1xx?p=5
   https://bilibili.com/video/BV1xx?p=10
   ```
   开关关闭，只下载第1、5、10这三个分P

## 配置文件

### config/app_config.json
```json
{
  "output_directory": "subtitles",          // 输出目录
  "last_selected_model": "模型名称",        // 上次选择的模型
  "cookies_file": "cookies.txt",           // Cookie文件路径
  "auto_refresh_interval": 2000,           // 刷新间隔(毫秒)
  "web_port": 5000,                        // Web服务端口
  "download_all_parts": false              // 是否下载所有分P（默认false）
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

1. **Cookie必需**：下载AI字幕必须配置SESSDATA，有效期约30天
2. **多P视频**：默认只下载URL指定的视频，可通过开关控制是否下载所有分P
3. **无字幕视频**：会跳过，不创建文件
4. **反爬虫**：已内置2秒延迟和重试机制，不要连续处理大量视频
5. **收藏夹处理**：视频较多时耗时较长，建议使用 `--stream` 查看实时进度
6. **安全**：妥善保管Cookie，不要分享

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
A: 是的，需要配置SESSDATA。

**Q: 收藏夹为空或无法访问？**  
A: 检查Cookie配置，确认收藏夹权限（可能是私密收藏夹）。

**Q: 如何只处理收藏夹中部分视频？**  
A: 目前不支持筛选，建议创建新收藏夹只添加需要的视频。

**Q: 多个视频如何避免文件混乱？**  
A: 所有文件都带视频标题前缀，不会冲突。留空文件夹名称则每个视频独立文件夹。

**Q: 如何打包成exe？**  
A: Windows运行 `build.bat`，打包结果在 `release` 目录。

## 许可证

MIT License

## 免责声明

本工具仅供学习交流使用，请勿用于商业目的，请遵守Bilibili的服务条款和相关法律法规。
