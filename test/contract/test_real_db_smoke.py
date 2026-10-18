#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_real_db_smoke.py
# @Path       : analyse/test/contract/test_real_db_smoke.py
# @Project    : hotel-dq
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:40:00
# @Description: 真实库对账（smoke）：结构、行数与报告里的关键数字。
# @ChangeLog:
#   2026-10-18 18:40:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
真实库对账（smoke）：只做结构与聚合，不读明细行（AGENTS.md 第 15.3 条）。

data/ 不进 Git，所以这组默认跳过；本地想对账时显式打开：
    python -m pytest test/contract/test_real_db_smoke.py --run-smoke

断言的数字就是报告里的数字：行数、四个缺失字段、重复行、清洗后行数。
任何一项变了，说明数据库换了一批数据——此时不该改测试，而该重新出报告。
"""
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from hotel_dq import config, dwd

from schema import BOOKINGS_COLS

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "hotel.db"

pytestmark = pytest.mark.smoke


@pytest.fixture(scope="module")
def real_db():
    if not DB_PATH.exists():
        pytest.skip(f"真实库不存在：{DB_PATH}")
    con = sqlite3.connect(DB_PATH)
    yield con
    con.close()


def test_bookings_schema(real_db):
    actual = [r[1] for r in real_db.execute('PRAGMA table_info("bookings")')]
    assert actual == BOOKINGS_COLS, "原始表结构与契约不符，流水线会读错列"


def test_row_count_and_views(real_db):
    assert real_db.execute('SELECT COUNT(*) FROM bookings').fetchone()[0] == 119_390
    views = {r[0] for r in real_db.execute("SELECT name FROM sqlite_master WHERE type = 'view'")}
    assert {"v_bookings_zh", "v_monthly_kpi", "v_channel_kpi"} <= views


def test_missing_counts_match_report(real_db):
    df = pd.read_sql(
        "SELECT company_id, agent_id, country, children FROM bookings", real_db)
    assert int(df["company_id"].isna().sum()) == 112_593
    assert int(df["agent_id"].isna().sum()) == 16_340
    assert int(df["country"].isna().sum()) == 488
    assert int(df["children"].isna().sum()) == 4


def test_cleaning_numbers_match_report(real_db):
    raw = pd.read_sql(f"SELECT * FROM {config.TABLE}", real_db)
    clean, steps = dwd.clean_bookings(raw, config.load_settings())
    assert [s["剔除行数"] for s in steps] == [180, 645, 1_167, 31_813]
    assert len(clean) == 85_585
