#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_dwd_contract.py
# @Path       : analyse/test/contract/test_dwd_contract.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:32:00
# @Description: dwd.clean_bookings 对下游的契约测试。
# @ChangeLog:
#   2026-10-18 18:32:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""dwd.clean_bookings 对下游的契约测试。

下游（db 写入、checks、notebook）依赖这些承诺：列与顺序、关键 dtype、
booking_id 唯一、剔除记录的键结构与自洽性。改实现可以，改承诺就是破坏契约。
"""
import pandas as pd
import pytest

from hotel_insight import config, dwd

from sample_data import make_raw


@pytest.fixture
def result():
    return dwd.clean_bookings(make_raw(20), config.load_settings())


def test_columns_exact_and_ordered(result):
    out, _ = result
    assert list(out.columns) == config.DWD_COLS


def test_key_dtypes(result):
    out, _ = result
    assert pd.api.types.is_integer_dtype(out["booking_id"])
    assert pd.api.types.is_integer_dtype(out["is_canceled"])
    assert pd.api.types.is_float_dtype(out["adr"])
    assert pd.api.types.is_string_dtype(out["hotel_type"])
    assert pd.api.types.is_string_dtype(out["month"])


def test_partition_column_matches_arrival_date(result):
    """month 必须等于 arrival_date 的前 7 位，否则分区会写错表。"""
    out, _ = result
    assert (out["month"] == out["arrival_date"].str[:7]).all()
    assert out["month"].nunique() == 2


def test_booking_id_unique(result):
    out, _ = result
    assert out["booking_id"].is_unique


def test_steps_record_contract(result):
    _, steps = result
    assert isinstance(steps, list) and len(steps) == 4
    for s in steps:
        assert set(s) == {"步骤", "剔除行数", "剩余行数"}
        assert isinstance(s["步骤"], str)
        assert isinstance(s["剔除行数"], int) and s["剔除行数"] >= 0
        assert isinstance(s["剩余行数"], int)
    remain = [s["剩余行数"] for s in steps]
    assert remain == sorted(remain, reverse=True)
    assert remain[-1] == 20
