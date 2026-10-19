#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_checks.py
# @Path       : analyse/test/unit/test_checks.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:20:00
# @Description: checks 的单元测试：16 项齐全、编号唯一、阈值来自 settings。
# @ChangeLog:
#   2026-10-18 18:20:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""checks 的单元测试：16 项检查齐全、编号唯一、判定随 settings 的阈值变化。"""
import copy

import pytest

from hotel_insight import checks, config, dwd, quality

from sample_data import make_raw


@pytest.fixture
def settings():
    return config.load_settings()


@pytest.fixture
def raw():
    return dwd.with_derived(make_raw(20))


def _row(res, check_id):
    return res.set_index("check_id").loc[check_id]


def test_sixteen_checks_with_unique_ids(raw, settings):
    res = checks.run_all(raw, settings)
    assert len(res) == 16
    assert list(res.columns) == quality.COLUMNS
    ids = res["check_id"].tolist()
    assert ids == [f"DQ-{i:02d}" for i in range(1, 17)]
    assert res["状态"].isin(quality.STATUSES).all()


def test_dq02_flags_high_missing_column(raw, settings):
    """company_id 全空 → 缺失率 100% > 50% → 不通过。"""
    assert _row(checks.run_all(raw, settings), "DQ-02")["状态"] == "不通过"


def test_dq10_flags_zero_adr(raw, settings):
    """adr=0 的 1 行占 4% > 1% → 不通过（DQ-10）。"""
    row = _row(checks.run_all(raw, settings), "DQ-10")
    assert row["状态"] == "不通过"
    assert "0 值 1 行" in row["结果"]


def test_dq06_threshold_comes_from_settings(raw, settings):
    """2/25 = 8%：默认阈值 10% 判警告；把阈值调到 5% 就变不通过——数字不在代码里。"""
    assert _row(checks.run_all(raw, settings), "DQ-06")["状态"] == "警告"

    strict = copy.deepcopy(settings)
    strict["quality"]["dup_rate_fail"] = 0.05
    assert _row(checks.run_all(raw, strict), "DQ-06")["状态"] == "不通过"


def test_dq12_passes_without_extreme_lead_time(raw, settings):
    assert _row(checks.run_all(raw, settings), "DQ-12")["状态"] == "通过"


def test_dq01_warns_on_incomplete_year(raw, settings):
    """合成数据只有 2016 年的两个月 → 首尾年份不完整，判警告。"""
    row = _row(checks.run_all(raw, settings), "DQ-01")
    assert row["状态"] == "警告"
    assert "2 个月" in row["结果"]


def test_dq09_detects_status_before_arrival(raw, settings):
    """把一条已离店记录的状态日期改到到达日期之前，DQ-09 必须报出违规。"""
    broken = raw.copy()
    broken.loc[0, "status_date"] = "2015-01-01"
    row = _row(checks.run_all(broken, settings), "DQ-09")
    assert "违规 1 行" in row["结果"]
