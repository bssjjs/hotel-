#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_schema_contract.py
# @Path       : analyse/test/contract/test_schema_contract.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:38:00
# @Description: 原始表结构契约：bookings 的列名与顺序。
# @ChangeLog:
#   2026-10-18 18:38:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""原始表结构契约。

流水线里写的是 SELECT *，列的顺序变了，clean/checks 就会读错位。
平台方（数据提供方）改了结构，这里最先报出来。
"""
from schema import BOOKINGS_COLS


def test_bookings_schema_matches_contract(db_con):
    actual = [r[1] for r in db_con.execute('PRAGMA table_info("bookings")')]
    assert actual == BOOKINGS_COLS


def test_contract_has_32_business_columns():
    assert len(BOOKINGS_COLS) == 37          # 32 业务字段 + 代理主键 + 4 派生列
    assert BOOKINGS_COLS[0] == "booking_id"
    assert BOOKINGS_COLS[-4:] == ["arrival_month_no", "arrival_date", "total_nights", "total_guests"]
