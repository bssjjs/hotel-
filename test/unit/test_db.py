#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_db.py
# @Path       : analyse/test/unit/test_db.py
# @Project    : hotel-dq
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:18:00
# @Description: db 的单元测试：三种写入语义与表存在性判断。
# @ChangeLog:
#   2026-10-18 18:18:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""db 的单元测试：整表替换、追加、按分区写入的语义（真实库不参与）。"""
import pandas as pd

from hotel_dq import db


def _df(months, n=None):
    """n 默认取月份个数：列长度必须一致，否则 pandas 直接报错。"""
    n = len(months) if n is None else n
    return pd.DataFrame({"booking_id": range(n), "month": months, "adr": 100.0})


def test_table_exists(con):
    assert db.table_exists(con, "t") is False
    _df(["2016-01"]).to_sql("t", con, index=False)
    assert db.table_exists(con, "t") is True


def test_replace_table_rewrites(con):
    df = _df(["2016-01", "2016-02"])
    assert db.replace_table(con, df, "t") == 2
    assert db.replace_table(con, df, "t") == 2
    assert len(db.read_table(con, "t")) == 2          # 替换，不叠加


def test_append_table_only_grows(con):
    df = _df(["2016-01", "2016-02"])
    assert db.append_table(con, df, "t") == 2
    assert db.append_table(con, df, "t") == 2
    assert len(db.read_table(con, "t")) == 4          # 追加，翻倍


def test_write_partition_is_idempotent(con):
    df = _df(["2016-01", "2016-01"])
    assert db.write_partition(con, df, "t", "2016-01") == 2
    assert db.write_partition(con, df, "t", "2016-01") == 2
    assert len(db.read_table(con, "t")) == 2          # 同月重跑，行数不变


def test_write_partition_keeps_other_months(con):
    db.write_partition(con, _df(["2016-01"]), "t", "2016-01")
    db.write_partition(con, _df(["2016-02", "2016-02", "2016-02"]), "t", "2016-02")
    out = db.read_table(con, "t")
    assert len(out) == 4
    assert out["month"].value_counts().to_dict() == {"2016-01": 1, "2016-02": 3}
