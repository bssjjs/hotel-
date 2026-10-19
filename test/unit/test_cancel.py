#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_cancel.py
# @Path       : analyse/test/unit/test_cancel.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 14:00:00
# @Version    : v1.0.0
# @Description: cancel 的单元测试：因素扫描、超额取消、取消时机与情景演算。
# @ChangeLog:
#   2026-10-19 14:00:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""cancel 的单元测试：影响面非负、时机分布闭合、情景公式可复算。"""
import pandas as pd

from hotel_insight import cancel

NATURES = {"结构性", "可干预", "混合", "需存疑"}


def test_every_factor_declares_nature_and_reason():
    """性质是业务判断，不能漏；漏一条，象限图就会少一个点却没人发现。"""
    for f in cancel.FACTORS:
        assert f["性质"] in NATURES, f"{f['名称']} 的性质 {f['性质']} 不在允许集合里"
        assert f["理由"].strip(), f"{f['名称']} 没写判定理由"


def test_factor_scan_columns_and_order(panel, settings):
    t = cancel.factor_scan(panel.copy(), settings)
    assert list(t.columns) == cancel.IMPACT_COLS
    assert t["超额取消单"].is_monotonic_decreasing
    assert len(t) == len(cancel.FACTORS)


def test_factor_scan_does_not_touch_input(panel, settings):
    before = list(panel.columns)
    cancel.factor_scan(panel.copy(), settings)
    assert list(panel.columns) == before        # 派生列建在副本上


def test_excess_is_zero_when_all_groups_share_the_same_rate():
    df = pd.DataFrame({"g": ["a"] * 40 + ["b"] * 60, "is_canceled": [1] * 40 + [1] * 60})
    assert abs(cancel.excess_cancellations(df, "g", min_n=1)) < 1e-12


def test_excess_only_counts_groups_above_average():
    df = pd.DataFrame({"g": ["高"] * 50 + ["低"] * 50, "is_canceled": [1] * 50 + [0] * 50})
    # 总体 50%，高组 100% → 超额 = 50 × (1 − 0.5) = 25；低组不贡献
    assert abs(cancel.excess_cancellations(df, "g", min_n=1) - 25) < 1e-9


def test_cancellation_timing_adds_up_to_cancelled_count(panel, settings):
    a = settings["analysis"]
    t = cancel.cancellation_timing(panel, a["cancel_lead_bins"], a["cancel_lead_labels"])
    assert t["记录数"].sum() == panel["is_canceled"].sum()
    assert abs(t["累计占比"].iloc[-1] - 1) < 1e-9


def test_scenario_formula_is_reproducible(panel, settings):
    r = cancel.scenario_reconfirm(panel, settings)
    a = settings["analysis"]
    risk = panel[panel["lead_time"] > a["scenario_lead_days"]]
    expect = len(risk) * risk["is_canceled"].mean() * a["scenario_relative_drop"]
    assert abs(r["少取消单数"] - expect) < 1e-9
    assert r["假设"].endswith("假设值，非实测）")


def test_revenue_share_matches_manual_sum(panel):
    r = cancel.revenue_at_risk(panel)
    rev = panel["adr"] * panel["total_nights"]
    assert abs(r["取消订单名义收入"] - rev[panel["is_canceled"] == 1].sum()) < 1e-6
    assert abs(r["占比"] - rev[panel["is_canceled"] == 1].sum() / rev.sum()) < 1e-12
