#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : dwd.py
# @Path       : analyse/src/hotel_insight/dwd.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 17:15:00
# @Version    : v1.0.0
# @Description: 明细层 dwd_bookings：补齐派生列，按固定顺序执行四步清洗。
# @ChangeLog:
#   2026-10-18 17:15:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
纯计算（AGENTS.md 第 4.1 条）：输入 DataFrame，输出 DataFrame 与剔除记录；不读库、不写库、不读文件。
清洗顺序是契约（docs/需求规格.md 5.1）：顺序不可交换，否则各步剔除数会变、报告与表就对不上。
"""
import pandas as pd

from . import config

# 中文月份 → 1—12。DQ-05 的量：原始 arrival_month 是"七月"这种文本，不能排序
CN_MONTH = {
    "一月": 1, "二月": 2, "三月": 3, "四月": 4, "五月": 5, "六月": 6,
    "七月": 7, "八月": 8, "九月": 9, "十月": 10, "十一月": 11, "十二月": 12,
}

# 四步清洗的步骤名。写进 etl_log 与报告表 5-1，改名字就是改契约
STEP_NAMES = ("无人入住", "零晚数", "房价异常", "完全重复")


def with_derived(raw: pd.DataFrame) -> pd.DataFrame:
    """补齐四个派生列与分区列 month；已存在的列不动（入库脚本已经算好了）。

    为什么只在缺失时补：真实库里 arrival_date 是入库时由年/月/日拼的，直接重算一遍
    等于把入库口径又实现一次，两处一旦不一致就没人知道该信谁。
    """
    out = raw.copy()

    if "arrival_month_no" not in out.columns:
        if "arrival_month" in out.columns:
            out["arrival_month_no"] = out["arrival_month"].map(CN_MONTH).astype("Int64")
        else:
            out["arrival_month_no"] = pd.to_datetime(
                out["arrival_date"], errors="coerce").dt.month.astype("Int64")

    if "arrival_date" not in out.columns:
        out["arrival_date"] = pd.to_datetime(
            dict(year=out["arrival_year"], month=out["arrival_month_no"], day=out["arrival_day"]),
            errors="coerce").dt.strftime("%Y-%m-%d")

    if "total_nights" not in out.columns:
        out["total_nights"] = out["stays_weekend"] + out["stays_weeknight"]
    if "total_guests" not in out.columns:
        out["total_guests"] = out["adults"] + out["children"].fillna(0) + out["babies"]

    out["month"] = out["arrival_date"].str[:7]        # 分区列：2015-07
    return out


def clean_bookings(raw: pd.DataFrame, settings: dict) -> tuple[pd.DataFrame, list[dict]]:
    """按固定顺序清洗，返回 (dwd_bookings, 每一步的剔除记录)。

    顺序：删无人入住 → 删零晚数 → 删房价异常 → 去完全重复。
    每行只计入第一个命中的步骤，所以四步之和等于总剔除量（报告表 5-1 的口径）。

    剔除记录的每一项是 {"步骤", "剔除行数", "剩余行数"}，与报告 5.1 节同一结构。
    先按 booking_id 排序，是为了让"去重保留第一条"等价于"保留 booking_id 最小者"。
    """
    p = settings["cleaning"]
    steps = []

    def log(name, before, after):
        steps.append({"步骤": name, "剔除行数": before - after, "剩余行数": after})

    df = with_derived(raw)
    if "booking_id" in df.columns:
        df = df.sort_values("booking_id", kind="stable")

    n = len(df); df = df[df["total_guests"] > 0];                                    log(STEP_NAMES[0], n, len(df))
    n = len(df); df = df[df["total_nights"] > 0];                                    log(STEP_NAMES[1], n, len(df))
    n = len(df); df = df[(df["adr"] > p["adr_min"]) & (df["adr"] <= p["adr_max"])];   log(STEP_NAMES[2], n, len(df))
    n = len(df); df = df.drop_duplicates(subset=config.BUSINESS_COLS, keep=p["keep_duplicate"]); log(STEP_NAMES[3], n, len(df))

    return df[config.DWD_COLS].reset_index(drop=True), steps
