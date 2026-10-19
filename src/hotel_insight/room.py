#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : room.py
# @Path       : analyse/src/hotel_insight/room.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 10:05:00
# @Version    : v1.0.0
# @Description: 房型结构：房型画像、房型与客源/酒店类型的交叉、换房流向。
# @ChangeLog:
#   2026-10-19 10:05:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
只会因为"房型口径变了（取前几种、交叉维度、换房怎么判）"而改（AGENTS.md 第 2 条）。
不读库、不读文件、不 import viz（第 4 条 4.1）。

两个必须写在函数里的前提：
1. **没有房型字典**。数据里只有 A—P 单字母，没有"标准双床/家庭房"的对应关系，
   所以任何"房型价值"结论都只能按代码比较，不能翻译成房型名称（DQ-16）。
2. **不能拿换房解释取消**。assigned_room_type 是入住时分配的，取消的订单根本没到店，
   它的 assigned 值不代表"如果来了会住哪"。换房与取消的关系是幸存者偏差，
   upgrade_flow() 只统计未取消单，并在文档里把这一点说死。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import rate

__all__ = ["room_table", "room_by", "upgrade_flow", "cancel_matrix",
           "ROOM_COLS"]

ROOM_COLS = ["记录数", "占比", "取消率", "下限", "上限", "平均房价", "平均停留",
             "平均提前期", "换房率"]


def room_table(df: pd.DataFrame, *, min_n: int = 30) -> pd.DataFrame:
    """按预订房型汇总，索引是房型代码，按记录数降序。

    换房率只在**未取消**的订单里算：取消单没有真实入住，谈不上"换了哪间房"。
    这也是全表唯一一处能算换房率的地方，别的模块不要自己再算一遍。
    """
    t = rate.rate_table(df, "reserved_room_type", min_n=min_n)
    stats = df.groupby("reserved_room_type", observed=True).agg(
        平均房价=("adr", "mean"), 平均停留=("total_nights", "mean"),
        平均提前期=("lead_time", "mean"))
    stayed = df[df["is_canceled"] == 0]
    moved = (stayed["assigned_room_type"] != stayed["reserved_room_type"]).groupby(
        stayed["reserved_room_type"], observed=True).mean()
    t["平均房价"] = stats["平均房价"].reindex(t.index)
    t["平均停留"] = stats["平均停留"].reindex(t.index)
    t["平均提前期"] = stats["平均提前期"].reindex(t.index)
    t["换房率"] = moved.reindex(t.index)
    return t[ROOM_COLS]


def room_by(df: pd.DataFrame, dim: str, *, top_rooms: int = 6,
            min_n: int = 30) -> pd.DataFrame:
    """房型 × dim 的行内占比（%），给 100% 堆叠条用。

    只保留记录数前 top_rooms 的房型：A—H 之后（L、P 等）合计不到 0.1%，
    留在堆叠条里会变成看不见的发丝线。
    """
    keep = df["reserved_room_type"].value_counts().head(top_rooms).index
    sub = df[df["reserved_room_type"].isin(keep)]
    tab = pd.crosstab(sub["reserved_room_type"], sub[dim], normalize="index") * 100
    counts = sub["reserved_room_type"].value_counts()
    # 用 .loc 取索引而不是布尔掩码：counts 的顺序来自 value_counts（按行数降序），
    # 与 tab 的行序不一定一致，直接传布尔 Series 会触发隐式 reindex（pandas 会给警告，
    # 顺序不巧时还会静默取错行）
    return tab.loc[counts[counts >= min_n].index]


def upgrade_flow(df: pd.DataFrame) -> pd.DataFrame:
    """预订房型 → 实际分到的房型，只统计未取消订单；返回长表（预订、实际、单数、占比）。

    为什么只看未取消：取消单的 assigned_room_type 不是"真实分配"，
    把它算进来会得到"换过房的订单取消率 4.7%"这种荒谬结论
    （真实原因：换房只发生在到店的客人身上，而到店的客人本来就没取消）。
    """
    stayed = df[df["is_canceled"] == 0]
    g = (stayed.groupby(["reserved_room_type", "assigned_room_type"], observed=True)
         .size().rename("单数").reset_index())
    g["占比"] = g["单数"] / len(stayed)
    return g.sort_values("单数", ascending=False)


def cancel_matrix(df: pd.DataFrame, index: str, columns: str, *,
                  min_cell_n: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    """交叉取消率矩阵，返回 (比率, 样本数)。样本少于 min_cell_n 的格子比率置 NaN。

    两个矩阵一起返回是故意的：图上一格 100% 取消率、旁边标着 n=1，
    和 n=200 的 100% 是两回事；只给比率会让人读错。
    """
    r = df.pivot_table(index=index, columns=columns, values="is_canceled", aggfunc="mean")
    n = df.pivot_table(index=index, columns=columns, values="is_canceled", aggfunc="size")
    r = r.where(n >= min_cell_n)
    return r, n.fillna(0).astype(int)
