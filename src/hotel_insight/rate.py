#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : rate.py
# @Path       : analyse/src/hotel_insight/rate.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 09:10:00
# @Version    : v1.1.0
# @Description: 比率估计与结构分解：分组取消率带置信区间、Kitagawa 三分解。
# @ChangeLog:
#   2026-10-19 09:10:00 | 一班第十二组 | v1.0.0 | 从 cancel 中拆出，供 origin/timing/room 共用
#   2026-10-19 10:40:00 | 一班第十二组 | v1.1.0 | 复核时误以为 nested_kitagawa 无人调用而删, 已恢复: D06 cell 11 在用(输出为表, 不是图, 首轮扫描漏判)
"""
只会因为"统计口径或分解方法变了"而改（AGENTS.md 第 2 条）。
这里的函数只做三件事：比率怎么估、区间怎么给、两个时点的差异怎么拆。
不读库、不读文件、不 import viz（第 4 条 4.1）。

为什么单开一个模块，而不是塞进 cancel.py：
客源结构、时间节奏、房型差异三本 notebook 都要给"取消率 ± 区间"，
如果放在 cancel.py，origin 就要 import cancel，依赖方向会变成环（第 3 条）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["wilson", "rate_table", "kitagawa", "nested_kitagawa", "RATE_COLS"]

RATE_COLS = ["分组", "记录数", "取消单数", "取消率", "下限", "上限", "占比"]


def wilson(k, n, z: float = 1.96) -> tuple[np.ndarray, np.ndarray]:
    """Wilson 区间：比例 k/n 的 95% 置信区间，返回 (下限, 上限)。

    为什么不用正态近似 p±1.96·√(p(1-p)/n)：小样本或比例接近 0 时它会给负下限。
    为什么不用 Clopper-Pearson：Wilson 在 n≥30 时已经够准，且不需要 scipy
    （本环境没装 scipy，装它只为算一个区间不划算）。

    坑：n=0 时返回 (nan, nan) 而不是抛错——热力矩阵里有空格子是常态，
    调用方自己决定要不要显示。
    """
    k = np.asarray(k, dtype=float)
    n = np.asarray(n, dtype=float)
    p = np.divide(k, n, out=np.full_like(k, np.nan), where=n > 0)
    denom = 1 + z**2 / np.where(n > 0, n, np.nan)
    center = p + z**2 / (2 * np.where(n > 0, n, np.nan))
    margin = z * np.sqrt(np.divide(p * (1 - p), np.where(n > 0, n, np.nan))
                         + z**2 / (4 * np.where(n > 0, n, np.nan) ** 2))
    lo = np.where(n > 0, (center - margin) / denom, np.nan)
    hi = np.where(n > 0, (center + margin) / denom, np.nan)
    return np.clip(lo, 0, 1), np.clip(hi, 0, 1)


def rate_table(df: pd.DataFrame, by: str | list[str], *, min_n: int = 0,
               sort: str = "记录数", ascending: bool = False) -> pd.DataFrame:
    """按 by 分组算取消率，附 95% 区间与占比。返回 RATE_COLS 列，索引是分组名。

    min_n：样本少于它的组**保留**但取消率置空（不是删掉）——图上一眼能看出
    "这组没有证据"，比悄悄消失诚实。这是小样本抑制（docs/图表规范.md 第 4 节）。
    sort：默认按记录数降序；给 "取消率" 就按比率排，方便找极端组。
    """
    cols = [by] if isinstance(by, str) else list(by)
    key = cols[0] if len(cols) == 1 else cols
    g = df.groupby(key, dropna=False).agg(记录数=("is_canceled", "size"),
                                          取消单数=("is_canceled", "sum"))
    g["取消率"] = g["取消单数"] / g["记录数"]
    lo, hi = wilson(g["取消单数"], g["记录数"])
    g["下限"], g["上限"] = lo, hi
    g["占比"] = g["记录数"] / len(df)
    if min_n:
        thin = g["记录数"] < min_n
        g.loc[thin, ["取消率", "下限", "上限"]] = np.nan
    g = g.reset_index()
    # 单列分组时索引就是分组名；多列分组拼成一列，图上的标签才不会丢维度
    if len(cols) == 1:
        g = g.rename(columns={cols[0]: "分组"})
    else:
        g["分组"] = g[cols].astype(str).agg(" / ".join, axis=1)
        g = g.drop(columns=cols)
    if sort in g.columns:
        g = g.sort_values(sort, ascending=ascending, kind="mergesort")
    return g[RATE_COLS].set_index("分组")


def _key(s: pd.Series, label: str = "（缺失）") -> pd.Series:
    """把分组键里的缺失值变成一个真实取值，供 kitagawa 用。

    坑：value_counts 与 groupby 默认都丢 NaN，两边的占比合计都小于 1，
    三块就拼不回总变化——本项目的客源国恰好缺 0.41%，实测缺口 0.06pp，
    断言直接失败。这不是浮点噪声，是口径漏了一组。

    categorical（提前期分箱）必须先补类别再填：fillna 一个不在类别里的值会抛错。
    """
    if not s.isna().any():
        return s
    if isinstance(s.dtype, pd.CategoricalDtype):
        if label in s.cat.categories:
            return s.fillna(label)
        return s.cat.add_categories([label]).fillna(label)
    return s.fillna(label).astype(object)


def kitagawa(a: pd.DataFrame, b: pd.DataFrame, by: str) -> dict:
    """两个时点 a→b 的取消率差异，按 by 拆成结构效应、组内效应、交互效应（单位：百分点）。

    恒等式：总变化 = 结构 + 组内 + 交互。三个数加起来必须等于 b−a，
    否则说明有分组的占比没覆盖全（比如 a 有、b 没有的组被丢了），函数会断言失败。

    怎么读这三个数：
      · 结构效应 > 0：客源/渠道的**构成**变了（比如 OTA 占比从 44% 涨到 66%），
        即使每组的行为没变，总取消率也会上升——这部分酒店短期改不了；
      · 组内效应 > 0：同一个渠道内部的取消率真的变高了，
        这部分才可能是服务、政策、竞争环境的变化；
      · 交互项：构成与比率同时变化带来的交叉部分，报告时单独列出，不硬摊到前两项。

    a、b 是同一口径的两批行（用 timing.comparable_slice 取同月份，别拿全年比半年）。
    """
    # 空值先变成"（缺失）"这个真实分组，否则占比合计不到 1，三块拼不回总变化
    a = a.assign(**{by: _key(a[by])})
    b = b.assign(**{by: _key(b[by])})
    sa = a[by].value_counts(normalize=True)
    sb = b[by].value_counts(normalize=True)
    ra = a.groupby(by, observed=True)["is_canceled"].mean()
    rb = b.groupby(by, observed=True)["is_canceled"].mean()
    idx = sa.index.union(sb.index)
    sa, sb = sa.reindex(idx, fill_value=0), sb.reindex(idx, fill_value=0)
    ra, rb = ra.reindex(idx, fill_value=0), rb.reindex(idx, fill_value=0)

    structure = float(((sb - sa) * ra).sum() * 100)
    within = float((sa * (rb - ra)).sum() * 100)
    interaction = float(((sb - sa) * (rb - ra)).sum() * 100)
    total = float((b["is_canceled"].mean() - a["is_canceled"].mean()) * 100)
    parts = structure + within + interaction

    # 对账：三块必须拼回总变化。误差只允许是浮点噪声（1e-9 级）
    assert abs(parts - total) < 1e-6, (
        f"分解没闭合：结构 {structure:.4f} + 组内 {within:.4f} + 交互 {interaction:.4f} "
        f"= {parts:.4f}，但总变化是 {total:.4f}；检查 {by} 是否有空值或未覆盖的组"
    )
    return {"结构效应": structure, "组内效应": within, "交互效应": interaction,
            "总变化": total, "起点": float(a["is_canceled"].mean() * 100),
            "终点": float(b["is_canceled"].mean() * 100)}


def nested_kitagawa(a: pd.DataFrame, b: pd.DataFrame, outer: str, inner: str) -> pd.DataFrame:
    """两层分解：先按 outer 分组，再在每个组内按 inner 拆结构与组内，返回长表。

    为什么需要第二层：按渠道拆完得到"组内 +5.0pp"，但这 5pp 里可能还有一半是
    "同一个渠道的订单，预订窗口变长了"，而不是"服务变差了"。
    一层分解到此为止，二层才能回答"到底是哪个结构在变"。

    列：外层组、结构效应、组内效应、交互效应、总变化、起点、终点、记录数。
    某个外层组在 b 里没有样本时跳过（不做 0 除）。
    """
    rows = []
    for name, ga in a.groupby(outer, observed=True):
        gb = b[b[outer] == name]
        if gb.empty:
            continue
        d = kitagawa(ga, gb, inner)
        rows.append({"外层组": name, **{k: round(v, 2) for k, v in d.items()},
                     "记录数": len(ga) + len(gb)})
    return pd.DataFrame(rows).set_index("外层组").sort_values("记录数", ascending=False)
