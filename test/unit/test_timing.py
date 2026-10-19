#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_timing.py
# @Path       : analyse/test/unit/test_timing.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 13:40:00
# @Version    : v1.0.0
# @Description: timing 的单元测试：分箱边界、同比切片、季节指数的完整年限制。
# @ChangeLog:
#   2026-10-19 13:40:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""timing 的单元测试：分箱的左右边界、同比只取同月、不完整年份不许算季节指数。"""
import pandas as pd
import pytest

from hotel_insight import timing


def test_binned_profile_puts_boundary_values_in_the_right_bucket(panel):
    """左开右闭：0 进第一档，7 仍在第一档，8 进第二档。边界错一格，整张图都会歪。"""
    df = panel.copy()
    df.loc[:3, "lead_time"] = [0, 7, 8, 365]
    t = timing.binned_profile(df, "lead_time", [0, 7, 30, 90, 180, 365, 99999],
                              ["7 天内", "8–30 天", "31–90 天", "91–180 天",
                               "181–365 天", "365 天以上"])
    assert t.loc["7 天内", "记录数"] >= 2       # 0 与 7
    assert t["记录数"].sum() == len(df)


def test_binned_profile_keeps_label_order(panel):
    """标签顺序就是显示顺序：有序变量不能按记录数重排，否则梯度被打乱。"""
    labels = ["7 天内", "8–30 天", "31–90 天", "91–180 天", "181–365 天", "365 天以上"]
    t = timing.binned_profile(panel, "lead_time", [0, 7, 30, 90, 180, 365, 99999], labels)
    assert list(t.index) == labels


def test_comparable_slice_only_keeps_requested_year_and_month(panel):
    s = timing.comparable_slice(panel, [2017], [1, 2, 3])
    assert set(s["arrival_year"]) == {2017}
    assert set(s["arrival_month_no"]) == {1, 2, 3}
    assert len(s) == len(panel[panel["arrival_year"] == 2017]) // 4


def test_season_index_rejects_incomplete_year():
    df = pd.DataFrame({"arrival_year": [2015] * 6,
                       "arrival_month_no": [7, 8, 9, 10, 11, 12]})
    with pytest.raises(ValueError, match="不能算季节指数"):
        timing.season_index(df, 2015)


def test_season_index_averages_to_one(panel):
    idx = timing.season_index(panel, 2016)
    assert len(idx) == 12
    assert abs(idx.mean() - 1) < 1e-12       # 等长月份的合成数据：每月都一样


def test_dow_profile_has_fixed_seven_rows(panel):
    t = timing.dow_profile(panel)
    assert list(t.index) == timing.DOW_LABELS
    assert t["记录数"].sum() == len(panel)
