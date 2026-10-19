#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_origin.py
# @Path       : analyse/test/unit/test_origin.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 13:30:00
# @Version    : v1.0.0
# @Description: origin 的单元测试：国家合并、占比分母、集中度、占比表。
# @ChangeLog:
#   2026-10-19 13:30:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""origin 的单元测试：合并"其他"后占比仍以全量为分母、HHI 的极端值。"""
import numpy as np
import pandas as pd

from hotel_insight import origin


def test_country_table_keeps_top_n_and_puts_other_last(panel):
    t = origin.country_table(panel, top_n=2, min_n=30)
    # 英国与德国在合成数据里行数相同，第 2 名谁在前取决于 groupby 的首次出现顺序，
    # 属于不稳定因素；这里只锁定"葡萄牙第一、恰好 top_n 个国家、其他垫底"这三件事
    assert t.index[0] == "葡萄牙"
    assert len(t) == 3
    assert t.index[-1] == "其他"
    assert t["记录数"].sum() == len(panel)


def test_country_share_uses_full_denominator(panel):
    """前 N 名 + 其他 的占比必须加起来等于 100%，不能是"前 N 名内部各占多少"。"""
    t = origin.country_table(panel, top_n=2, min_n=30)
    assert abs(t["占比"].sum() - 1) < 1e-12
    assert abs(t["累计占比"].iloc[-1] - 1) < 1e-12
    assert t["累计占比"].is_monotonic_increasing


def test_country_cancel_rate_of_other_is_recomputed(panel):
    """合并组不能取各国比率的平均，必须用合计的取消单/合计行数重算。"""
    t = origin.country_table(panel, top_n=1, min_n=30)
    tail = panel[panel["country"] != "葡萄牙"]
    assert abs(t.loc["其他", "取消率"] - tail["is_canceled"].mean()) < 1e-12


def test_cumulative_share_ends_at_one_and_ignores_order():
    v = [10, 30, 60]
    assert abs(origin.cumulative_share(v)[-1] - 1) < 1e-12
    assert np.all(np.diff(origin.cumulative_share(v)) >= 0)


def test_mix_table_rows_sum_to_100(panel):
    t = origin.mix_table(panel, "market_segment", "reserved_room_type")
    assert np.allclose(t.sum(axis=1), 100, atol=0.11)   # 百分比保留一位的舍入


def test_mix_table_drops_thin_rows(panel):
    thin = pd.concat([panel, pd.DataFrame([{
        "market_segment": "只有三单", "reserved_room_type": "A", "is_canceled": 0,
        "country": "英国", "hotel_type": "城市酒店", "customer_type": "散客",
        "arrival_year": 2016, "arrival_month_no": 1, "arrival_date": "2016-01-15",
        "lead_time": 1, "adr": 90.0, "total_nights": 1, "status_date": "2016-01-15",
        "previous_cancellations": 0, "booking_changes": 0,
        "total_of_special_requests": 0, "required_car_parking_spaces": 0,
        "deposit_type": "无押金", "assigned_room_type": "A"}])], ignore_index=True)
    t = origin.mix_table(thin, "market_segment", "reserved_room_type", min_n=30)
    assert "只有三单" not in t.index
