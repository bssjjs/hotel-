#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : origin.py
# @Path       : analyse/src/hotel_insight/origin.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 09:30:00
# @Version    : v1.0.0
# @Description: 客源结构：国别、市场细分、渠道、客群的规模与集中度。
# @ChangeLog:
#   2026-10-19 09:30:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
只会因为"客源口径变了（国家怎么归并、取前几、集中度怎么算）"而改（AGENTS.md 第 2 条）。
不读库、不读文件、不 import viz（第 4 条 4.1）。

一个必须先说清的前提：
这份数据**没有酒店所在城市/地区字段**，只有客源国 `country`。
所以"用户从哪来"能答，"酒店开在哪、哪个地区客源多"答不了。
origin 与 room 的交叉只能落在"客源国 × 房型"，不能写成"地区 × 房型"。
见 docs/发现清单.md 第 4 条。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import rate

__all__ = ["country_table", "concentration", "cumulative_share", "mix_table",
           "COUNTRY_COLS"]

COUNTRY_COLS = ["记录数", "占比", "累计占比", "取消率", "下限", "上限",
                "平均房价", "平均停留", "平均提前期"]


def country_table(df: pd.DataFrame, *, top_n: int = 10, min_n: int = 30,
                  other_label: str = "其他") -> pd.DataFrame:
    """客源国汇总：前 top_n 名单列，其余合并成"其他"。索引是国家名，按记录数降序。

    为什么合并"其他"：176 个国家里，后 100 个合计不到 2%，逐个画会把图撑成一条细线。
    合并后**取消率必须重算**（用合并后的单数/行数），不能对各国比率取平均——
    后者是"比率的平均"，会被小国放大（AGENTS 第 4 条：算数的地方别偷懒）。

    min_n 只作用于单个国家：样本不足的国家取消率置空，但仍占一条记录数；
    "其他"是合计，不受抑制。
    """
    total = len(df)
    ordered = df.groupby("country", observed=True)["is_canceled"].size().sort_values(ascending=False)
    keep = list(ordered.index[:top_n])

    head = df[df["country"].isin(keep)]
    tail = df[~df["country"].isin(keep)]

    t = rate.rate_table(head, "country", min_n=min_n)
    if len(tail):
        k = int(tail["is_canceled"].sum())
        lo, hi = rate.wilson(k, len(tail))
        t.loc[other_label] = [len(tail), k, k / len(tail), float(lo), float(hi), len(tail) / total]
    # "其他"永远排最后：它是兜底集合，混在头部国家中间会让帕累托曲线出现假台阶
    order = [c for c in t.index if c != other_label]
    if other_label in t.index:
        order.append(other_label)
    t = t.reindex(order)
    # 占比的分母是**全量**，不是"前 N 名这几行的合计"：
    # rate_table 的占比默认按传入行算，这里必须换回全量，否则前 8 国会加起来等于 100%
    t["占比"] = t["记录数"] / total

    # 累计占比给帕累托用：从最大的国家往下加，看"几个国家覆盖了 80%"
    t["累计占比"] = t["占比"].cumsum()
    stats = df.groupby("country", observed=True).agg(
        平均房价=("adr", "mean"), 平均停留=("total_nights", "mean"), 平均提前期=("lead_time", "mean"))
    t["平均房价"] = stats["平均房价"].reindex(t.index)
    t["平均停留"] = stats["平均停留"].reindex(t.index)
    t["平均提前期"] = stats["平均提前期"].reindex(t.index)
    if other_label in t.index:
        t.loc[other_label, ["平均房价", "平均停留", "平均提前期"]] = [
            tail["adr"].mean(), tail["total_nights"].mean(), tail["lead_time"].mean()]
    return t[COUNTRY_COLS]


def concentration(df: pd.DataFrame, by: str) -> dict:
    """集中度：组数、HHI、第一大与前三/前十占比。

    HHI（赫芬达尔指数）= Σ 份额²，取值 0—1（这里用 0—1，不是乘 10000 的版本）。
    为什么给 HHI 而不只给"前三占比"：前三占比相同，可能是"3 家各 20%"，
    也可能是"1 家 50% + 2 家各 5%"，风险完全不同；HHI 对头部更敏感。
    """
    shares = df[by].value_counts(normalize=True)
    return {
        "组数": int(len(shares)),
        "HHI": float((shares ** 2).sum()),
        "第一大占比": float(shares.iloc[0]) if len(shares) else float("nan"),
        "前三占比": float(shares.iloc[:3].sum()),
        "前十占比": float(shares.iloc[:10].sum()),
    }


def cumulative_share(values) -> np.ndarray:
    """把一组规模值变成累计占比（0—1），用于洛伦兹/帕累托曲线。

    输入顺序就是画图顺序，函数不排序——排序是分析判断，留在调用方，
    否则"按记录数排"和"按取消率排"两种图会拿到同一个结果，图上就看不出差别了。
    """
    v = np.asarray(values, dtype=float)
    if v.sum() <= 0:
        return np.zeros_like(v)
    return np.cumsum(v) / v.sum()


def mix_table(df: pd.DataFrame, index: str, columns: str, *,
              min_n: int = 0) -> pd.DataFrame:
    """交叉占比表：行是 index，列是 columns 的取值，格子里是行内占比（%）。

    给 100% 堆叠条用。min_n 过滤的是**行**的记录数，不是格子——
    一行只有 12 条时，把它拆成 9 个房型的占比没有意义。

    不自动排序：按记录数排还是按 A 房型占比排，是分析判断，留在调用方。
    """
    tab = pd.crosstab(df[index], df[columns])
    if min_n:
        tab = tab[tab.sum(axis=1) >= min_n]
    return (tab.div(tab.sum(axis=1), axis=0) * 100).round(1)
