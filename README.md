# Bilibili 视频字幕下载与教程编写

一个功能强大的Python工具，用于下载Bilibili视频字幕（包括AI字幕），并调用大模型生成教程内容。

**提供两种使用方式：**
- 🌐 **Web界面**（推荐）- 简单易用的网页操作界面
- 💻 **命令行工具** - 适合批处理和自动化

## 开发进度

- [ ] 通过url获取视频信息
  - [x] b站ai字幕/标题
  - [ ] b站视频封面，无ai字幕视频
  - [ ] 其他网站
- [x] 知识要点总结 
- [ ] 知识内容
- [ ] 预设问题
- [ ] 习题及答案


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

```
subtitles/
├── 视频标题_ai-zh.srt              # 字幕文件
├── 视频标题_ai-zh.summary.txt      # 总结文件（文本格式）
└── 视频标题_ai-zh.summary.json     # 总结文件（JSON格式）
```

### 总结格式示例

```
================================================================================
视频内容总结
================================================================================

关键要点（共 2 个）：

1. [00:07] 电工入行分享：工种、证书与求职
   本期分享电工入行知识，强调电工必须持证上岗...

2. [04:28] 电工入行与考证流程全解析
   电工入行一般有老师傅带，可从物业电工、工厂学徒等...

================================================================================
```

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
3. **无字幕视频**：如果视频没有字幕，程序会提示并直接退出
4. **安全提醒**：请妥善保管Cookie，不要分享给他人

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

## 常见问题

**Q: AI字幕必须登录吗？**  
A: 是的，B站AI字幕需要登录凭证（SESSDATA）才能下载。

**Q: 如何打包成exe？**  
A: Windows运行 `build.bat`，打包结果在 `release` 目录。

## 许可证

MIT License

## 免责声明

本工具仅供学习交流使用，请勿用于商业目的，请遵守Bilibili的服务条款和相关法律法规。
