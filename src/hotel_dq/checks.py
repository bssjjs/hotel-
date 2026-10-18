#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @File       : checks.py
# @Path       : analyse/src/hotel_dq/checks.py
# @Project    : hotel-dq
# @Author     : 一班第十二组
# @Date       : 2026-10-18 17:25:00
# @Version    : v1.0.0
# @Description: 16 项数据质量检查（DQ-01—DQ-16），返回与稽核表同结构的结果表。
# @ChangeLog:
#   2026-10-18 17:25:00 | 一班第十二组 | v1.0.0 | 初始化创建
"""
只会因为"16 项检查的定义变了"而改（AGENTS.md 第 2 条）。
纯计算（第 4.1 条）：输入一份 bookings 明细，输出结论表；不读库、不写库。
判定阈值一律从 settings["quality"] 取（第 8 条），代码里不写 0.5、0.1 这类字面量。

每项检查遵循"提出假设 → 用数据验证 → 量化证据 → 登记决定"四步（docs/需求规格.md 1.3）。
state 只有三种：通过 / 警告 / 不通过；判定标准见 docs/需求规格.md 表 1-3。
"""
import pandas as pd

from . import config
from .quality import COLUMNS, fmt_pct


def _months_span(d: pd.Series) -> tuple[int, str, str, dict]:
    """时间覆盖：月数、首月、末月、每年各有几个月。DQ-01 与 DQ-13 共用这一份口径。"""
    ok = d.dropna()
    months = ok.dt.to_period("M")
    per_year = months.groupby(months.dt.year).nunique().to_dict()
    return int(months.nunique()), f"{months.min()}", f"{months.max()}", per_year


def run_all(df: pd.DataFrame, settings: dict) -> pd.DataFrame:
    """跑完 16 项检查，返回列序 == quality.COLUMNS 的结果表。

    df 是原始层 bookings 的明细（含派生列）。检查只读，不改 df；
    需要"清洗后"数字的地方自己按 settings 算，不调用 dwd（否则检查与清洗会互相牵连）。
    """
    q = settings["quality"]
    p_clean = settings["cleaning"]
    rep = settings["reporting"]
    n = len(df)
    rows = []

    def add(check_id, dim, item, field, result, status, evidence="", decision=""):
        rows.append(dict(zip(COLUMNS, [check_id, dim, item, field, result, status,
                                       evidence, decision])))

    arrival = pd.to_datetime(df["arrival_date"], errors="coerce")
    status_date = pd.to_datetime(df["status_date"], errors="coerce")

    # ── 时效性 ──
    n_month, first, last, per_year = _months_span(arrival)
    y0, y1 = min(per_year), max(per_year)
    incomplete = {y: m for y, m in per_year.items() if m < 12}
    add("DQ-01", "时效性", "到达日期覆盖完整性", "bookings.arrival_date",
        f"{n_month} 个月，{first} 至 {last}", "警告" if incomplete else "通过",
        evidence="；".join(f"{y} 年仅 {m} 个月" for y, m in incomplete.items()),
        decision="分析范围限定在完整月份，不做整年同比")

    # ── 完整性 ──
    miss = df["company_id"].isna().sum()
    rate = miss / n
    add("DQ-02", "完整性", "整列高缺失字段：company_id", "bookings.company_id",
        f"缺失 {miss:,} 行（{fmt_pct(rate)}）",
        "不通过" if rate > q["high_missing"] else "警告" if rate else "通过",
        evidence="整列几乎为空，无法承担“按协议公司分析”的用途",
        decision="company_id 降级为“是否协议客户”二值标记")

    miss_children = int(df["children"].isna().sum())
    miss_country = int(df["country"].isna().sum())
    any_miss = int(df[["children", "country"]].isna().any(axis=1).sum())
    rate = any_miss / n
    add("DQ-03", "完整性", "关键业务字段缺失", "bookings.children / country",
        f"children {miss_children} 行、country {miss_country:,} 行，合计 {any_miss} 行（{fmt_pct(rate)}）",
        "通过" if rate < q["pass_threshold"] else "警告",
        evidence="缺失呈两极分布，不存在“每列都缺一点”的弥散型缺失",
        decision="保留 NULL，不填 0：填 0 会造出一个虚构的客源国")

    # ── 规范性 ──
    float_cols = [c for c in ("children", "agent_id", "company_id")
                  if pd.api.types.is_float_dtype(df[c]) and df[c].isna().any()
                  and (df[c].dropna() % 1 == 0).all()]
    add("DQ-04", "规范性", "数值字段存储类型", "bookings.children / agent_id / company_id",
        f"{len(float_cols)} 个编号列以浮点存储（含空值）" if float_cols else "编号列均为整数",
        "警告" if float_cols else "通过",
        evidence="CSV 导出时整列统一成浮点文本（如 240.0）；直接 pandas 读取会推断为 float64",
        decision="入库时按业务语义转整数；读 CSV 时显式指定 dtype")

    cn_month = df["arrival_month"].astype("string").str.match(r"^[一二三四五六七八九十]+月$").any()
    add("DQ-05", "规范性", "日期与月份编码", "bookings.arrival_month / arrival_date",
        "月份为中文文本、日期为字符串" if cn_month else "月份与日期均可直接计算",
        "警告" if cn_month else "通过",
        evidence="“七月”无法按时间排序；年/周/日拆成四列，无法做日期运算",
        decision="新增 arrival_month_no 与 arrival_date 两个派生列，原字段原样保留")

    # ── 唯一性 ──
    dup_mask = df.duplicated(subset=config.BUSINESS_COLS, keep="first")
    n_dup = int(dup_mask.sum())
    dup_rate = n_dup / n
    dup_cancel = df.loc[dup_mask, "is_canceled"].mean() if n_dup else 0.0
    add("DQ-06", "唯一性", "完全重复记录", "bookings（32 个业务字段）",
        f"{n_dup:,} 行（{fmt_pct(dup_rate)}）",
        "不通过" if dup_rate > q["dup_rate_fail"] else "警告" if n_dup else "通过",
        evidence=f"重复行中取消单占 {fmt_pct(dup_cancel)}，含重复口径会系统性高估取消率",
        decision="保留原始层；报数时并列含重复与去重两套口径")

    key = ["hotel_type", "arrival_date", "lead_time", "adults"]
    n_key_dup = int(df.duplicated(subset=key, keep=False).sum())
    add("DQ-07", "唯一性", "主键唯一性", "bookings.booking_id",
        f"代理主键 {df['booking_id'].nunique():,} 个 / {n:,} 行；业务组合键仍有 {n_key_dup:,} 行无法区分",
        "警告",
        evidence="booking_id 由入库时自增生成，不是业务主键；数据中没有订单号",
        decision="新增代理主键 booking_id，按订单计数时显式声明是否去重")

    # ── 一致性 ──
    st = df["reservation_status"]
    noshow_cancel = int(((st == "未到店") & (df["is_canceled"] == 1)).sum())
    add("DQ-08", "一致性", "状态码与取消标记", "bookings.reservation_status / is_canceled",
        f"未到店 {noshow_cancel:,} 行计入 is_canceled=1",
        "警告" if noshow_cancel else "通过",
        evidence=f"已取消 {int((st == '已取消').sum()):,} 行、已离店 {int((st == '已离店').sum()):,} 行",
        decision="需要区分时改用 reservation_status，不把“未到店”读作“取消”")

    dep_viol = int(((st == "已离店") & (status_date < arrival)).sum())
    can_viol = int(((st == "已取消") & (status_date > arrival)).sum())
    noshow_viol = int(((st == "未到店") & (status_date < arrival)).sum())
    viol = dep_viol + can_viol + noshow_viol
    add("DQ-09", "一致性", "状态日期与到达日期时序", "bookings.status_date / arrival_date",
        f"违规 {viol} 行",
        "通过" if viol / n < q["pass_threshold"] else "警告",
        evidence=f"已离店 {dep_viol} 行、已取消 {can_viol} 行、未到店 {noshow_viol} 行",
        decision="无需处理，可放心用于时长计算")

    # ── 准确性 ──
    n_zero = int((df["adr"] == 0).sum())
    n_neg = int((df["adr"] < 0).sum())
    n_high = int((df["adr"] > p_clean["adr_max"]).sum())
    bad = (df["adr"] <= p_clean["adr_min"]) | (df["adr"] > p_clean["adr_max"])
    bad_rate = bad.mean()
    add("DQ-10", "准确性", "房价异常值", "bookings.adr",
        f"0 值 {n_zero:,} 行、负值 {n_neg} 行、超 {p_clean['adr_max']:,} 的 {n_high} 行",
        "不通过" if bad_rate > q["adr_bad_fail"] else "警告" if bad.any() else "通过",
        evidence=f"异常合计 {int(bad.sum()):,} 行（{fmt_pct(bad_rate)}）；剔除后均值 "
                 f"{df.loc[~bad, 'adr'].mean():.2f}，全体均值 {df['adr'].mean():.2f}",
        decision="均价一律排除 0 值（SQL 侧用 NULLIF(adr, 0)）；极值单独核对")

    guests = df[["adults", "children", "babies"]].fillna(0).sum(axis=1)
    nights = df["stays_weekend"] + df["stays_weeknight"]
    no_guest = int((guests == 0).sum())
    zero_night = int((nights == 0).sum())
    either = int(((guests == 0) | (nights == 0)).sum())      # 两类会重叠，合计要按"或"去重
    add("DQ-11", "准确性", "无人入住与零晚数", "bookings.adults / children / babies / stays_*",
        f"无人入住 {no_guest} 行、零晚数 {zero_night} 行",
        "警告" if (no_guest or zero_night) else "通过",
        evidence=f"两类合计 {either} 行（{fmt_pct(either / n)}），业务上不成立",
        decision="进入转化率与客单价分析前剔除")

    lead_max = int(df["lead_time"].max())
    lead_bin = rep["lead_time_bin_max"]
    n_long = int((df["lead_time"] > lead_bin).sum())
    add("DQ-12", "准确性", "提前预订天数极值", "bookings.lead_time",
        f"最大 {lead_max} 天，超 {lead_bin} 天的 {n_long:,} 行（{fmt_pct(n_long / n)}）",
        "通过" if n_long / n <= q["lead_time_extreme_warn"] else "警告",
        evidence="长周期团队/会议预订在行业内合理，且占比低，不构成系统性问题",
        decision="不处理；做提前期分箱时末段单设“365 天以上”一箱")

    # ── 代表性 ──
    add("DQ-13", "代表性", "时段代表性", "bookings.arrival_date",
        f"完整年份只有 {rep['complete_year']}",
        "警告" if incomplete else "通过",
        evidence="；".join(f"{y} 年仅 {m} 个月" for y, m in incomplete.items()),
        decision="时间序列按完整月份筛选，不做 2015 与 2017 的整年同比")

    top_country = df["country"].value_counts().index[0]
    top_share = df["country"].value_counts(normalize=True).iloc[0]
    hotels = df["hotel_type"].nunique()
    add("DQ-14", "代表性", "客源与酒店覆盖", "bookings.country / hotel_type",
        f"{top_country}占 {fmt_pct(top_share)}，仅 {hotels} 家酒店",
        "不通过" if (hotels < q["min_hotels"] or top_share > q["top_country_share_fail"]) else "警告",
        evidence=f"客源国 {df['country'].nunique()} 个，前十位占 "
                 f"{fmt_pct(df['country'].value_counts().head(rep['top_country_n']).sum() / n)}",
        decision="结论限定在这两家酒店，不外推行业")

    add("DQ-15", "代表性", "样本圈选口径", "bookings（元数据缺失）",
        "库中无圈选说明，总体范围不可核", "警告",
        evidence="由客源结构与酒店类型推断为葡萄牙两家酒店，未获数据提供方确认",
        decision="书面确认圈选口径，交付物标注适用范围")

    # ── 准确性（元数据） ──
    codes = sorted(set(df["reserved_room_type"].dropna()) | set(df["assigned_room_type"].dropna()))
    single_letter = [c for c in codes if len(str(c)) == 1]
    un_market = int((df["market_segment"] == "未定义").sum())
    un_channel = int((df["distribution_channel"] == "未定义").sum())
    add("DQ-16", "准确性", "字典可解释性", "bookings.reserved_room_type / market_segment",
        f"房型代码 {len(single_letter)} 种单字母；市场细分“未定义” {un_market} 行、渠道“未定义” {un_channel} 行",
        "警告" if (single_letter or un_market or un_channel) else "通过",
        evidence="字典未说明 A—P 各对应何种房型，无法判断“升级/降级”的方向",
        decision="暂不开展房型价值分析，待提供方补齐代码表")

    return pd.DataFrame(rows, columns=COLUMNS)
