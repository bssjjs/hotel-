#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : quality.py
# @Path       : analyse/src/hotel_insight/quality.py
# @Project    : hotel-insight
# @Author     : 一班第十二组
# @Date       : 2026-10-18 17:10:00
# @Version    : v1.0.0
# @Description: 字段画像与稽核结论的登记：profile / dq_record / summary。
# @ChangeLog:
#   2026-10-18 17:10:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
只会因为"稽核记录、数据画像的格式变了"而改（AGENTS.md 第 2 条）。
dq_record 是唯一写库的计算模块（第 4.2 条）：稽核结论必须落在库里，才能被报告直接引用。
"""
import pandas as pd

from . import config

STATUSES = config.STATUSES


def fmt_pct(p: float) -> str:
    """把比例写成百分比字符串，遵循图表规范第 6 节。

    不小于 10% 取整；1%–10% 保留一位小数；小于 1% 保留两位有效数字，避免出现 "0.0%"。
    报告正文、稽核证据、图上的标注都用这一个函数，免得同一份数据在三个地方写成三种精度。
    """
    v = p * 100
    if v == 0:
        return "0%"
    if v >= 10:
        return f"{v:.0f}%"
    if v >= 1:
        return f"{v:.1f}%"
    return f"{v:.2g}%"

# 稽核表的列序：与 docs/需求规格.md 附录 A 的检查明细一一对应
COLUMNS = ["check_id", "维度", "检查项", "表字段", "结果", "状态", "证据", "处理决定"]


def dq_record(con, check_id: str, dimension: str, item: str, field: str,
              result: str, status: str, evidence: str = "", decision: str = "") -> None:
    """把一条质量检查结果登记到 dq_check_result 表里，同一个 check_id 再运行会覆盖旧记录。

    为什么覆盖而不是追加：报告引用的是"最新一次结论"，追加会让同一编号出现多条，
    读的人分不清哪条算数。运行历史由 etl_log 负责，两张表各管一件事。
    """
    if status not in STATUSES:
        raise ValueError(f"状态只能是: {' / '.join(STATUSES)}，收到了: {status}")

    row = pd.DataFrame([dict(zip(COLUMNS, [check_id, dimension, item, field,
                                           result, status, evidence, decision]))])

    try:
        old = pd.read_sql("SELECT * FROM dq_check_result", con)
    except Exception:                      # 表还不存在：第一次运行
        old = row.iloc[0:0]
    new = pd.concat([old[old["check_id"] != check_id], row], ignore_index=True)
    new.to_sql("dq_check_result", con, if_exists="replace", index=False)
    n_old = len(old[old["check_id"] == check_id])
    overwrite = f"（覆盖 {n_old} 条旧记录）" if n_old else ""
    print(f"【{status}】{check_id} {dimension} | {item}: {result}{overwrite}")


def profile(df: pd.DataFrame) -> pd.DataFrame:
    """生成字段画像，每个字段输出一行统计信息。

    缺失值包括 NaN/None/NA，以及文本类字段（str、object、category）中
    去除首尾空白后为空的字符串。唯一值个数和示例值均基于非缺失值计算，
    保证各统计项的缺失口径一致。

    Args:
        df: 待分析的 DataFrame。允许 0 行、重复列名，以及包含 list、dict
            等不可哈希值的列。

    Returns:
        每个字段一行的 DataFrame，包含以下列：

        - 字段：列名。
        - 类型：pandas dtype 的字符串表示，如 "int64"、"str"。
        - 缺失数：缺失值个数（int）。
        - 缺失率：缺失数 / 总行数（float），0 行时为 0.0。
        - 唯一值个数：非缺失值的去重个数（int）。不可哈希的值按其字符串形式去重。
        - 示例值：第一个非缺失值；全部缺失时为 None。
    """
    n = len(df)
    rows = []
    for col, s in df.items():              # 按位置取列，列名重复也不会出错
        missing = s.isna()
        if (pd.api.types.is_string_dtype(s) or s.dtype == object
                or isinstance(s.dtype, pd.CategoricalDtype)):
            blank = s.astype("string").str.strip().eq("").fillna(False).astype(bool)
            missing = missing | blank
        valid = s[~missing]
        try:
            n_unique = int(valid.nunique())
        except TypeError:                  # 列里有 list/dict 等不可哈希的值
            n_unique = int(valid.astype(str).nunique())
        n_missing = int(missing.sum())
        rows.append({
            "字段": col,
            "类型": str(s.dtype),
            "缺失数": n_missing,
            "缺失率": n_missing / n if n else 0.0,
            "唯一值个数": n_unique,
            "示例值": valid.iloc[0] if len(valid) else None,
        })
    return pd.DataFrame(rows)


def summary(con) -> pd.DataFrame:
    """按"维度 × 状态"统计检查项数，给汇总图用。

    列序固定为 不通过 → 警告 → 通过：图要从危险到安全读，缺状态补 0 而不是消失。
    """
    dq = pd.read_sql("SELECT * FROM dq_check_result", con).sort_values("check_id")
    return (dq.pivot_table(index="维度", columns="状态", values="check_id",
                           aggfunc="count", fill_value=0)
              .reindex(columns=list(reversed(STATUSES)), fill_value=0))
