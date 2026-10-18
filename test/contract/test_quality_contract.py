#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_quality_contract.py
# @Path       : analyse/test/contract/test_quality_contract.py
# @Project    : hotel-dq
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:36:00
# @Description: dq_check_result 表结构的契约测试。
# @ChangeLog:
#   2026-10-18 18:36:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""dq_check_result 对读回方的承诺：列与顺序、同编号覆盖、不同编号共存、表自动创建。

报告里的 16 项结论、汇总图、附录 A 都从这张表读，列序一变全部要改。
"""
import pandas as pd

from hotel_dq import quality

from schema import DQ_COLS


def test_table_is_created_on_first_write(con):
    quality.dq_record(con, "DQ-01", "时效性", "覆盖", "bookings.arrival_date", "26 个月", "警告")
    cols = [r[1] for r in con.execute('PRAGMA table_info("dq_check_result")')]
    assert cols == DQ_COLS


def test_same_id_overwrites(con):
    quality.dq_record(con, "DQ-01", "时效性", "覆盖", "f", "旧", "警告")
    quality.dq_record(con, "DQ-01", "时效性", "覆盖", "f", "新", "通过")
    dq = pd.read_sql("SELECT * FROM dq_check_result", con)
    assert len(dq) == 1 and dq.loc[0, "结果"] == "新"


def test_different_ids_coexist(con):
    quality.dq_record(con, "DQ-01", "时效性", "覆盖", "f", "r", "警告")
    quality.dq_record(con, "DQ-02", "完整性", "缺失", "f", "r", "不通过")
    dq = pd.read_sql("SELECT * FROM dq_check_result", con).sort_values("check_id")
    assert dq["check_id"].tolist() == ["DQ-01", "DQ-02"]
    assert dq["状态"].tolist() == ["警告", "不通过"]
