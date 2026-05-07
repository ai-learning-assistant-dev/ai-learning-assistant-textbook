# AI Learning Assistant Textbook

面向“学科培训”的本地课程生产工具。它把视频资源处理、AI 内容生成、课程结构编写和线上课程库管理串成一条完整流程：从 Bilibili 视频开始，生成字幕、知识要点、正文和题目，整理为标准 `course.json`，再上传到学科培训后端进行测试和管理。

默认 Web 地址：

```text
http://127.0.0.1:7200
```

## 功能总览

这个工具目前支持四类核心工作。

### 视频资源处理

- 支持单个 Bilibili 视频、分 P 视频、收藏夹批量处理。
- 自动下载视频封面、视频信息和字幕。
- 优先读取在线字幕；没有在线字幕时，可继续使用本地 ASR 转录。
- 支持配置 SESSDATA，用于读取需要登录状态的视频字幕。
- 音频下载具备兜底路径，可提升部分视频的转录成功率。

### AI 课程素材生成

- 调用已配置的大模型生成课程生产素材。
- 可生成知识要点 `summary.json`。
- 可生成知识正文 `.md`。
- 可生成练习题 `exercises.json`。
- 可生成引导问题 `questions.json`。
- 支持任务列表查看进度、状态和生成文件。

### 可视化课程编写

- 以工作区管理课程素材，一门课程对应一个本地工作区。
- 支持从工作区加载课程，或打开本地课程 JSON。
- 支持编辑课程基础信息、章、小节、AI 人设、分类和图标。
- 支持编辑小节知识正文、知识要点、视频字幕、引导问题和练习题。
- 支持导入 SRT 到小节字幕，并将 `knowledge_points` 与 `video_subtitles` 一并保存到单个 `course.json`。
- 自动规范化课程 JSON，兼容旧格式并补齐必要主键。

### 学科培训课程库管理

- 可在课程编辑器内直接连接学科培训后端，默认地址为 `http://127.0.0.1:7100`。
- 支持上传当前课程到课程库。
- 支持测试读取当前课程或线上课程。
- 支持从学科培训后端导出指定课程 JSON。
- 支持删除线上课程。
- 上传前会检查课程标题、章/小节结构、主键和扩展字段，降低错误课程进入线上库的概率。

启动器一次性动态构建方案见 [doc/launcher-dynamic-build.md](doc/launcher-dynamic-build.md)。

## 页面入口

启动后打开：

```text
http://127.0.0.1:7200
```

顶部包含两个主要页面：

- `视频下载`：配置模型、工作区、SESSDATA，创建视频处理任务。
- `课程编辑`：编辑课程结构和课程内容，并打开课程库管理面板。

## 推荐使用流程

1. 在“模型配置”中添加可用大模型。
2. 在“工作区配置”中为当前课程创建工作区。
3. 在“Cookie 配置”中填写并测试 SESSDATA。
4. 在“创建下载任务”中粘贴视频 URL 或收藏夹 URL。
5. 等待任务生成字幕、封面、知识要点、正文、题目和引导问题。
6. 进入“课程编辑”，选择工作区并加载课程。
7. 整理课程标题、描述、章节、小节、知识正文、知识点、字幕和题目。
8. 点击“保存”写回工作区，或点击“另存为”导出课程 JSON。
9. 打开“课程库管理”，连接学科培训后端。
10. 上传当前课程，刷新线上课程库并测试读取。

## 本地开发与运行

项目当前推荐使用 `uv` 管理 Python 环境，使用 `bun` 构建前端。

### 1. Python 依赖

基础依赖：

```powershell
uv sync
```

包含本地 ASR / GPU 相关依赖：

```powershell
uv sync --extra gpu
```

如果是全新环境，可先安装 Python 3.12：

```powershell
uv python install 3.12
uv sync --python 3.12 --extra gpu
```

### 2. 前端依赖与构建

```powershell
cd frontend
bun install
bun run build
cd ..
```

前端构建产物会写入根目录 `templates/`，由 Flask 服务直接托管。

### 3. 启动 Web 服务

```powershell
uv run python start_web.py
```

浏览器打开：

```text
http://127.0.0.1:7200
```

### 4. 常用环境变量

普通用户通过启动器使用时通常无需手动设置。维护或开发环境可参考：

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON_INSTALL_DIR = "<launcher>\external-resources\native-runtime\python"
$env:BUN_INSTALL_CACHE_DIR = "$PWD\frontend\.bun\install\cache"
```

本地 ASR 进程会在代码中自动设置必要运行参数，避免部分 Windows 环境中数值计算运行库重复初始化导致转录失败。

## 配置文件

### 应用配置

`config/app_config.json`

关键字段：

```json
{
  "output_directory": "subtitles",
  "web_port": 7200,
  "download_all_parts": false,
  "max_concurrent_tasks": 2,
  "ffmpeg_path": "ffmpeg",
  "courses_api_base": "http://127.0.0.1:7100"
}
```

说明：

- `output_directory`：默认输出目录。
- `web_port`：Web 服务端口，当前默认 `7200`。
- `download_all_parts`：是否默认下载所有分 P。
- `max_concurrent_tasks`：最大并发任务数。
- `ffmpeg_path`：FFmpeg 路径。
- `courses_api_base`：学科培训后端地址。

### 模型配置

`config/llm_models.json`

也可以在 Web 界面“模型配置”中新增或编辑。

```json
{
  "models": [
    {
      "id": "1",
      "name": "模型显示名称",
      "model_name": "模型标识",
      "api_base": "https://your-api-base/v1",
      "api_key": "your-api-key"
    }
  ]
}
```

### Bilibili 登录信息

可在 Web 界面的“Cookie 配置”中填写 SESSDATA，也可维护 `cookies.txt`。

格式示例：

```text
SESSDATA=你的SESSDATA值
```

SESSDATA 有有效期。如果视频字幕读取异常，可重新获取并更新。

## 输出结构

默认输出根目录为 `subtitles/`。每个工作区建议对应一门课程。

示例：

```text
subtitles/
└── 英语基础语法/
    ├── course.json
    ├── There_be句型的本质/
    │   └── section.json
    ├── 视频标题.srt
    ├── 视频标题_cover.jpg
    ├── 视频标题_summary.json
    ├── 视频标题_exercises.json
    └── 视频标题_questions.json
```

具体文件会根据视频标题、分 P 标题和任务选项生成。

## 课程 JSON 结构

课程编辑器以单个 `course.json` 作为课程生产与上传的核心文件。

重要结构：

```json
{
  "course_id": "uuid",
  "title": "课程标题",
  "description": "课程描述",
  "category": "职业技能",
  "ai_persona": {
    "persona_id": "uuid",
    "name": "课程助手名称",
    "prompt": "课程助手提示词",
    "is_default_template": true
  },
  "chapters": [
    {
      "chapter_id": "uuid",
      "title": "第1章",
      "order": 0,
      "sections": [
        {
          "section_id": "uuid",
          "title": "小节标题",
          "order": 0,
          "estimated_time": 5,
          "video_url": "https://...",
          "knowledge_content": "Markdown 正文",
          "knowledge_points": {
            "key_points": []
          },
          "video_subtitles": [],
          "leading_questions": [],
          "exercises": []
        }
      ]
    }
  ]
}
```

说明：

- `course_id`、`chapter_id`、`section_id` 是后端建立课程关联关系的关键字段。
- `knowledge_points.key_points` 用于保存知识要点。
- `video_subtitles` 用于保存视频字幕记录。
- 当前课程库上传逻辑会直接携带这些扩展字段，便于学科培训后端保存和后续读取。

## 视频下载与转录

### 支持输入

- 单个 Bilibili 视频 URL
- 多个视频 URL，每行一个
- 分 P 视频 URL，例如带 `?p=2`
- 收藏夹 URL
- 视频 URL 和收藏夹 URL 混合输入

### 字幕处理策略

处理顺序：

1. 优先读取在线视频字幕。
2. 如果没有在线字幕，尝试使用本地同名 SRT。
3. 如果仍不可用，自动进行本地 ASR 转录。

音频下载优先使用 `yt-dlp`。当页面入口返回 412 或入口不稳定时，会自动使用 B 站播放地址接口作为兜底路径下载音频，再交给本地 ASR 转录。

### 本地 ASR

本地 ASR 使用 `faster-whisper`。首次使用模型时会自动准备模型文件，默认保存在 `models/`。

如果没有检测到 CUDA 设备，会自动使用 CPU 模式，并将计算类型调整为 CPU 可用模式。

## 课程编辑器

课程编辑器支持两种打开方式：

- `工作区模式`：从工作区加载课程，可保存回服务器。
- `文件模式`：通过“选中 JSON”打开本地文件，只能另存为导出。

主要编辑项：

- 课程信息：标题、描述、AI 人设、分类、图标、贡献者。
- 章：标题和排序。
- 小节：
  - 基础信息
  - 知识正文
  - 知识要点
  - 视频字幕
  - 引导问题
  - 练习题

右侧“可用节”面板可从当前工作区生成的小节素材中插入内容。

## 学科培训课程库管理

在课程编辑器顶部点击“课程库管理”。

功能：

- 配置和测试学科培训后端地址
- 刷新线上课程列表
- 校验当前课程是否可上传
- 上传当前课程
- 测试读取课程
- 导出线上课程 JSON
- 删除线上课程

默认后端地址：

```text
http://127.0.0.1:7100
```

上传前会检查：

- 是否有课程标题
- 是否至少包含 1 个章和 1 个小节
- 章和小节是否存在主键
- 内容统计是否正常
- 知识点和字幕字段是否正常

如果检查项出现红色错误，需要先回到课程编辑器修复。

## 命令行工具

Web 界面是当前推荐入口。命令行工具仍可用于自动化或批处理。

```powershell
# 一键下载并总结
uv run python download_and_summarize.py "视频URL" -n "模型名称"

# 处理收藏夹
uv run python download_and_summarize.py "收藏夹URL" -n "模型名称"

# 指定输出文件夹
uv run python download_and_summarize.py "视频URL" -f "课程名称" -n "模型名称"

# 下载所有分 P
uv run python download_and_summarize.py "视频URL" -n "模型名称" --download-all-parts

# 查看可用模型
uv run python download_and_summarize.py --list-models

# 只下载字幕
uv run python bilibili_subtitle_downloader.py "视频URL"

# 合并 Excel
uv run python merge_excel_files.py "人工Excel.xlsx" "程序Excel.xlsx" -o "合并后.xlsx"
```

## 启动器动态构建

当前项目已按启动器本地动态构建方向适配：

- 默认端口：`7200`
- 健康检查：`GET http://127.0.0.1:7200/api/config`
- Python：建议使用启动器内置 `uv`
- 前端：建议使用启动器内置 `bun`
- 用户数据建议保留：
  - `config/`
  - `subtitles/`
  - `cookies.txt`
  - `models/`
- 可重建目录：
  - `.venv/`
  - `.uv-cache/`
  - `frontend/node_modules/`
  - `frontend/.bun/`
  - `templates/`

完整落地说明见：

[doc/launcher-dynamic-build.md](doc/launcher-dynamic-build.md)

## 常见问题

### 页面打不开

检查服务是否启动，访问地址是否为：

```text
http://127.0.0.1:7200
```

如果端口被占用，可关闭占用 7200 的程序后重试。

### 没有可选模型

进入“模型配置”添加模型，确认模型名称、模型标识、API 地址和 API 密钥都已填写。

### 下载任务无法创建

检查是否已填写视频 URL、选择工作区、选择模型。

### 视频没有在线字幕

这是正常情况。软件会继续尝试本地 SRT 或本地 ASR 转录。

### 本地 ASR 首次运行很慢

首次运行可能需要准备模型文件。模型准备完成后，后续同模型转录会更快。

### 课程无法上传

先打开“课程库管理”的当前课程检查结果。常见原因是缺少课程标题、没有章/小节、章或小节主键缺失，或旧版 JSON 结构未规范化。

### 学科培训后端连接失败

确认学科培训后端已启动，并检查地址是否为：

```text
http://127.0.0.1:7100
```

## 相关文档

- [启动器动态构建说明](doc/launcher-dynamic-build.md)
- [依赖安装简述](doc/About%20dependence.md)