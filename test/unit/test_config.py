#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : test_config.py
# @Path       : analyse/test/unit/test_config.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:10:00
# @Description: config 的单元测试：根定位、口径常量、参数加载。
# @ChangeLog:
#   2026-10-18 18:10:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""config 的单元测试：根定位、口径常量、参数加载（纯计算 + 一次文件读取）。"""
import pytest

from hotel_insight import config


def test_find_project_root_hits_marker():
    root = config.find_project_root()
    assert (root / config.WORKSPACE_MARKER).is_file()
    assert root == config.PROJECT_ROOT


def test_find_project_root_raises_without_marker(monkeypatch, tmp_path):
    """没有标记文件时必须报错，而不是悄悄返回一个错目录（那样数据路径会全错）。"""
    fake = tmp_path / "a" / "b" / "config.py"
    fake.parent.mkdir(parents=True)
    fake.write_text("", encoding="utf-8")
    monkeypatch.setattr(config, "__file__", str(fake))
    with pytest.raises(FileNotFoundError):
        config.find_project_root()


def test_business_cols_are_32_and_exclude_keys():
    assert len(config.BUSINESS_COLS) == 32
    assert "booking_id" not in config.BUSINESS_COLS
    assert config.BUSINESS_COLS[-1] == "status_date"


def test_dwd_cols_order():
    """列序是契约：db 写入与下游读取都按这个顺序。"""
    assert config.DWD_COLS[0] == "booking_id"
    assert config.DWD_COLS[-1] == "month"
    assert len(config.DWD_COLS) == 1 + 32 + 4 + 1


def test_settings_have_cleaning_and_quality_thresholds():
    s = config.load_settings()
    assert s["cleaning"]["adr_max"] == 1000
    assert s["cleaning"]["keep_duplicate"] == "first"
    for key in ("pass_threshold", "high_missing", "dup_rate_fail", "adr_bad_fail"):
        assert 0 < s["quality"][key] <= 1
    assert s["reporting"]["complete_year"] == 2016
