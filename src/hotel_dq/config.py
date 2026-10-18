#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : config.py
# @Path       : analyse/src/hotel_dq/config.py
# @Project    : hotel-dq
# @Author     : 一班第十二组
# @Date       : 2026-10-18 17:00:00
# @Version    : v1.0.0
# @Description: 项目根定位、路径常量、口径常量与业务参数加载。
# @ChangeLog:
#   2026-10-18 17:00:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
只会因为"文件放的位置变了、口径常量变了"而改（AGENTS.md 第 2 条）。
不 import 项目里的任何模块：这里是依赖图的最底层（第 3.2 条）。
import 本模块只做路径拼接与读一个 YAML，不建目录、不连库（第 7 条）。
"""
import os
from pathlib import Path

import yaml

# 项目根的标记文件：根目录里只要有它，就能锁定项目根，
# 不依赖 config.py 自己在包内第几层（AGENTS.md 第 2 条）。
WORKSPACE_MARKER = "hotel.workspace"


def find_project_root(marker: str = WORKSPACE_MARKER) -> Path:
    """从 config.py 所在目录逐级向上查找含 marker 的目录，作为项目根路径。

    这样即使包被移动到更深的层级，也能靠根目录里的 hotel.workspace 找到正确的根。
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / marker).exists():
            return parent
    raise FileNotFoundError(
        f"未找到项目根标记文件 {marker!r}，请确认它存在于项目根目录"
    )


PROJECT_ROOT = find_project_root()

DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "hotel.db"          # 原始层 + 三个分析视图，只读不改

IMAGE_DIR = PROJECT_ROOT / "image"       # notebook 出图，不进 Git

SETTINGS_PATH = PROJECT_ROOT / "configs" / "settings.yaml"

# 默认的可视化主题：viz/styles/ 里的文件名（default / academic / business）
THEME = os.environ.get("HOTEL_THEME", "default")

# ── 口径常量：报告里出现的每一个"分母"都从这里来 ──
TABLE = "bookings"
SOURCE_NOTE = "数据来源：Hotel Booking Demand 酒店预订数据集（中文版，119,390 行）"
AUTHOR = "一班第十二组"

# 原始层的 32 个业务字段（不含代理主键 booking_id，也不含 4 个派生列）。
# 判"完全重复"就用这 32 列：booking_id 是入库时自增的，带上它永远判不出重复。
BUSINESS_COLS = [
    "hotel_type", "is_canceled", "lead_time", "arrival_year", "arrival_month",
    "arrival_week", "arrival_day", "stays_weekend", "stays_weeknight",
    "adults", "children", "babies", "meal", "country", "market_segment",
    "distribution_channel", "is_repeated_guest", "previous_cancellations",
    "previous_bookings_not_canceled", "reserved_room_type", "assigned_room_type",
    "booking_changes", "deposit_type", "agent_id", "company_id",
    "days_in_waiting_list", "customer_type", "adr",
    "required_car_parking_spaces", "total_of_special_requests",
    "reservation_status", "status_date",
]

# 派生列：DQ-05 处理月份/日期编码、DQ-11 判零晚数与无人入住时用
DERIVED_COLS = ["arrival_month_no", "arrival_date", "total_nights", "total_guests"]

# 明细层列序：代理主键 + 32 业务字段 + 4 派生列 + 分区列 month
DWD_COLS = ["booking_id", *BUSINESS_COLS, *DERIVED_COLS, "month"]

# 稽核结果的三级状态（docs/需求规格.md 表 1-3），新增第四种状态要同时改 checks 与报告
STATUSES = ("通过", "警告", "不通过")


def load_settings(path=None) -> dict:
    """读 configs/settings.yaml，返回业务参数字典。

    业务数字只在这里出现（AGENTS.md 第 8 条）：清洗阈值、判定阈值都从这里传给函数。
    文件必须是 UTF-8；Windows 记事本默认 GBK，读出来会报错，这里换成人能看懂的提示。
    """
    p = SETTINGS_PATH if path is None else Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise UnicodeDecodeError(
            e.encoding, e.object, e.start, e.end,
            f"{p} 不是 UTF-8，请另存为 UTF-8 后重试",
        )
    return yaml.safe_load(text)
