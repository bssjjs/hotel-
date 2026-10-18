#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_quality.py
# @Path       : analyse/test/unit/test_quality.py
# @Project    : hotel-dq
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:15:00
# @Description: quality 的单元测试：画像口径、百分比写法、状态校验。
# @ChangeLog:
#   2026-10-18 18:15:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""quality 的单元测试：字段画像的缺失口径、fmt_pct 的取位规则、dq_record 的参数校验。"""
import pandas as pd
import pytest

from hotel_dq import quality


# ── profile ──

def test_profile_missing_includes_blank_strings():
    """空白字符串算缺失：CSV 导出的空值常常是 " "，不是 NULL。"""
    df = pd.DataFrame({"a": [1, None, 3], "b": ["x", " ", None]})
    p = quality.profile(df).set_index("字段")
    assert p.loc["a", "缺失数"] == 1
    assert p.loc["b", "缺失数"] == 2
    assert p.loc["b", "唯一值个数"] == 1        # 只剩 "x"
    assert p.loc["b", "示例值"] == "x"


def test_profile_zero_rows_has_zero_rate():
    p = quality.profile(pd.DataFrame({"a": []}))
    assert p.loc[0, "缺失率"] == 0.0
    assert p.loc[0, "示例值"] is None


def test_profile_duplicate_columns_by_position():
    """列名重复也要逐列统计：df.items() 按位置取，不会把两列合并成一列。"""
    df = pd.DataFrame([[1, 2]], columns=["a", "a"])
    assert len(quality.profile(df)) == 2


def test_profile_unhashable_values():
    df = pd.DataFrame({"a": [[1], [1], [2]]})
    p = quality.profile(df).set_index("字段")
    assert p.loc["a", "唯一值个数"] == 2        # list 不可哈希，按字符串去重


def test_profile_columns_exact():
    p = quality.profile(pd.DataFrame({"a": [1]}))
    assert list(p.columns) == ["字段", "类型", "缺失数", "缺失率", "唯一值个数", "示例值"]


# ── fmt_pct ──

@pytest.mark.parametrize("value, expected", [
    (0.0, "0%"),
    (0.973, "97%"),        # ≥10% 取整
    (0.408, "41%"),
    (0.027, "2.7%"),       # 1%–10% 一位小数
    (0.0041, "0.41%"),     # <1% 两位有效数字，不能写成 0.0%
    (0.0001, "0.01%"),
])
def test_fmt_pct_rules(value, expected):
    assert quality.fmt_pct(value) == expected


# ── dq_record ──

def test_dq_record_rejects_unknown_status(con):
    with pytest.raises(ValueError):
        quality.dq_record(con, "DQ-99", "完整性", "测试项", "bookings.a", "结果", "待定")


def test_dq_record_writes_and_overwrites(con):
    quality.dq_record(con, "DQ-01", "时效性", "覆盖", "bookings.arrival_date", "26 个月", "警告")
    quality.dq_record(con, "DQ-01", "时效性", "覆盖", "bookings.arrival_date", "27 个月", "通过")
    dq = pd.read_sql("SELECT * FROM dq_check_result", con)
    assert len(dq) == 1                       # 同编号覆盖，不叠加
    assert dq.loc[0, "结果"] == "27 个月"
    assert list(dq.columns) == quality.COLUMNS


def test_summary_fills_missing_status_with_zero(con):
    quality.dq_record(con, "DQ-01", "时效性", "覆盖", "f", "r", "通过")
    s = quality.summary(con)
    assert list(s.columns) == ["不通过", "警告", "通过"]
    assert s.loc["时效性", "不通过"] == 0
