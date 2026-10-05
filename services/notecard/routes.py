"""笔记制卡服务的 HTTP 接口，挂载在 ``/api/notecard`` 下。

这一层只做三件事：取请求体、调 ``note2anki.server`` 里的 do_* 函数、
按迁移前的错误码映射回响应。业务判断一律不写在这里。

依赖是懒加载的：制卡引擎需要 genanki / aspose-note-foss，
没装时接口给出可操作提示，而不是让整个 Flask 服务起不来。
"""

import traceback

from flask import Blueprint, jsonify, request, send_from_directory

from .note2anki.extract_llm import LLMError, LLMNotConfigured

bp = Blueprint('notecard', __name__, url_prefix='/api/notecard')

# 路径 → note2anki.server 里的 do_* 函数名
_POST_ROUTES = {
    'extract': 'do_extract',
    'compare': 'do_compare',
    'validate': 'do_validate',
    'export': 'do_export',
    'onenote/browse': 'do_onenote_browse',
    'onenote/scan': 'do_onenote_scan',
    'onenote/pages': 'do_onenote_pages',
    'onenote/page': 'do_onenote_page',
    'onenote/section': 'do_onenote_section',
}


def _engine():
    """懒加载制卡引擎（内含 aspose / genanki 两个可选依赖）。"""
    try:
        # 必须显式导入子模块：note2anki/__init__.py 只写了文档字符串，
        # `from . import note2anki` 拿不到 .server 属性
        from .note2anki import server
        return server, None
    except ImportError as exc:
        return None, (
            f"制卡引擎依赖缺失：{exc}。请先安装 genanki>=0.13.0 与 "
            "aspose-note-foss==26.9.0 再重启服务。"
        )


def _dispatch(func_name, payload):
    """调一个 do_* 函数，并把异常映射成与迁移前一致的 HTTP 状态码。"""
    srv, err = _engine()
    if err:
        return jsonify({'error': err, 'code': 'engine_missing'}), 500

    try:
        return jsonify(getattr(srv, func_name)(payload))
    except srv.OneNoteError as exc:
        return jsonify({'error': str(exc), 'code': 'onenote_error'}), 400
    except LLMNotConfigured as exc:
        return jsonify({'error': str(exc), 'code': 'llm_not_configured'}), 400
    except LLMError as exc:
        return jsonify({'error': str(exc), 'code': 'llm_error'}), 502
    except ValueError as exc:
        return jsonify({'error': str(exc), 'code': 'bad_request'}), 400
    except Exception as exc:  # noqa: BLE001 - 兜底，避免前端只拿到一个 500 空壳
        traceback.print_exc()
        return jsonify({'error': f'{type(exc).__name__}: {exc}'}), 500


def _register():
    """按 _POST_ROUTES 逐个登记路由；新增接口只需在上面加一行。"""
    def make(func_name):
        def view():
            payload = request.get_json(silent=True) or {}
            return _dispatch(func_name, payload)
        return view

    for path, func_name in _POST_ROUTES.items():
        endpoint = 'do_' + path.replace('/', '_')
        bp.add_url_rule('/' + path, endpoint=endpoint, view_func=make(func_name),
                        methods=['POST'])


_register()


@bp.route('/health', methods=['GET'])
def health():
    """健康检查；engine 缺失时 ok=false，便于面板给出提示。"""
    _, err = _engine()
    return jsonify({'ok': err is None, 'error': err})


@bp.route('/out/<path:filename>', methods=['GET'])
def download_out(filename):
    """下载导出的 .apkg。send_from_directory 自带目录穿越防护。"""
    srv, err = _engine()
    if err:
        return jsonify({'error': err, 'code': 'engine_missing'}), 500
    return send_from_directory(srv.OUT_DIR, filename, as_attachment=True)
