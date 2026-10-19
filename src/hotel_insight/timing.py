#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : timing.py
# @Path       : analyse/src/hotel_insight/timing.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 09:50:00
# @Version    : v1.0.0
# @Description: 时间节奏：日历矩阵、月度季节指数、周内分布、提前期与停留时长分档。
# @ChangeLog:
#   2026-10-19 09:50:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
只会因为"时间口径变了（分箱边界、同比取哪几个月、季节指数怎么算）"而改（AGENTS.md 第 2 条）。
不读库、不读文件、不 import viz（第 4 条 4.1）。

本模块反复处理一个坑：**这份数据不是完整日历**。
2015 只有 7—12 月（6 个月），2016 全年，2017 只有 1—8 月（8 个月）。
所以任何"年度对比"都必须先用 comparable_slice 取两年都有的月份，
直接拿 2016 全年比 2017 年前 8 个月，会把"少了 4 个月"读成"业务下滑"。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import rate

__all__ = ["calendar_matrix", "month_profile", "dow_profile", "binned_profile",
           "comparable_slice", "season_index", "PROFILE_COLS"]

PROFILE_COLS = ["记录数", "占比", "取消率", "下限", "上限"]
DOW_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def calendar_matrix(df: pd.DataFrame, value: str = "is_canceled",
                    agg: str = "mean") -> pd.DataFrame:
    """年 × 月的矩阵，行是 arrival_year，列是 1—12 月。

    缺失月份留 NaN（不是 0）：颜色上做"无数据"处理，别让一张热力图把
    "2015 年 1 月没数据"画成"那天没有取消"。
    agg="size" 得到记录数，agg="mean" 得到取消率。
    """
    tab = df.pivot_table(index="arrival_year", columns="arrival_month_no",
                         values=value, aggfunc=agg)
    return tab.reindex(columns=range(1, 13))


def month_profile(df: pd.DataFrame) -> pd.DataFrame:
    """按自然月汇总：记录数、占比、累计占比、取消率。索引是"1 月"…"12 月"。"""
    t = rate.rate_table(df, "arrival_month_no", sort="分组", ascending=True)
    t["月名"] = [f"{int(m)} 月" for m in t.index]
    t = t.set_index("月名")
    t["累计占比"] = t["占比"].cumsum()
    return t[["记录数", "占比", "累计占比", "取消率", "下限", "上限"]]


def dow_profile(df: pd.DataFrame) -> pd.DataFrame:
    """按到达日期的星期几汇总。

    数据里没有"星期"字段，只有 arrival_date；星期由日期算出来，
    所以这一步依赖 arrival_date 已经正确（DQ-05 查过）。
    """
    d = df.assign(到达星期=pd.to_datetime(df["arrival_date"]).dt.dayofweek.map(dict(enumerate(DOW_LABELS))))
    t = rate.rate_table(d, "到达星期")
    return t.reindex(DOW_LABELS)[PROFILE_COLS]


def binned_profile(df: pd.DataFrame, col: str, bins: list, labels: list, *,
                   name: str = "分组") -> pd.DataFrame:
    """把连续量分档后汇总（记录数、占比、取消率、区间）。

    bins 用左开右闭 (a, b]，第一档用 include_lowest 把最小值包进来：
    这样 lead_time=0（当天订当天到）落在"7 天内"，不会被切成 NaN。
    标签顺序就是显示顺序，不按记录数重排——提前期是有序变量，
    按记录数排会把"7 天内→365 天以上"的梯度打乱。
    """
    cut = pd.cut(df[col], bins=bins, labels=labels, include_lowest=True)
    t = rate.rate_table(df.assign(**{name: cut}), name)
    t = t.reindex(labels)
    t["记录数"] = t["记录数"].fillna(0).astype(int)
    t["占比"] = t["占比"].fillna(0.0)
    t["累计占比"] = t["占比"].cumsum()
    return t[["记录数", "占比", "累计占比", *PROFILE_COLS[2:]]]


def comparable_slice(df: pd.DataFrame, years: list, months: list) -> pd.DataFrame:
    """取"指定年份 ∩ 指定月份"的行，用于同比。

    2016 与 2017 的 1—8 月是唯一可比的窗口（2017 缺 9—12 月）。
    返回的是原表的子集，不改列、不改索引。
    """
    return df[df["arrival_year"].isin(years) & df["arrival_month_no"].isin(months)].copy()


def season_index(df: pd.DataFrame, year: int) -> pd.Series:
    """某一年各月的季节指数 = 该月记录数 / 该年月均记录数；1.0 表示与平均持平。

    只接受**完整年**（2016）：拿不完整的年份算季节指数，1 月会凭空变成淡季。
    这条限制写在函数里而不是注释里，用错年份直接抛错，比图上解释便宜。
    """
    g = df[df["arrival_year"] == year].groupby("arrival_month_no").size()
    if len(g) != 12:
        raise ValueError(f"{year} 年只有 {len(g)} 个月的数据，不能算季节指数；完整年只有 2016")
    return (g / g.mean()).reindex(range(1, 13))
