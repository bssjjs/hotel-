#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : cancel.py
# @Path       : analyse/src/hotel_insight/cancel.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 10:30:00
# @Version    : v1.0.0
# @Description: 取消归因：因素影响面、取消发生时机、结构性/可干预分类与情景估算。
# @ChangeLog:
#   2026-10-19 10:30:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
只会因为"取消因素的定义、影响面算法、情景假设变了"而改（AGENTS.md 第 2 条）。
不读库、不读文件、不 import viz（第 4 条 4.1）。

**本模块不做因果推断，只做三件能说清的事**：
1. 影响面：这个因素把取消率拉开多少个百分点、涉及多少单；
2. 时机：取消发生在到达前多少天，决定还有没有干预窗口；
3. 情景：在明确写出的假设下，某类订单少取消能省多少——假设值可调，不是拟合结果。

"结构性 / 可干预"不是数据算出来的，是业务属性，写在 FACTORS 里逐条给理由。
把业务判断伪装成统计结论，是这类分析最常见的错。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import rate

__all__ = ["FACTORS", "factor_scan", "excess_cancellations", "cancellation_timing",
           "revenue_at_risk", "scenario_reconfirm", "IMPACT_COLS"]

IMPACT_COLS = ["性质", "组数", "最高组", "最高组取消率", "最低组", "最低组取消率",
               "极差(pp)", "超额取消单", "覆盖单量", "判定理由"]

# 每个因素的性质是**人定的**，理由写在同一行里，方便被反驳、被改。
# 判据只有一条：酒店在 3—6 个月内能不能改变它。
#   · 结构性：由客源地理、供给、年度合同、季节决定，酒店改不了，只能预测和适应；
#   · 可干预：酒店有动作可用（提醒、担保、引导填要求、风控政策），且成本可控；
#   · 混合：客户自己决定，但酒店的政策能改变它的后果（比如对长提前期订单加担保）；
#   · 需存疑：数据表现与直觉相反，先查口径，不放进杠杆清单。
FACTORS = [
    {"字段": "hotel_type", "名称": "酒店类型", "性质": "结构性",
     "理由": "城市/度假两家店的定位，短期不动"},
    {"字段": "country", "名称": "客源国", "性质": "结构性",
     "理由": "客源地理；可做营销引导，但要两三年才见效"},
    {"字段": "market_segment", "名称": "市场细分", "性质": "结构性",
     "理由": "渠道组合由年度合同与分销策略决定"},
    {"字段": "customer_type", "名称": "客群类型", "性质": "结构性",
     "理由": "散客/协议/团队的构成跟随销售结构"},
    {"字段": "arrival_month_no", "名称": "到达月份", "性质": "结构性",
     "理由": "季节由气候与假期决定，酒店改不了"},
    {"字段": "reserved_room_type", "名称": "房型", "性质": "结构性",
     "理由": "房型供给固定；能调的是分配与超售，不是需求"},
    {"字段": "lead_time", "名称": "提前期", "性质": "混合",
     "理由": "客户自己决定；酒店可对长提前期单加担保或再确认，改变其后果"},
    {"字段": "booking_changes", "名称": "改单次数", "性质": "混合",
     "理由": "改单是客户行为；酒店只能让改单更顺，不能强制"},
    {"字段": "total_of_special_requests", "名称": "特殊要求数", "性质": "可干预",
     "理由": "下单页引导填写，零成本；有要求=有沉没投入"},
    {"字段": "required_car_parking_spaces", "名称": "停车位需求", "性质": "可干预",
     "理由": "可主动询问并锁定车位，形成承诺；但只覆盖有车客"},
    {"字段": "previous_cancellations", "名称": "历史取消次数", "性质": "可干预",
     "理由": "可直接用于风控：高风险客户要求预付或担保"},
    {"字段": "deposit_type", "名称": "押金类型", "性质": "需存疑",
     "理由": "不可退款组取消率 94.7%，与直觉相反，先查口径再谈政策"},
]


def _collapse(s: pd.Series, min_share: float, label: str = "其他") -> pd.Series:
    """把占比低于 min_share 的取值合并成一个 label，避免 176 个国家打成 176 行。

    合并只影响展示，不影响超额取消单的计算口径：合并后的组用加权率重算。
    """
    shares = s.value_counts(normalize=True)
    keep = shares[shares >= min_share].index
    return s.where(s.isin(keep), label)


def excess_cancellations(df: pd.DataFrame, by: str, *, min_n: int = 30) -> float:
    """超额取消单数 = Σ n_i × max(0, r_i − r̄)，即"高于总体平均的那些组多出来的取消"。

    为什么不用"最高组 − 最低组"乘以总量：那等于假设所有组都能降到最低组的水平。
    停车位需求组的取消率是 0%，把它当目标会算出"可消灭全部取消"——数学上成立，
    业务上荒谬。超额法只承认"高于平均的部分"，是有下界的保守估计。

    样本不足 min_n 的组不参与（它们的 r_i 本身不可信）。
    """
    t = rate.rate_table(df, by)
    valid = t[t["记录数"] >= min_n]
    if valid.empty:
        return float("nan")
    base = df["is_canceled"].mean()
    return float((valid["记录数"] * (valid["取消率"] - base).clip(lower=0)).sum())


def factor_scan(df: pd.DataFrame, settings: dict, *,
                min_share: float = 0.005, min_n: int = 30) -> pd.DataFrame:
    """逐个因素扫描影响面，返回 IMPACT_COLS 列，按超额取消单降序。

    min_share 只用于高基数因素（客源国）：占比不足 0.5% 的取值并入"其他"，
    否则最高的那组可能只有 3 单，极差会被小样本撑大。

    提前期先按 settings 的分箱变成有序档再扫；其余因素直接用原值。
    这一步不改入参：所有派生列都建在副本上。
    """
    a = settings["analysis"]
    rows = []
    for f in FACTORS:
        col = f["字段"]
        s = df[col]
        if col == "lead_time":
            s = pd.cut(df[col], bins=a["lead_time_bins"], labels=a["lead_time_labels"],
                       include_lowest=True)
        elif pd.api.types.is_string_dtype(s) and s.nunique() > 20:
            # 只在"取值很多"的文本列上归并；pandas 3 的文本列 dtype 是 str，
            # 不是 object，用 dtype == object 判断会漏掉（踩过一次）
            s = _collapse(s, min_share)
        work = df.assign(因素=s)
        t = rate.rate_table(work, "因素", min_n=min_n)
        valid = t.dropna(subset=["取消率"])
        if len(valid) < 2:
            continue
        hi, lo = valid["取消率"].idxmax(), valid["取消率"].idxmin()
        rows.append({
            "因素": f"{f['名称']}（{col}）",
            "性质": f["性质"],
            "组数": int(len(valid)),
            "最高组": hi,
            "最高组取消率": float(valid.loc[hi, "取消率"]),
            "最低组": lo,
            "最低组取消率": float(valid.loc[lo, "取消率"]),
            "极差(pp)": float((valid.loc[hi, "取消率"] - valid.loc[lo, "取消率"]) * 100),
            "超额取消单": excess_cancellations(work, "因素", min_n=min_n),
            "覆盖单量": int(valid["记录数"].sum()),
            "判定理由": f["理由"],
        })
    out = pd.DataFrame(rows).set_index("因素")
    return out.sort_values("超额取消单", ascending=False)[IMPACT_COLS]


def cancellation_timing(df: pd.DataFrame, bins: list, labels: list) -> pd.DataFrame:
    """取消发生在"到达前多少天"的分布，只统计取消单。

    与提前期不是一回事：提前期是"订得多早"，这里是"什么时候退的"。
    干预窗口看这个：如果 60% 的取消发生在到达前 30 天之前，
    那么在 T−7 天发提醒已经来不及了。
    """
    c = df[df["is_canceled"] == 1].copy()
    c["取消提前天数"] = (pd.to_datetime(c["arrival_date"])
                         - pd.to_datetime(c["status_date"])).dt.days.clip(lower=0)
    cut = pd.cut(c["取消提前天数"], bins=bins, labels=labels, include_lowest=True)
    t = rate.rate_table(c.assign(窗口=cut), "窗口")
    t = t.reindex(labels)
    t["记录数"] = t["记录数"].fillna(0).astype(int)
    t["占比"] = t["占比"].fillna(0.0)
    t["累计占比"] = t["占比"].cumsum()
    return t[["记录数", "占比", "累计占比"]]


def revenue_at_risk(df: pd.DataFrame) -> dict:
    """取消订单的名义收入规模（adr × 晚数），以及它占全部名义收入的比例。

    口径提醒：这是**名义**收入，不是实际损失。取消后房间多半会被卖掉一部分，
    真实损失要用 RevPAR 与替代率算，本数据集没有每日房态，算不了。
    这里只回答"取消涉及的盘子有多大"，不能写成"损失了多少"。
    """
    rev = df["adr"] * df["total_nights"]
    cancelled = df["is_canceled"] == 1
    return {
        "取消单数": int(cancelled.sum()),
        "取消订单名义收入": float(rev[cancelled].sum()),
        "全部名义收入": float(rev.sum()),
        "占比": float(rev[cancelled].sum() / rev.sum()),
        "每单均值": float(rev[cancelled].mean()),
    }


def scenario_reconfirm(df: pd.DataFrame, settings: dict) -> dict:
    """情景：对提前期超过阈值的订单做一次再确认，假设其取消率相对下降 drop，能少取消多少。

    **这是情景演算，不是预测**：drop 是 settings 里的假设值（默认 10%），
    没有任何一版数据能验证"再确认一定有效"。结果要写成"若…则…"，
    并且必须同时给出假设值，否则读者会把它当成实测。

    只对提前期 > scenario_lead_days 的订单生效；这批单是可识别的（下单时就知道）。
    """
    a = settings["analysis"]
    thr, drop = a["scenario_lead_days"], a["scenario_relative_drop"]
    risk = df[df["lead_time"] > thr]
    if risk.empty:
        return {"适用单量": 0, "当前取消率": float("nan"), "少取消单数": 0.0,
                "少取消名义收入": 0.0, "假设": f"提前期>{thr}天，取消率相对下降{drop:.0%}"}
    n = len(risk)
    r = float(risk["is_canceled"].mean())
    saved = n * r * drop
    per_order = float((risk["adr"] * risk["total_nights"]).mean())
    return {
        "适用单量": int(n),
        "适用单量占比": n / len(df),
        "当前取消率": r,
        "少取消单数": float(saved),
        "少取消名义收入": float(saved * per_order),
        "假设": f"提前期>{thr}天，取消率相对下降{drop:.0%}（假设值，非实测）",
    }
