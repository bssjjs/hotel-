#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : theme.py
# @Path       : analyse/src/hotel_insight/viz/theme.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 17:40:00
# @Version    : v1.0.0
# @Description: 蓝色系出图主题：语义色、主题切换、标题区与来源行。
# @ChangeLog:
#   2026-10-18 17:40:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
只会因为"图表规范变了"而改（AGENTS.md 第 2 条）。分工：
  · 外观（字体、坐标轴、网格、默认循环色、标题字号）写在 styles/*.mplstyle，用 matplotlib 的 plt.style 加载；
  · 含义（MAIN 强调、RED 只表示警示、"通过"是浅蓝）写在本文件的常量里，不随主题变；
  · finish() 统一标题区、来源行和保存。

import 本模块不改任何全局设置、不读文件（AGENTS.md 第 7 条）：要生效，调用方显式调用 apply_theme()。

配色纪律（docs/图表规范.md）：蓝色打底，一种颜色强调一件事，红色只表示警示。
本项目整体偏蓝：分类色用蓝色明度梯度，状态里"通过"给浅蓝而不是绿，避免一张图出现三种色相。
"""
from __future__ import annotations

from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Iterator

import matplotlib.pyplot as plt
from matplotlib.layout_engine import ConstrainedLayoutEngine
from matplotlib.patches import Rectangle

from .. import config

__all__ = [
    "MAIN", "MAIN_LIGHT", "MAIN_MID", "MAIN_DARK",
    "GRAY", "GRAY_DARK", "RED", "AMBER", "INK", "MUTED", "FAINT",
    "HOTEL_COLOR", "STATUS_COLOR", "BLUES",
    "apply_theme", "use_theme", "available_themes", "finish", "margins_in",
]

# ── 语义色：蓝色打底，灰色衬托，红色只表示警示 ──
# 这些是"含义"，不是"外观"：换主题不换它们，所以 from ... import MAIN 拿到的值永远对。
MAIN, MAIN_LIGHT, MAIN_MID, MAIN_DARK = "#1D6FA5", "#DCEAF5", "#7FB3D9", "#174E73"
GRAY, GRAY_DARK = "#C4CAD3", "#8E99A6"
RED, AMBER = "#D64545", "#B7791F"          # 不通过 / 警告
INK, MUTED, FAINT = "#1F2937", "#6B7280", "#9CA3AF"   # 标题正文 / 副标题 / 来源行

# 同一个对象在所有图里颜色相同：两家酒店、三种状态
HOTEL_COLOR = {"城市酒店": MAIN, "度假酒店": MAIN_MID}
STATUS_COLOR = {"通过": MAIN_MID, "警告": AMBER, "不通过": RED}

# 分类色：蓝色由深到浅，色相不跳（不用彩虹色阶）
BLUES = ("#174E73", "#1D6FA5", "#4A93C4", "#7FB3D9", "#A9CDE6", "#DCEAF5")

FONTS: list[str] = []      # apply_theme() 之后 = 当前生效的 font.family

# ── 主题文件 ──
_STYLES = files(__package__) / "styles"       # 随包安装的 styles/ 文件夹
_BASE = f"{__package__}.styles.base"


def available_themes() -> list[str]:
    """内置主题名（styles/ 里除 base 以外的 .mplstyle）。"""
    return sorted(p.name.removesuffix(".mplstyle") for p in _STYLES.iterdir()
                  if p.name.endswith(".mplstyle") and p.name != "base.mplstyle")


def _resolve(theme) -> str:
    """主题名 → plt.style 认的写法。内置名用包内路径；也可以直接给一个 .mplstyle 文件路径。"""
    name = str(theme or config.THEME)
    if (_STYLES / f"{name}.mplstyle").is_file():
        return f"{__package__}.styles.{name}"
    if name.endswith(".mplstyle") and Path(name).is_file():
        return name
    raise ValueError(f"没有主题 {name!r}：可用 {', '.join(available_themes())}，或给一个 .mplstyle 文件路径")


def apply_theme(theme: str | Path | None = None) -> list[str]:
    """应用主题，返回生效的字体列表。每本 notebook 第一格调用一次。

    theme 不给就用 config.THEME（环境变量 HOTEL_THEME 可覆盖）。
    总是先套 base 再套主题：切换顺序不影响结果，不会残留上一个主题的设置。
    """
    plt.style.use([_BASE, _resolve(theme)])
    FONTS[:] = plt.rcParams["font.family"]        # 原地更新：from ... import FONTS 也跟着变
    return list(FONTS)


@contextmanager
def use_theme(theme: str | Path) -> Iterator[list[str]]:
    """临时换主题，出了 with 自动恢复。同一本 notebook 里出两版图时用：
    建图、画图、finish 都要写在 with 里面——已经画好的图不会因为换主题重新着色。
    """
    with plt.style.context([_BASE, _resolve(theme)]):
        yield list(plt.rcParams["font.family"])


# ── 标题区与来源行 ──
def margins_in(n_sub: int) -> tuple[float, float]:
    """(顶部标题区高度, 底部来源行高度)，单位英寸；n_sub 是副标题行数。

    按"英寸"留白而不是按比例：图高 4 英寸还是 7 英寸，标题区看起来一样大。
    """
    return 0.67 + 0.23 * n_sub, 0.32


def finish(fig, title: str, subtitle: str, source: str, path: str | Path | None = None,
           *, accent: bool = True) -> Path | None:
    """给一张图加统一的标题区和来源行，留好上下空白；给了 path 就保存（相对路径存进 image/），返回完整路径。

    标题是 fig.texts[0]："读回断言"靠它检查标题里的数字是不是代码算的。
    标题字号取 rcParams["figure.titlesize"]，所以主题文件能改它。accent=False 去掉标题上方的主色短条。
    不做的事：不读数据库，不算业务数字（标题里的数由调用方算好传进来）。
    """
    h, w = fig.get_figheight(), fig.get_figwidth()
    n_sub = subtitle.count("\n") + 1 if subtitle else 0
    if accent:
        fig.add_artist(Rectangle((0.02, 1 - 0.115 / h), 0.38 / w, 0.045 / h,
                                 transform=fig.transFigure, color=MAIN, lw=0))
    fig.text(0.02, 1 - 0.19 / h, title, fontsize=plt.rcParams["figure.titlesize"],
             fontweight=plt.rcParams["figure.titleweight"], color=INK, va="top")
    if subtitle:
        fig.text(0.02, 1 - 0.48 / h, subtitle, fontsize=10.5, color=MUTED, va="top", linespacing=1.5)
    fig.text(0.02, 0.1 / h, source, fontsize=8.5, color=FAINT)

    head, foot = margins_in(n_sub)
    top, bottom = 1 - head / h, foot / h
    engine = fig.get_layout_engine()
    if isinstance(engine, ConstrainedLayoutEngine):
        engine.set(rect=(0.01, bottom, 0.98, top - bottom))     # 注意：这里是 (左, 下, 宽, 高)
    else:
        fig.tight_layout(rect=(0.01, bottom, 0.99, top))        # 这里是 (左, 下, 右, 上)

    if path is None:
        return None
    out = Path(path) if Path(path).is_absolute() else config.IMAGE_DIR / path
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    return out
