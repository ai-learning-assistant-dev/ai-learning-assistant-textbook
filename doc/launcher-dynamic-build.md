# 启动器动态构建适配说明

本文档面向 AI 学习助手启动器，用于把课程编写工具作为本地动态构建工具安装到工具箱。

## 运行定位

- 工具名称：课程编写工具
- 推荐安装目录：`external-resources/textbook-tool`
- 默认端口：`7200`
- 健康检查：`GET http://127.0.0.1:7200/api/config`
- 前端构建产物：`templates/`
- 用户数据目录：`config/`、`subtitles/`、`cookies.txt`、`models/`
- 学科培训后端默认地址：`http://127.0.0.1:7100`

## 启动器运行环境

启动器需要把内置 runtime 注入到 PATH：

```powershell
<launcher>\external-resources\native-runtime\bun
<launcher>\external-resources\native-runtime\uv
```

建议同时指定缓存目录，避免落到系统用户目录后出现权限或污染问题：

```powershell
$env:UV_CACHE_DIR = "<textbook-tool>\.uv-cache"
$env:UV_PYTHON_INSTALL_DIR = "<launcher>\external-resources\native-runtime\python"
$env:BUN_INSTALL_CACHE_DIR = "<textbook-tool>\frontend\.bun\install\cache"
```

## 一次性构建流程

在 `external-resources/textbook-tool` 目录执行：

```powershell
uv python install 3.12
uv sync --python 3.12 --extra gpu
```

然后构建前端：

```powershell
cd frontend
bun install
bun run build
cd ..
```

`vite` 会把前端产物写入根目录的 `templates/`，Flask 会直接托管该目录。

## 启动流程

启动前确保 `config/app_config.json` 至少包含：

```json
{
  "web_port": 7200,
  "courses_api_base": "http://127.0.0.1:7100"
}
```

启动命令：

```powershell
uv run python start_web.py
```

启动器等待健康检查成功后，使用 Electron `BrowserWindow` 打开：

```text
http://127.0.0.1:7200/
```

## 停止流程

当前课程编写工具没有专用 shutdown API。启动器第一版可按端口结束进程：

```powershell
netstat -ano | findstr :7200
taskkill /F /PID <pid>
```

后续如需更稳，可增加只允许本机调用的 `/shutdown` 接口。

## 更新与卸载边界

更新程序文件时不要删除用户数据：

- 保留：`config/`
- 保留：`subtitles/`
- 保留：`cookies.txt`
- 保留：`models/`
- 可重建：`.venv/`
- 可重建：`frontend/node_modules/`
- 可重建：`frontend/.bun/`
- 可重建：`templates/`

## 失败处理建议

- `uv sync` 失败：展示日志，提示检查网络或重试。
- Python 版本失败：优先执行 `uv python install 3.12`。
- `bun install` 失败：展示 registry、网络和缓存目录。
- 端口占用：提示用户关闭占用程序，或由启动器自动结束 7200 端口进程。
- 学科培训未启动：课程编写工具仍可打开，但课程库管理面板会显示未连接。
