# services/ — 后端业务服务

每个子目录对应首页的一个功能栏，目录名与前端 `frontend/src/panels/` 下的面板名一一对应。

| 服务 | 前端面板 | 接口前缀 | 职责 |
|---|---|---|---|
| `notecard/` | `panels/notecard`（笔记制卡） | `/api/notecard` | 笔记 → Anki Basic 卡片 → `.apkg`（引擎为迁入的 Note2Anki） |

## 约定

1. 子包自包含：路由、领域逻辑都放在自己的目录里，不外泄到 `app.py`。
2. 子包通过 Flask `Blueprint` 暴露接口，统一 `/api/<服务名>/` 前缀，与 app.py 里
   「视频下载」主线的历史路由零重叠。
3. app.py 只调用一次 `register_all(app)`；新增服务在 `services/__init__.py`
   的 `_SUBPACKAGES` 登记即可，不用再动 app.py。
4. 服务之间只允许 `services.<服务名>` 方向的显式导入，不允许反向依赖 app.py。
5. **可选依赖懒加载**：会拖垮服务启动的依赖（如 aspose / genanki）在路由里按需导入，
   缺失时接口返回明确提示，而不是让整个 Flask 起不来。

## notecard

引擎在 `services/notecard/note2anki/`，HTTP 层在 `services/notecard/routes.py`。
路由只做「取请求体 → 调 `note2anki.server` 的 do_* 函数 → 映射错误码」，
业务判断一律留在引擎里。

依赖：`genanki>=0.13.0`、`aspose-note-foss==26.9.0`。

**只读保证**：OneNote 源 `.one` 文件全程只读，产物只落 `out/`（导出）与内存缓存（解析）。

细节见 `services/notecard/README.md`。
