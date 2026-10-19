#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : __init__.py
# @Path       : analyse/src/hotel_insight/viz/__init__.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 11:20:00
# @Version    : v1.1.0
# @Description: 图表包入口：重新导出 theme 与 charts 的名字。
# @ChangeLog:
#   2026-10-18 17:45:00 | 一班第十二组 | v1.0.0 | 初始化创建
#   2026-10-19 11:20:00 | 一班第十二组 | v1.1.0 | 增加 charts 图型库，viz.hbar / viz.heat 可直接用
"""
notebook 里的两种写法都成立：
    from hotel_insight import viz;  viz.apply_theme()、viz.finish(...)、viz.hbar(...)
    from hotel_insight.viz import MAIN, GRAY
styles/ 是主题文件（数据文件只能跟着包一起安装，所以主题放在包里而不是项目根）。
"""
from . import charts
from .charts import *          # noqa: F401,F403
from .charts import __all__ as _charts_all
from .theme import *           # noqa: F401,F403  （theme.py 的 __all__ 决定导出哪些名字）
from .theme import __all__ as _theme_all

__all__ = [*_theme_all, *_charts_all, "charts"]
