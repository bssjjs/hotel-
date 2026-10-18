#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_pipeline_contract.py
# @Path       : analyse/test/contract/test_pipeline_contract.py
# @Project    : hotel-dq
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:30:00
# @Description: pipeline.run_day 的端到端契约测试。
# @ChangeLog:
#   2026-10-18 18:30:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""pipeline.run_day 的端到端契约测试。

对调用方的承诺：给定符合契约的原始表，产出四张表（dwd_bookings / ads_clean_steps /
dq_check_result / etl_log）结构与内容正确；同一份数据重跑幂等；返回值就是写进 etl_log 的那份。
"""
import sqlite3

import pandas as pd

from hotel_dq import pipeline

from schema import CLEAN_STEPS_COLS, DQ_COLS, DWD_COLS, ETL_COLS, EXPECTED_STEPS


def test_run_day_produces_four_tables(db_path):
    log = pipeline.run_day(db_path)
    con = sqlite3.connect(db_path)
    dwd = pd.read_sql("SELECT * FROM dwd_bookings", con)
    steps = pd.read_sql("SELECT * FROM ads_clean_steps", con)
    dq = pd.read_sql("SELECT * FROM dq_check_result", con)
    etl = pd.read_sql("SELECT * FROM etl_log", con)
    con.close()

    # 25 行原始 → 四步各剔 1/1/1/2 → 20 行
    assert len(dwd) == 20
    assert list(dwd.columns) == DWD_COLS
    assert len(steps) == 4 and list(steps.columns) == CLEAN_STEPS_COLS
    assert steps["剔除行数"].tolist() == [1, 1, 1, 2]
    assert len(dq) == 16 and list(dq.columns) == DQ_COLS
    assert len(etl) == len(EXPECTED_STEPS)
    assert list(etl.columns) == ETL_COLS


def test_step_order_and_rows_are_contract(db_path):
    log = pipeline.run_day(db_path)
    assert log["步骤"].tolist() == EXPECTED_STEPS
    assert log["输出行数"].tolist() == [25, 20, 20, 4, 16, 16]
    # 读库那一步拿到的不是 DataFrame，输入行数留空（SQLite 读回是 NaN）
    assert pd.isna(log.loc[0, "输入行数"])
    assert log.loc[1, "输入行数"] == 25


def test_run_day_idempotent(db_path):
    pipeline.run_day(db_path)
    pipeline.run_day(db_path)
    con = sqlite3.connect(db_path)
    assert pd.read_sql("SELECT COUNT(*) n FROM dwd_bookings", con)["n"].item() == 20
    etl = pd.read_sql("SELECT * FROM etl_log", con)
    con.close()
    assert len(etl) == len(EXPECTED_STEPS) * 2        # 日志追加
    assert etl["批次"].nunique() == 2                 # 两次运行两个批次号


def test_returned_log_equals_etl_log(db_path):
    log = pipeline.run_day(db_path)
    con = sqlite3.connect(db_path)
    etl = pd.read_sql("SELECT * FROM etl_log", con)
    con.close()
    pd.testing.assert_frame_equal(log, etl, check_dtype=False)


def test_batches_are_single_per_run(db_path):
    log = pipeline.run_day(db_path)
    assert log["批次"].nunique() == 1                 # 一次运行的 6 步共用一个批次号
