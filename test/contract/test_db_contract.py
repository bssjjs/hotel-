#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_db_contract.py
# @Path       : analyse/test/contract/test_db_contract.py
# @Project    : hotel-dq
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:34:00
# @Description: db 写入格式与分区语义的契约测试。
# @ChangeLog:
#   2026-10-18 18:34:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""db 写入对读回方的承诺：分区幂等、换月不互相影响、替换与追加的语义不同。

这些是"下游按什么假设写代码"的问题：notebook 与报告都假设重跑不会让行数翻倍。
"""
import pandas as pd

from hotel_dq import db


def _dwd(months):
    return pd.DataFrame({"booking_id": range(len(months)), "month": months,
                         "adr": [100.0] * len(months)})


def test_same_partition_twice_does_not_double(con):
    df = _dwd(["2016-01", "2016-01", "2016-01"])
    db.write_partition(con, df, "dwd_bookings", "2016-01")
    db.write_partition(con, df, "dwd_bookings", "2016-01")
    assert len(pd.read_sql("SELECT * FROM dwd_bookings", con)) == 3


def test_partitions_are_independent(con):
    db.write_partition(con, _dwd(["2016-01"]), "dwd_bookings", "2016-01")
    db.write_partition(con, _dwd(["2016-02", "2016-02"]), "dwd_bookings", "2016-02")
    db.write_partition(con, _dwd(["2016-01"]), "dwd_bookings", "2016-01")   # 重写一月
    out = pd.read_sql("SELECT month FROM dwd_bookings", con)
    assert out["month"].value_counts().to_dict() == {"2016-01": 1, "2016-02": 2}


def test_replace_vs_append(con):
    df = _dwd(["2016-01", "2016-02"])
    db.append_table(con, df, "etl_log")
    db.append_table(con, df, "etl_log")
    assert len(pd.read_sql("SELECT * FROM etl_log", con)) == 4      # 只增
    db.replace_table(con, df, "etl_log")
    assert len(pd.read_sql("SELECT * FROM etl_log", con)) == 2      # 全量替换
