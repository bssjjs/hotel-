#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : conftest.py
# @Path       : analyse/test/contract/conftest.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:25:00
# @Description: 契约测试的公共 fixture：造一个"迷你酒店库"。
# @ChangeLog:
#   2026-10-18 18:25:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""契约测试的公共 fixture：在临时目录里按真实 schema 建 bookings 表。

数据全合成（25 行，其中 5 行各有毛病），不读 data/ 下任何东西；
表结构按 schema.py 的契约常量建，端到端测试可以精确断言每一步的行数。
"""
import sqlite3

import pytest

from sample_data import write_db


@pytest.fixture
def db_path(tmp_path) -> str:
    """建好 bookings 表的临时库路径（连接已关，pipeline.run_day 可以自己连）。"""
    path = tmp_path / "hotel.db"
    write_db(path)
    return str(path)


@pytest.fixture
def db_con(db_path) -> sqlite3.Connection:
    """同一个库的打开连接，给直接读表的测试用。"""
    con = sqlite3.connect(db_path)
    yield con
    con.close()
