#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : __init__.py
# @Path       : analyse/src/hotel_insight/__init__.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 17:30:00
# @Version    : v2.1.0
# @Description: hotel_insight 包入口：只声明版本，不 import 子模块。
# @ChangeLog:
#   2026-10-18 17:30:00 | 一班第十二组 | v1.0.0 | 初始化创建
#   2026-10-19 18:00:00 | 一班第十二组 | v2.0.0 | 对齐v2.0里程碑; 原 __version__ 停在 0.1.0 与文件头版本号不一致, 一并纠正
#   2026-10-19 10:45:00 | 一班第十二组 | v2.1.0 | 清理四个未被调用的分析函数, country_table 改用 cumulative_share
"""
import 本包时不做任何事（AGENTS.md 第 7 条）：不连库、不读配置、不改 rcParams。
子模块由调用方显式 import：from hotel_insight import config, dwd, checks, viz
"""
__version__ = "2.1.0"
