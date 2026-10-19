#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_room.py
# @Path       : analyse/test/unit/test_room.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-19 13:50:00
# @Version    : v1.0.0
# @Description: room 的单元测试：换房率只算未取消、交叉矩阵的小样本抑制。
# @ChangeLog:
#   2026-10-19 13:50:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""room 的单元测试：换房率的分母、流向表的范围、热力矩阵的样本抑制。"""
import numpy as np

from hotel_insight import room


def test_room_table_columns_are_contract(panel):
    t = room.room_table(panel)
    assert list(t.columns) == room.ROOM_COLS
    assert t["记录数"].sum() == len(panel)


def test_room_move_rate_ignores_cancelled(panel):
    """取消单没有真实分配，换房率的分母只能是未取消单。

    合成数据里所有 A 房型都换成了 D，若分母误用全量，A 的换房率会被稀释到
    "未取消占比" 那么多，而不是 100%。
    """
    t = room.room_table(panel)
    assert abs(t.loc["A", "换房率"] - 1.0) < 1e-12


def test_upgrade_flow_only_covers_stayed_bookings(panel):
    f = room.upgrade_flow(panel)
    assert f["单数"].sum() == (panel["is_canceled"] == 0).sum()
    assert abs(f["占比"].sum() - 1) < 1e-9
