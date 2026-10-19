#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : conftest.py
# @Path       : analyse/test/conftest.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 18:06:00
# @Description: pytest 根配置：共享 fixture 与命令行参数。
# @ChangeLog:
#   2026-10-18 18:06:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
运行方式（项目根目录）：
    python -m pytest                 # 全部测试（不含真实库对账）
    python -m pytest --run-smoke     # 加跑 data/hotel.db 的对账测试

hotel_insight 的导入路径由 pyproject.toml 的 [tool.pytest.ini_options] pythonpath 提供，
这里不 hack sys.path，也不依赖 pip install -e。
"""
import sqlite3

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: 依赖真实数据库 data/hotel.db 的对账测试")


def pytest_addoption(parser):
    parser.addoption(
        "--run-smoke",
        action="store_true",
        default=False,
        help="运行依赖真实数据库 data/hotel.db 的对账测试（默认跳过）",
    )


def pytest_collection_modifyitems(config, items):
    """不给 --run-smoke 时，跳过所有标了 smoke 的测试：CI 和没有 data/ 的机器照常跑。"""
    if config.getoption("--run-smoke"):
        return
    skip = pytest.mark.skip(reason="需要 --run-smoke 才运行（依赖真实 data/hotel.db）")
    for item in items:
        if "smoke" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def con():
    """内存 SQLite 连接：每个测试一个独立的库，测试结束自动关闭。"""
    c = sqlite3.connect(":memory:")
    yield c
    c.close()


@pytest.fixture(scope="session")
def settings():
    """configs/settings.yaml 的内容。只读，所以整个测试会话共用一份。"""
    from hotel_insight import config
    return config.load_settings()


@pytest.fixture(scope="session")
def panel():
    """多维合成数据（1,296 行，见 sample_data.make_panel）。

    返回的是**副本**：分析函数承诺不改入参，但测试之间共享一个 DataFrame 时，
    只要有一个函数偷偷改了列，后面的断言就会莫名其妙地错。
    每个用到它的测试自己 .copy()，比追查"谁改的"便宜。
    """
    from sample_data import make_panel
    return make_panel()
