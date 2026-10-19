#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : charts.py
# @Path       : analyse/src/hotel_insight/viz/charts.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 11:10:00
# @Version    : v1.0.0
# @Description: 常用图型的画法：横向条、占比堆叠、热力、帕累托、瀑布、哑铃、象限。
# @ChangeLog:
#   2026-10-19 11:10:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
只会因为"图型规范变了（配色、标注位置、留白）"而改（AGENTS.md 第 2 条）。
这里的函数**只画，不算**（第 4 条）：数值由调用方算好传进来；
也**不加标题**——标题区统一由 theme.finish() 负责（第 12.1 条）。

颜色从 theme 里取，不在本文件写十六进制：同一含义在所有图里必须是同一个蓝。
"""
from __future__ import annotations

import numpy as np
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from matplotlib.patches import Rectangle

from .theme import BLUES, FAINT, GRAY, GRAY_DARK, INK, MAIN, MAIN_DARK, MAIN_LIGHT, MAIN_MID, RED

__all__ = ["BLUE_CMAP", "hbar", "grouped_hbar", "share_bar", "heat", "pareto",
           "waterfall", "dumbbell", "quadrant", "fmt_pct", "fmt_k"]

# 单色蓝渐变：浅底 → 深蓝。不用彩虹色阶（第 12.5 条）：
# 彩虹色阶在灰度打印时顺序会乱，而深浅蓝不会。
BLUE_CMAP = LinearSegmentedColormap.from_list(
    "hotel_blue", ["#F7FAFD", "#DCEAF5", "#A9CDE6", "#7FB3D9", "#4A93C4", "#1D6FA5", "#174E73"])


def fmt_pct(v: float, digits: int = 0) -> str:
    """0.356 → "36%"。百分比的统一写法，图上的标签都用它。"""
    return f"{v * 100:.{digits}f}%"


def fmt_k(v: float) -> str:
    """13893 → "13.9k"，用于坐标轴刻度，避免五位数挤在一起。"""
    return f"{v / 1000:.1f}k" if abs(v) >= 1000 else f"{v:,.0f}"


def _ink_on(color) -> str:
    """按背景亮度选字色：深底白字、浅底深字。

    不能用"第几段"来判（i <= 1 就白字）——配色一换，第 2 段可能已经是浅蓝，
    白字直接糊在底色上。亮度阈值 0.55 对蓝、灰、琥珀都够用。
    """
    r, g, b = to_rgb(color)
    return "white" if 0.299 * r + 0.587 * g + 0.114 * b < 0.55 else INK


def hbar(ax, labels, values, *, errors=None, colors=None, value_fmt="{:,.0f}",
         annotate=True, pad_ratio=0.02, label_size=9):
    """横向条形：默认按传入顺序从上往下画，条形末端标数值。

    为什么统一用横向：分组名是中文（"线下旅行社/旅游运营商"），
    竖着放会挤成一团或被迫旋转 45°，读起来要歪头。
    误差线给的是 95% 区间，传 errors=(low, high) 或单侧半宽数组。
    """
    y = np.arange(len(labels))
    vals = np.asarray(values, dtype=float)
    cols = colors if colors is not None else MAIN
    ax.barh(y, vals, color=cols, height=0.62, zorder=2)
    if errors is not None:
        lo, hi = errors if isinstance(errors, tuple) else (np.zeros_like(vals), errors)
        ax.errorbar(vals, y, xerr=[vals - np.asarray(lo), np.asarray(hi) - vals],
                    fmt="none", ecolor=GRAY_DARK, elinewidth=1, capsize=0, zorder=3)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()                      # 第一行在最上面，跟表格的阅读顺序一致
    ax.grid(False)                         # 横向条形不需要网格：条长本身就是刻度
    if annotate:
        span = np.nanmax(vals) - min(0, np.nanmin(vals))
        for yi, v in zip(y, vals):
            if np.isnan(v):
                continue
            ax.text(v + span * pad_ratio, yi, value_fmt.format(v), va="center",
                    ha="left", fontsize=label_size, color=INK)
        ax.set_xlim(0, np.nanmax(vals) * (1 + pad_ratio * 4))


def grouped_hbar(ax, labels, series, *, colors=None, value_fmt="{:+.1f}",
                 label_size=8.5, height=0.34, zero_line=True):
    """分组横向条形：每个 label 一组，series 里每个键一根条。

    用来放"同一个分组在两个口径下的值"（例如结构效应 vs 组内效应）。
    与 dumbbell 的分工：哑铃适合"两个时点的同一个量"，分组条适合"两个不同含义的量"。

    条末端标数值：正的标在右边、负的标在左边，否则负数标签会压在零线上。
    """
    n = len(series)
    y = np.arange(len(labels))
    span = (np.arange(n) - (n - 1) / 2) * height
    cols = colors if colors is not None else BLUES
    for i, (name, vals) in enumerate(series.items()):
        v = np.asarray(vals, dtype=float)
        ax.barh(y + span[i], v, height=height, color=cols[i % len(cols)],
                label=str(name), zorder=2)
        for yi, vi in zip(y + span[i], v):
            ax.text(vi + (0.15 if vi >= 0 else -0.15), yi, value_fmt.format(vi),
                    va="center", ha="left" if vi >= 0 else "right",
                    fontsize=label_size, color=INK)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    if zero_line:
        ax.axvline(0, color=GRAY_DARK, linewidth=1, zorder=1)
    # 两侧留白给条末标签：负值的标签写在左边，不留白会被裁掉
    lo, hi = float(min(0, np.nanmin([np.min(v) for v in series.values()]))), \
        float(max(0, np.nanmax([np.max(v) for v in series.values()])))
    span = hi - lo
    ax.set_xlim(lo - span * 0.18, hi + span * 0.18)
    ax.grid(False)
    ax.legend(frameon=False, fontsize=9, loc="upper left")


def share_bar(ax, table, *, colors=None, label_threshold=6.0, label_size=8.5,
              legend=True):
    """100% 堆叠条：table 的行是一个个组，列是构成类别，格子是百分比。

    只在占比 ≥ label_threshold 的段里写数字：小段写字会糊成一团，
    它们的准确值由旁边的表提供，图上只需要看形状。

    行序**不由本函数决定**：传进来的表是什么顺序就画什么顺序。
    曾经想在这里按行合计排序，但堆叠表每行都等于 100，排了等于没排。
    要按样本量或某一段的占比排，调用方先 table.sort_values(...) 再传进来。
    """
    cols = colors if colors is not None else BLUES
    left = np.zeros(len(table))
    y = np.arange(len(table))
    for i, col in enumerate(table.columns):
        w = table[col].to_numpy(dtype=float)
        ax.barh(y, w, left=left, color=cols[i % len(cols)], height=0.62,
                label=str(col), zorder=2)
        for yi, wi, li in zip(y, w, left):
            if wi >= label_threshold:
                ax.text(li + wi / 2, yi, f"{wi:.0f}", ha="center", va="center",
                        fontsize=label_size, color=_ink_on(cols[i % len(cols)]))
        left += w
    ax.set_yticks(y, table.index)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")   # 轴是百分比，刻度上就写明白
    ax.grid(False)
    if legend:
        ax.legend(ncol=min(len(table.columns), 5), loc="upper center",
                  bbox_to_anchor=(0.5, -0.08), frameon=False, fontsize=9)


def heat(ax, matrix, *, counts=None, fmt="{:.0%}", min_cell=None, cmap=None,
         cbar=True, fig=None, label_size=8.5, empty_color="#F2F4F7"):
    """热力矩阵：行/列都是分类，格子里是比率，格子上直接写数值。

    counts 给了就做样本抑制：样本 < min_cell 的格子涂灰、不写数，
    否则一张 3 单的格子会显示 100%，比空白更误导。
    NaN 也走同一条灰格逻辑。
    """
    m = np.array(matrix, dtype=float)
    shown = m.copy()
    if counts is not None and min_cell is not None:
        c = np.array(counts, dtype=float)
        shown = np.where(c >= min_cell, shown, np.nan)
    masked = np.ma.masked_invalid(shown)
    cm = cmap if cmap is not None else BLUE_CMAP.copy()
    cm.set_bad(empty_color)
    im = ax.imshow(masked, cmap=cm, aspect="auto")
    ax.set_xticks(np.arange(matrix.shape[1]), [str(c) for c in matrix.columns],
                  rotation=0)
    ax.set_yticks(np.arange(matrix.shape[0]), [str(i) for i in matrix.index])
    ax.set_xticks(np.arange(-.5, matrix.shape[1], 1), minor=True)
    ax.set_yticks(np.arange(-.5, matrix.shape[0], 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", length=0)
    ax.grid(which="major", visible=False)

    vmax = np.nanmax(shown) if np.isfinite(np.nanmax(shown)) else 1
    vmin = np.nanmin(shown) if np.isfinite(np.nanmin(shown)) else 0
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = shown[i, j]
            if not np.isfinite(v):
                ax.text(j, i, "—", ha="center", va="center", color=FAINT, fontsize=label_size)
                continue
            dark = (v - vmin) / (vmax - vmin + 1e-12) > 0.55
            ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=label_size,
                    color="white" if dark else INK)
    if cbar and fig is not None:
        cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
        cb.outline.set_visible(False)
        cb.ax.tick_params(labelsize=8)
    return im


def pareto(ax, labels, values, *, cum=None, colors=None, value_fmt=fmt_k,
           cum_fmt="{:.0%}", label_size=8.5):
    """帕累托：柱=规模，折线=累计占比，80% 处画一条参考线。

    双轴在这里是必要的：规模与累计占比量纲不同，但**只有一个 y 轴会被读错**。
    为减少误读，右轴只保留 0/50/80/100 四个刻度，并给累计线单独配色与直接标注。
    """
    x = np.arange(len(labels))
    vals = np.asarray(values, dtype=float)
    ax.bar(x, vals, color=colors if colors is not None else MAIN_MID, width=0.62, zorder=2)
    ax.set_xticks(x, labels, rotation=0, fontsize=9)
    ax.set_ylabel("记录数（条）")
    ax.yaxis.set_major_formatter(lambda v, _: value_fmt(v))

    if cum is not None:
        ax2 = ax.twinx()
        c = np.asarray(cum, dtype=float)
        ax2.plot(x, c * 100, color=MAIN_DARK, marker="o", markersize=4, linewidth=1.6, zorder=3)
        ax2.set_ylim(0, 118)                # 顶部留白给标签，否则 100% 会顶到边框
        ax2.set_yticks([0, 50, 80, 100], ["0", "50%", "80%", "100%"])
        ax2.axhline(80, color=GRAY_DARK, linewidth=0.9, linestyle=(0, (4, 3)), zorder=1)
        ax2.tick_params(axis="y", labelsize=8.5)
        ax2.spines["top"].set_visible(False)
        for xi, ci in zip(x, c):
            ax2.annotate(cum_fmt.format(ci), (xi, ci * 100), textcoords="offset points",
                         xytext=(0, 9), ha="center", fontsize=label_size, color=MAIN_DARK)
        # 右轴只留 0/50/80/100 四个刻度；80% 线用灰不用红——红留给"警示结论"，这里只是参考线


def waterfall(ax, labels, deltas, *, start=0.0, start_label=None, unit="%",
              value_fmt="{:+.1f}", colors=None, label_size=9):
    """瀑布图：从 start 出发，逐个加减，最后落在 start+Σdeltas。

    连接线必须画：没有它，瀑布就是一堆悬空的柱子，
    读者要靠脑补把"上一根的顶"和"这一根的底"连起来。
    start_label 给了就补一根"起点"柱——否则读者看到第一根从 25.9 悬空起跳，
    会以为图被裁掉了。
    """
    d = np.asarray(deltas, dtype=float)
    n = len(d)
    bottoms, heights, tops = [], [], []
    cur = start
    for v in d:
        bottoms.append(min(cur, cur + v))
        heights.append(abs(v))
        cur += v
        tops.append(cur)

    c = colors if colors is not None else [MAIN if v >= 0 else GRAY_DARK for v in d]
    if start_label:
        ax.bar(0, start, color=GRAY, width=0.6, zorder=2)
        ax.text(0, start, f"{start:.1f}{unit}", ha="center", va="bottom",
                fontsize=label_size, color=INK)
        x_delta = np.arange(1, n + 1)
        x_total = n + 1
    else:
        x_delta = np.arange(n)
        x_total = n
    ax.bar(x_delta, heights, bottom=bottoms, color=c, width=0.6, zorder=2)
    ax.bar(x_total, cur, color=MAIN_DARK, width=0.6, zorder=2)

    for i, (b, h, v) in enumerate(zip(bottoms, heights, d)):
        ax.text(x_delta[i], b + h, value_fmt.format(v), ha="center", va="bottom",
                fontsize=label_size, color=INK)
        left_edge = x_delta[i] - 0.3
        prev_top = start if i == 0 else tops[i - 1]
        ax.plot([left_edge - 0.4, left_edge], [prev_top] * 2, color=FAINT,
                linewidth=0.8, linestyle=(0, (2, 2)), zorder=1)
    ax.text(x_total, cur, f"{cur:.1f}{unit}", ha="center", va="bottom",
            fontsize=label_size + 0.5, color=MAIN_DARK, fontweight="bold")

    ticks = ([start_label] if start_label else []) + list(labels) + ["合计"]
    ax.set_xticks([*((0,) if start_label else ()), *x_delta, x_total], ticks, fontsize=9)
    ax.set_ylabel(f"取消率（{unit}）" if unit == "%" else unit)
    ax.grid(axis="x", visible=False)


def dumbbell(ax, labels, left, right, *, left_name="A", right_name="B",
             color_left=GRAY_DARK, color_right=MAIN, label_size=8.5,
             value_fmt="{:.0%}"):
    """哑铃图：同一分组在两个时点/两种口径下的值，用一条线连起来。

    比并排双柱好在"差值"直接就是线段长度，读者不用自己减。
    """
    y = np.arange(len(labels))
    l, r = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    for yi, li, ri in zip(y, l, r):
        ax.plot([li, ri], [yi, yi], color=GRAY, linewidth=2.2, zorder=1, solid_capstyle="round")
    ax.scatter(l, y, s=46, color=color_left, zorder=3, label=left_name)
    ax.scatter(r, y, s=46, color=color_right, zorder=3, label=right_name)
    for yi, li, ri in zip(y, l, r):
        ax.text(max(li, ri) + 0.012, yi, f"{value_fmt.format(li)} → {value_fmt.format(ri)}",
                va="center", fontsize=label_size, color=INK)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    # 右侧留白：数值标签写在最右点之后，不留白会被画布裁掉（D03 第一稿就踩了）
    span = max(r.max(), l.max()) - min(r.min(), l.min())
    ax.set_xlim(min(l.min(), r.min()) - span * 0.08, max(l.max(), r.max()) + span * 0.55)
    # 图例放右上角：数据点都压在左侧，右上是唯一不会压住东西的位置
    ax.legend(frameon=False, fontsize=9, loc="upper right")


def quadrant(ax, xs, ys, labels, *, x_name="影响面", y_name="可干预程度",
             x_mid=None, y_mid=None, colors=None, label_size=9, size=90,
             y_ticks=None):
    """2×2 象限图：每个点一个因素，横纵轴各一个判据，虚线分四块。

    象限图不是"算出来的"：横轴可以用超额取消单（可算），
    但纵轴"可干预程度"是业务打分（人为），必须在副标题里写明打分依据。

    y_ticks 给 (位置列表, 标签列表) 时，纵轴按档位显示文字（结构性/混合/可干预），
    比露出 0.15、0.6、0.9 这种人为分值更像结论。
    """
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    xm = np.median(x) if x_mid is None else x_mid
    ym = np.median(y) if y_mid is None else y_mid
    ax.axvline(xm, color=GRAY, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    ax.axhline(ym, color=GRAY, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
    ax.scatter(x, y, s=size, color=colors if colors is not None else MAIN,
               alpha=0.85, zorder=3, edgecolor="white", linewidth=1.2)

    # 同一横档上的标签交错排：最低档只能朝上（朝下会压住 x 轴刻度），
    # 最高档只能朝下（朝上会顶出画布），中间档正常上下交替
    layers: dict[float, list[int]] = {}
    for i, yi in enumerate(y):
        layers.setdefault(float(yi), []).append(i)
    ymin, ymax = float(np.min(y)), float(np.max(y))
    offsets = {}
    for yv, idxs in layers.items():
        idxs.sort(key=lambda i: x[i])
        for k, i in enumerate(idxs):
            if yv == ymin:
                offsets[i] = (0, 14) if k % 2 == 0 else (0, 32)
            elif yv == ymax:
                offsets[i] = (0, -22) if k % 2 == 0 else (0, -40)
            else:
                offsets[i] = (0, 13) if k % 2 == 0 else (0, -21)
    for i, (xi, yi, li) in enumerate(zip(x, y, labels)):
        ax.annotate(li, (xi, yi), textcoords="offset points", xytext=offsets[i],
                    ha="center", fontsize=label_size, color=INK)

    ax.set_xlabel(x_name)
    ax.set_ylabel(y_name)
    ax.margins(x=0.10, y=0.16)
    if y_ticks is not None:
        pos, lab = y_ticks
        ax.set_yticks(pos, lab)
        ax.set_ylim(min(min(pos), y.min()) - 0.12, max(max(pos), y.max()) + 0.12)

    # 四角提示写在轴外：写在轴内会压住数据点，这版第一稿就踩了这个坑。
    # 只标右侧两角——左侧的"影响小"不改变决策，标出来反而抢注意力。
    ax.text(1.0, 1.02, "影响大 · 可控（优先做）", transform=ax.transAxes,
            fontsize=8, color=MAIN_DARK, va="bottom", ha="right", clip_on=False)
    ax.text(1.0, -0.16, "影响大 · 难控（只能适应）", transform=ax.transAxes,
            fontsize=8, color=FAINT, va="top", ha="right", clip_on=False)
