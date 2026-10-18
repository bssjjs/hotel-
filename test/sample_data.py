#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : sample_data.py
# @Path       : analyse/test/sample_data.py
# @Project    : hotel-dq
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:05:00
# @Description: 测试用的合成 bookings 数据与迷你库工厂（不含任何真实记录）。
# @ChangeLog:
#   2026-10-18 18:05:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
只装"合成样例"这一种东西，不是 utils.py（AGENTS.md 第 6.2 条）。

为什么不用真实库：data/ 不进 Git（第 1.1 条），测试读它就没法在别人机器上跑；
而且真实数据每天被流水线改写，断言数字会飘。这里的 25 行是构造出来的，
每一步剔除多少行都算得清，端到端测试才能精确断言。

构造结果（tests 依赖这些数字）：
    25 行原始 → ①无人入住 −1 → 24 → ②零晚数 −1 → 23 → ③房价异常 −1 → 22 → ④完全重复 −2 → 20
"""
import sqlite3

import pandas as pd

from hotel_dq import config, dwd

# 一行的"正常"取值：字段名与真实表的业务字段一一对应
DEFAULTS = {
    "hotel_type": "城市酒店",
    "is_canceled": 0,
    "lead_time": 30,
    "arrival_year": 2016,
    "arrival_month": "一月",
    "arrival_week": 1,
    "arrival_day": 1,
    "stays_weekend": 1,
    "stays_weeknight": 2,
    "adults": 2,
    "children": 0,
    "babies": 0,
    "meal": "含早餐",
    "country": "葡萄牙",
    "market_segment": "在线旅行社",
    "distribution_channel": "旅行社/旅游运营商",
    "is_repeated_guest": 0,
    "previous_cancellations": 0,
    "previous_bookings_not_canceled": 0,
    "reserved_room_type": "A",
    "assigned_room_type": "A",
    "booking_changes": 0,
    "deposit_type": "无押金",
    "agent_id": 240.0,          # 故意留成浮点：DQ-04 要能识别出"整数却以浮点存储"
    "company_id": None,         # 故意留空：DQ-02 的高缺失
    "days_in_waiting_list": 0,
    "customer_type": "散客",
    "adr": 100.0,
    "required_car_parking_spaces": 0,
    "total_of_special_requests": 0,
    "reservation_status": "已离店",
    "status_date": "2016-03-01",   # 晚于到达日期：DQ-09 的时序应该通过
}


def make_raw(n_base: int = 20) -> pd.DataFrame:
    """造 n_base 条干净记录（一月/二月各一半），再追加 5 条各有毛病的记录。

    最后 5 条的顺序是故意的：脏数据混在中间也不会影响四步剔除的计数，
    因为每行只计入第一个命中的步骤——这正是报告表 5-1 的口径。
    """
    rows = []
    for i in range(n_base):
        row = dict(DEFAULTS)
        if i >= n_base // 2:                    # 后半段换到二月，测多分区
            row.update(arrival_month="二月", arrival_day=i - n_base // 2 + 1)
        else:
            row.update(arrival_day=i + 1)
        row.update(hotel_type="城市酒店" if i % 2 == 0 else "度假酒店",
                   is_canceled=int(i % 3 == 0),   # 整数而不是布尔：契约里 is_canceled 是 int
                   lead_time=10 + i,
                   adr=100.0 + i)
        rows.append(row)

    rows.append({**DEFAULTS, "adults": 0, "children": 0, "babies": 0})              # ① 无人入住
    rows.append({**DEFAULTS, "stays_weekend": 0, "stays_weeknight": 0})             # ② 零晚数
    rows.append({**DEFAULTS, "adr": 0.0})                                           # ③ 房价 0 值
    rows.append(dict(rows[0]))                                                      # ④ 与第 1 条完全重复
    rows.append(dict(rows[0]))                                                      # ④ 再来一条

    df = pd.DataFrame(rows, columns=config.BUSINESS_COLS)
    df.insert(0, "booking_id", range(1, len(df) + 1))
    return df


def write_db(path) -> None:
    """把合成数据写成一张跟真实库同结构的 bookings 表（37 列：主键 + 32 业务 + 4 派生）。

    派生列用生产代码补一次，保证"结构契约"这一层测的是真实形状；
    至于"从 32 列补齐派生列"这件事，由 test/unit/test_dwd.py 单独覆盖。
    """
    df = dwd.with_derived(make_raw())
    df = df[["booking_id", *config.BUSINESS_COLS, *config.DERIVED_COLS]]
    con = sqlite3.connect(path)
    df.to_sql("bookings", con, index=False)
    con.close()
