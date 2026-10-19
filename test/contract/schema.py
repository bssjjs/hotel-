#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : schema.py
# @Path       : analyse/test/contract/schema.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:26:00
# @Description: 原始表与产物表的期望结构（契约常量）。
# @ChangeLog:
#   2026-10-18 18:26:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
契约测试与真实库对账共用这一份常量：只抄表结构，不抄数据行（AGENTS.md 第 15.3 条）。
来源：data/hotel.db 的 PRAGMA table_info，2026-10-18。
不是 utils.py 一类的东西——它只装"表结构契约"这一种常量（第 6.2 条）。
"""
from hotel_insight import config, quality

# 原始层：37 列（代理主键 + 32 业务字段 + 4 派生列）；流水线依赖这些列齐全
BOOKINGS_COLS = ["booking_id", *config.BUSINESS_COLS, *config.DERIVED_COLS]

# 明细层：列序即契约，与 config.DWD_COLS 同源
DWD_COLS = config.DWD_COLS

# 清洗步骤表：报告表 5-1 就是它
CLEAN_STEPS_COLS = ["步骤", "剔除行数", "剩余行数", "占原始比例"]

DQ_COLS = quality.COLUMNS

# 运行日志：一次运行 6 步，同批同号
ETL_COLS = ["步骤", "输入行数", "输出行数", "耗时(秒)", "运行时间", "批次"]

# 一次运行的步骤顺序（契约测试固化它；有人要"优化"顺序时，先改这里）
EXPECTED_STEPS = ["extract_bookings", "clean_bookings", "write_dwd",
                  "write_clean_steps", "audit", "save_audit"]
