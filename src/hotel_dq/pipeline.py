#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : pipeline.py
# @Path       : analyse/src/hotel_dq/pipeline.py
# @Project    : hotel-dq
# @Author     : 一班第十二组
# @Date       : 2026-10-18 17:55:00
# @Version    : v1.0.0
# @Description: 把原始层一键算到 dwd_bookings、清洗步骤表与 16 项稽核结论，并留下运行记录。
# @ChangeLog:
#   2026-10-18 17:55:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
编排层（AGENTS.md 第 3 条）：唯一同时碰"数据库"和"计算"的地方。
读库 → 调用 dwd / checks 里的纯函数 → 写库，每一步由 @step 记下行数和耗时，最后写进 etl_log。

业务参数一律从 configs/settings.yaml 读，传给计算函数（AGENTS.md 第 8 条）。

用法：
    python -m hotel_dq.pipeline --db data/hotel.db
或在 notebook 里：
    from hotel_dq import pipeline;  pipeline.run_day()
"""
import argparse
import functools
import time

import pandas as pd

from . import checks, config, db, dwd, quality

_LOG: list[dict] = []        # 本进程里所有步骤的记录；run_day 只取自己这一次的那一段

# 产物表：dwd_bookings 按到达月分区；其余三张"永远只有一份"，整表替换
DWD_TABLE = "dwd_bookings"
STEPS_TABLE = "ads_clean_steps"
DQ_TABLE = "dq_check_result"
LOG_TABLE = "etl_log"


def _rows(x):
    """一个步骤的"行数"：DataFrame 取行数，(DataFrame, 其他) 取第一个的行数，整数原样返回。"""
    if isinstance(x, tuple):
        x = x[0]
    if isinstance(x, pd.DataFrame):
        return len(x)
    return x if isinstance(x, int) else None


def step(func):
    """装饰器：记录步骤名、输入行数、输出行数、耗时，不改函数本身的行为。

    装饰器就是"接收一个函数、返回一个新函数"的函数：调用方的写法一个字都不用改，
    但每一步都自动留下了运行记录。出了问题时，看记录就知道是哪一步、处理了多少行、花了多久。
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        rows_in = next((_rows(a) for a in args if isinstance(a, pd.DataFrame)), None)
        t0 = time.perf_counter()
        out = func(*args, **kwargs)
        _LOG.append({"步骤": func.__name__, "输入行数": rows_in, "输出行数": _rows(out),
                     "耗时(秒)": round(time.perf_counter() - t0, 3),
                     "运行时间": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")})
        return out
    return wrapper


# ── 每一步：读库的、算的、写库的分开，各自一个函数，日志里才分得清哪一步慢 ──
@step
def extract_bookings(con):
    """读原始层。bookings 只读，不在这里加任何条件（AGENTS.md 第 1.2 条）。"""
    return pd.read_sql(f"SELECT * FROM {config.TABLE}", con)


@step
def clean_bookings(raw, settings):
    return dwd.clean_bookings(raw, settings)


@step
def write_dwd(con, df: pd.DataFrame) -> int:
    """按到达月分区写 dwd_bookings：同一个月重跑，行数不变（幂等）。返回写入总行数。"""
    n = 0
    for month, part in df.groupby("month", sort=True):
        n += db.write_partition(con, part, DWD_TABLE, month)
    return n


@step
def write_clean_steps(con, steps: list[dict], n_raw: int) -> int:
    """把四步清洗的剔除明细写成 ads_clean_steps（报告表 5-1 就是这张表）。"""
    tbl = pd.DataFrame(steps)
    tbl["占原始比例"] = tbl["剔除行数"] / n_raw
    return db.replace_table(con, tbl, STEPS_TABLE)


@step
def audit(raw, settings):
    """16 项检查（DQ-01—DQ-16）。检查原始层，不是清洗后的数据。

    先把缺失的派生列补齐：真实库里入库脚本已经算好，合成库没有；
    checks 依赖 arrival_date 等派生列，但绝不依赖清洗结果（否则检查与清洗互相牵连）。
    """
    return checks.run_all(dwd.with_derived(raw), settings)


@step
def save_audit(con, result: pd.DataFrame) -> int:
    """逐条登记到 dq_check_result；同一 check_id 覆盖旧结论。

    结果表的列是中文（给人看），dq_record 的参数是英文（给代码看）：这里显式逐个传，
    不用 **dict 展开——列名一改，展开会静默丢字段，逐个传会直接报错。
    """
    for r in result.to_dict("records"):
        quality.dq_record(con, r["check_id"], r["维度"], r["检查项"], r["表字段"],
                          r["结果"], r["状态"], r["证据"], r["处理决定"])
    return len(result)


def run_day(db_path=None) -> pd.DataFrame:
    """跑一遍：读原始层 → 派生+清洗 → 写明细层 → 写清洗步骤 → 16 项稽核 → 写日志。

    返回本次运行的步骤记录。原始层不删不改（第 1.2 条）：所有产物都写在新表里。
    """
    settings = config.load_settings()
    start = len(_LOG)
    batch = pd.Timestamp.now().strftime("%Y%m%d-%H%M%S-%f")     # 批次号：同一次运行的几步共用一个
    con = db.connect(db_path)
    try:
        raw = extract_bookings(con)
        clean, steps = clean_bookings(raw, settings)
        write_dwd(con, clean)
        write_clean_steps(con, steps, len(raw))
        result = audit(raw, settings)
        save_audit(con, result)
        log = pd.DataFrame(_LOG[start:]).assign(批次=batch)
        db.append_table(con, log, LOG_TABLE)
    finally:
        con.close()
    return log


def main(argv=None):
    parser = argparse.ArgumentParser(description="跑一遍数据质量流水线：bookings → dwd_bookings + 16 项稽核")
    parser.add_argument("--db", default=None, help="数据库路径，默认 data/hotel.db")
    args = parser.parse_args(argv)
    log = run_day(args.db)
    print(log[["步骤", "输入行数", "输出行数", "耗时(秒)"]].to_string(index=False))


if __name__ == "__main__":
    main()
