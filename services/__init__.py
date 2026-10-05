"""

首页每个功能栏背后的服务在此目录下使用一个独立的命名空间。

1. 每个命名空间对应首页的一个功能栏（如 ``notecard`` = 笔记制卡），
   内部自包含路由、存储、领域逻辑，不把实现细节外泄到 app.py。
2. 子包通过 Flask ``Blueprint`` 暴露接口，统一使用 ``/api/<服务名>/`` 前缀，
   避免与 app.py 中「视频下载」主线的历史路由冲突。
3. app.py 只做一件事：导入本包的 ``register_all`` 并调用一次。
   服务之间的依赖通过 ``services.<服务名>`` 显式导入，不允许反向依赖 app.py。
4. 新增服务时：在此目录新建子包 → 在下方 ``_SUBPACKAGES`` 登记 →
   前端在 ``src/panels/`` 下建同名面板，两端按服务名一一对应。

"""

from . import notecard

# 服务注册表：新增服务在此登记
_SUBPACKAGES = (notecard,)


def register_all(app):
    """把所有服务的 Blueprint 注册到 app。

    在 app.py 中调用一次即可::

        from services import register_all
        register_all(app)
    """
    registered = []
    for pkg in _SUBPACKAGES:
        blueprint = getattr(pkg, "bp", None)
        if blueprint is None:
            raise RuntimeError(
                f"服务子包 {pkg.__name__} 未导出 bp（Blueprint）"
            )
        app.register_blueprint(blueprint)
        registered.append(blueprint.name)
    return registered


__all__ = ["register_all", "notecard"]
