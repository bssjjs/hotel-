#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_dwd.py
# @Path       : analyse/test/unit/test_dwd.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:12:00
# @Description: dwd 的单元测试：派生列、四步剔除数与顺序、去重保留规则。
# @ChangeLog:
#   2026-10-18 18:12:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""dwd 的单元测试：派生列补齐、四步清洗的每一步剔除多少行、去重保留哪一条。"""
import pandas as pd
import pytest

from hotel_insight import config, dwd

from sample_data import make_raw


@pytest.fixture
def settings():
    return config.load_settings()


# ── with_derived ──

def test_with_derived_fills_four_cols_and_month():
    out = dwd.with_derived(make_raw(4))
    for col in [*config.DERIVED_COLS, "month"]:
        assert col in out.columns
    first = out.iloc[0]
    assert first["arrival_date"] == "2016-01-01"
    assert first["arrival_month_no"] == 1
    assert first["total_nights"] == 3                 # 1 个周末晚 + 2 个工作日
    assert first["total_guests"] == 2
    assert first["month"] == "2016-01"


def test_with_derived_maps_chinese_month():
    """中文月份必须能变成 1—12：DQ-05 的整个处理都靠这一步。"""
    out = dwd.with_derived(make_raw(20))
    feb = out[out["arrival_month"] == "二月"]
    assert not feb.empty and (feb["arrival_month_no"] == 2).all()
    assert (feb["month"] == "2016-02").all()


def test_with_derived_keeps_existing_columns():
    """已存在的派生列不重算：真实库里入库脚本已经算好了，重算等于把口径实现两遍。"""
    raw = make_raw(4).assign(arrival_date="1999-09-09")
    out = dwd.with_derived(raw)
    assert (out["arrival_date"] == "1999-09-09").all()


# ── clean_bookings ──

def test_clean_steps_counts_and_order(settings):
    """25 行 → 每步各剔 1 行 → 去重剔 2 行 → 20 行（与 sample_data 的构造对应）。"""
    clean, steps = dwd.clean_bookings(make_raw(20), settings)
    assert [s["步骤"] for s in steps] == list(dwd.STEP_NAMES)
    assert [s["剔除行数"] for s in steps] == [1, 1, 1, 2]
    assert [s["剩余行数"] for s in steps] == [24, 23, 22, 20]
    assert len(clean) == 20


def test_clean_steps_are_self_consistent(settings):
    """每一步剩余只减不增，且最后一步的剩余 = 输出行数（报告表 5-1 的口径）。"""
    clean, steps = dwd.clean_bookings(make_raw(20), settings)
    remain = [s["剩余行数"] for s in steps]
    assert remain == sorted(remain, reverse=True)
    assert remain[-1] == len(clean)
    assert steps[0]["剩余行数"] + steps[0]["剔除行数"] == 25      # 第一步之前就是原始行数


def test_dedupe_keeps_smallest_booking_id(settings):
    """去重保留 booking_id 最小者：先说清楚留哪条，报表才能复核。"""
    clean, _ = dwd.clean_bookings(make_raw(20), settings)
    assert 1 in set(clean["booking_id"])
    assert 24 not in set(clean["booking_id"])
    assert 25 not in set(clean["booking_id"])


def test_clean_output_columns_and_effects(settings):
    clean, _ = dwd.clean_bookings(make_raw(20), settings)
    assert list(clean.columns) == config.DWD_COLS
    assert clean["booking_id"].is_unique
    assert (clean["total_guests"] > 0).all()
    assert (clean["total_nights"] > 0).all()
    assert (clean["adr"] > 0).all()


def test_clean_does_not_mutate_input(settings):
    raw = make_raw(20)
    before = raw.shape, raw["adr"].sum()
    dwd.clean_bookings(raw, settings)
    assert (raw.shape, raw["adr"].sum()) == before


def test_adr_boundary_is_exclusive_at_zero(settings):
    """adr 必须 > 0 且 ≤ 上限：0 值算异常（DQ-10），上限值本身保留。"""
    raw = make_raw(2).iloc[:2].copy()      # 只留两条干净记录，避免脏行干扰这一条断言
    raw.loc[0, "adr"] = 1000.0             # 边界内
    raw.loc[1, "adr"] = 1000.01            # 越界
    clean, steps = dwd.clean_bookings(raw, settings)
    assert steps[2]["剔除行数"] == 1
    assert clean["adr"].max() == 1000.0
