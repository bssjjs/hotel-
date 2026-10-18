#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : db.py
# @Path       : analyse/src/hotel_dq/db.py
# @Project    : hotel-dq
# @Author     : 一班第十二组
# @Date       : 2026-10-18 17:05:00
# @Version    : v1.0.0
# @Description: 数据库读写：连接、按到达月分区写入、整表替换、追加。
# @ChangeLog:
#   2026-10-18 17:05:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
只会因为"换了数据库"而改（AGENTS.md 第 2 条）。换成 MySQL、DuckDB 时，计算模块一行不动，只改这里。
只有 db.py 和 pipeline.py 碰数据库；quality.dq_record 是唯一例外（第 4.2 条）。
"""
import sqlite3

import pandas as pd

from . import config


def connect(path=None) -> sqlite3.Connection:
    """连接数据库；不给路径就连 config.DB_PATH（data/hotel.db）。"""
    return sqlite3.connect(config.DB_PATH if path is None else path)


def table_exists(con, table: str) -> bool:
    """表（或视图）是否存在。视图也算：v_monthly_kpi 是查询定义，不是表。"""
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE name = ? AND type IN ('table', 'view')",
        (table,),
    ).fetchone() is not None


def write_partition(con, df: pd.DataFrame, table: str, month: str,
                    month_col: str = "month") -> int:
    """按到达月分区写入：先删掉这个月的旧数据，再追加。同一个月重跑多少次，结果都一样（幂等）。

    ⚠️ 已知不足（与 signal-insight 的 db.write_partition 同源）："删"和"写"是两次提交。
    删完、还没写完时程序崩了，这个月就没了。换支持事务的库时再收进一个事务里。
    返回写入的行数。
    """
    if table_exists(con, table):
        con.execute(f'DELETE FROM "{table}" WHERE "{month_col}" = ?', (month,))
        con.commit()
    df.to_sql(table, con, if_exists="append", index=False)
    return len(df)


def replace_table(con, df: pd.DataFrame, table: str) -> int:
    """整表替换：稽核表、维表这类"永远只有一份"的表用它。返回写入的行数。"""
    df.to_sql(table, con, if_exists="replace", index=False)
    return len(df)


def append_table(con, df: pd.DataFrame, table: str) -> int:
    """追加：运行日志这类"只增不改"的表用它。返回写入的行数。"""
    df.to_sql(table, con, if_exists="append", index=False)
    return len(df)


def read_table(con, table: str) -> pd.DataFrame:
    """读整表。只给流水线与 notebook 用；分析代码拿到 DataFrame 后不再碰连接。"""
    return pd.read_sql(f'SELECT * FROM "{table}"', con)
