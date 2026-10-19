#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_rate.py
# @Path       : analyse/test/unit/test_rate.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 13:20:00
# @Version    : v1.0.0
# @Description: rate 的单元测试：区间、分组率、结构分解的恒等式。
# @ChangeLog:
#   2026-10-19 13:20:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""rate 的单元测试：Wilson 区间、分组率的抑制规则、Kitagawa 分解必须闭合。"""
import numpy as np
import pandas as pd

from hotel_insight import rate


def test_wilson_contains_estimate_and_stays_in_01():
    lo, hi = rate.wilson(np.array([30, 1, 0]), np.array([100, 100, 100]))
    assert lo[0] < 0.30 < hi[0]
    assert 0 <= lo.min() and hi.max() <= 1
    # 极端比例：0/100 的下限是 0，上限不该顶到 1（那等于说"最多全员取消"）
    assert lo[2] == 0 and hi[2] < 0.05


def test_wilson_returns_nan_for_empty_group():
    lo, hi = rate.wilson(np.array([0]), np.array([0]))
    assert np.isnan(lo[0]) and np.isnan(hi[0])


def test_rate_table_counts_add_up(panel):
    t = rate.rate_table(panel, "market_segment")
    assert t["记录数"].sum() == len(panel)
    assert abs(t["占比"].sum() - 1) < 1e-12
    assert t["取消单数"].sum() == panel["is_canceled"].sum()


def test_rate_table_keeps_thin_group_but_blanks_rate():
    df = pd.DataFrame({"g": ["大"] * 100 + ["小"] * 3, "is_canceled": [0] * 100 + [1, 1, 1]})
    t = rate.rate_table(df, "g", min_n=30)
    assert t.loc["小", "记录数"] == 3          # 记录数保留：读者要知道"这里只有 3 单"
    assert np.isnan(t.loc["小", "取消率"])      # 但比率不给：3 单算 100% 是误导


def test_kitagawa_identity_holds(panel):
    a = panel[panel["arrival_year"] == 2016]
    b = panel[panel["arrival_year"] == 2017]
    d = rate.kitagawa(a, b, "market_segment")
    parts = d["结构效应"] + d["组内效应"] + d["交互效应"]
    assert abs(parts - d["总变化"]) < 1e-9
    assert abs(d["总变化"] - (b["is_canceled"].mean() - a["is_canceled"].mean()) * 100) < 1e-9


def test_kitagawa_structure_effect_is_zero_when_mix_is_identical():
    """构成完全相同时，全部差异只能落在"组内"这一项。"""
    a = pd.DataFrame({"g": ["x"] * 50 + ["y"] * 50, "is_canceled": [0] * 50 + [1] * 50})
    b = pd.DataFrame({"g": ["x"] * 50 + ["y"] * 50, "is_canceled": [1] * 50 + [1] * 50})
    d = rate.kitagawa(a, b, "g")
    assert abs(d["结构效应"]) < 1e-12
    assert abs(d["交互效应"]) < 1e-12
    assert abs(d["组内效应"] - d["总变化"]) < 1e-9


def test_nested_kitagawa_covers_every_outer_group(panel):
    a = panel[panel["arrival_year"] == 2016]
    b = panel[panel["arrival_year"] == 2017]
    t = rate.nested_kitagawa(a, b, "market_segment", "hotel_type")
    assert set(t.index) == set(a["market_segment"])
    for _, r in t.iterrows():
        assert abs(r["结构效应"] + r["组内效应"] + r["交互效应"] - r["总变化"]) < 0.02
