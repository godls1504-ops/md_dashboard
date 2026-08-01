# -*- coding: utf-8 -*-
"""차트 빌더 — 데이터프레임을 받아 plotly figure를 반환(순수 함수, streamlit 비의존).

설계: reports/dashboard_design.md. 이중축 금지, 범주 고정 색순서, 상태색 예약.
색은 색맹 안전(Okabe-Ito) 기반 임시값 — 빌드 폴리시 단계에서 팔레트 검증 예정.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from data_access import CAT_ORDER, POLICY_ORDER, STATUS_ORDER

# 범주(대분류) 고정 색순서 — Okabe-Ito
CAT_COLORS = {
    "여성": "#0072B2", "남성": "#E69F00", "아동": "#009E73",
    "장비": "#CC79A7", "용품": "#56B4E9", "스킨케어": "#D55E00",
}
# 정책초과 = 예약 상태색
POLICY_COLORS = {
    "리오더후보": "#0288D1", "정상": "#2E7D32", "주의": "#ED6C02",
    "클리어런스후보": "#C62828", "판정보류": "#9E9E9E",
}
LAYOUT = dict(margin=dict(l=10, r=10, t=40, b=10), plot_bgcolor="rgba(0,0,0,0)",
              paper_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-0.2))


def _won(x: float) -> str:
    return f"{x/1e8:.2f}억"


# ---------- 화면 ③ 재고 건전성 ----------
def fig_policy_stack(inv: pd.DataFrame) -> go.Figure:
    """정책초과 구성 — SKU수·재고금액 100% 스택 바(상태색)."""
    cnt = inv["정책초과"].value_counts()
    val = inv.groupby("정책초과")["inventory_value"].sum()
    totc, totv = max(cnt.sum(), 1), max(val.sum(), 1)
    fig = go.Figure()
    for k in POLICY_ORDER:
        fig.add_bar(
            y=["SKU 수", "재고금액"], orientation="h", name=k,
            x=[cnt.get(k, 0) / totc * 100, val.get(k, 0) / totv * 100],
            marker_color=POLICY_COLORS[k],
            customdata=[[cnt.get(k, 0)], [_won(val.get(k, 0))]],
            hovertemplate="%{y} · " + k + ": %{x:.1f}%% (%{customdata[0]})<extra></extra>")
    fig.update_layout(barmode="stack", title="정책초과 구성 (100%)",
                      xaxis_title="비중 %", **LAYOUT)
    return fig


def fig_wos_hist(inv: pd.DataFrame) -> go.Figure:
    """재고주수 분포 + 정책 임계 참조선. 아웃라이어 클립(60주)."""
    w = pd.to_numeric(inv["재고주수_WOS"], errors="coerce").dropna()
    clipped = int((w > 60).sum())
    fig = px.histogram(x=w.clip(upper=60), nbins=30)
    fig.update_traces(marker_color="#56B4E9",
                      hovertemplate="WOS %{x}주: %{y} SKU<extra></extra>")
    for v in sorted(pd.to_numeric(inv["reorder_point_wos"], errors="coerce").dropna().unique()):
        fig.add_vline(x=v, line_color="#0288D1", line_dash="dash",
                      annotation_text=f"리오더 {int(v)}", annotation_position="top")
    for v in sorted(pd.to_numeric(inv["clearance_point_wos"], errors="coerce").dropna().unique()):
        fig.add_vline(x=min(v, 60), line_color="#C62828", line_dash="dash",
                      annotation_text=f"클리어 {int(v)}", annotation_position="top")
    ttl = "재고주수(WOS) 분포"
    if clipped:
        ttl += f" · 60주↑ {clipped} SKU 클립"
    fig.update_layout(title=ttl, xaxis_title="재고주수(주)", yaxis_title="SKU 수", **LAYOUT)
    return fig


def fig_heatmap_wos(inv: pd.DataFrame) -> go.Figure:
    """대분류 × 시즌민감도 평균 WOS 히트맵(단일 hue 순차)."""
    w = inv.assign(wos=pd.to_numeric(inv["재고주수_WOS"], errors="coerce"))
    piv = w.pivot_table(index="대분류", columns="시즌민감도", values="wos", aggfunc="mean")
    piv = piv.reindex([c for c in CAT_ORDER if c in piv.index])
    fig = px.imshow(piv, color_continuous_scale="Blues", aspect="auto",
                    labels=dict(color="평균 WOS"), text_auto=".0f")
    fig.update_layout(title="대분류 × 시즌민감도 평균 재고주수", **LAYOUT)
    return fig


# ---------- 화면 ② 상품 성과 ----------
def fig_category_sales(prod: pd.DataFrame) -> go.Figure:
    g = prod.groupby("대분류").agg(순매출=("순매출", "sum"),
                                 공헌이익=("가용공헌이익", "sum")).reset_index()
    g["마진율"] = (g["공헌이익"] / g["순매출"] * 100).round(1)
    g = g.sort_values("순매출")
    fig = go.Figure(go.Bar(
        x=g["순매출"], y=g["대분류"], orientation="h",
        marker_color=[CAT_COLORS.get(c, "#999") for c in g["대분류"]],
        text=[f"{_won(v)} · 마진 {m}%" for v, m in zip(g["순매출"], g["마진율"])],
        textposition="outside",
        hovertemplate="%{y}: %{x:,.0f}원<extra></extra>"))
    fig.update_layout(title="대분류 순매출 · 마진율(라벨)", xaxis_title="순매출(원)", **LAYOUT)
    return fig


def fig_bubble(prod: pd.DataFrame) -> go.Figure:
    """성과 사분면: x=순매출, y=마진율, 크기=재고금액, 색=대분류."""
    p = prod.copy()
    p["마진율%"] = pd.to_numeric(p["마진율"], errors="coerce") * 100
    p = p.dropna(subset=["마진율%"])
    fig = px.scatter(p, x="순매출", y="마진율%", size="inventory_value", color="대분류",
                     category_orders={"대분류": CAT_ORDER}, color_discrete_map=CAT_COLORS,
                     hover_name="상품명", size_max=40)
    fig.update_layout(title="상품 성과 사분면 (버블=재고금액)",
                      xaxis_title="순매출(원)", yaxis_title="마진율(%)", **LAYOUT)
    return fig


def fig_channel(sales: pd.DataFrame, ch: pd.DataFrame) -> go.Figure:
    g = sales.groupby("channel_id").agg(순매출=("순매출", "sum"),
                                        공헌이익=("가용공헌이익", "sum")).reset_index()
    g = g.merge(ch, on="channel_id", how="left")
    g["마진율"] = (g["공헌이익"] / g["순매출"] * 100).round(1)
    g["수수료%"] = (pd.to_numeric(g["수수료율"], errors="coerce") * 100).round(1)
    g = g.sort_values("순매출")
    fig = go.Figure(go.Bar(
        x=g["순매출"], y=g["채널명"], orientation="h", marker_color="#0072B2",
        text=[f"{_won(v)} · 마진 {m}% · 수수료 {f}%" for v, m, f in
              zip(g["순매출"], g["마진율"], g["수수료%"])],
        textposition="outside", hovertemplate="%{y}: %{x:,.0f}원<extra></extra>"))
    fig.update_layout(title="채널 순매출 · 마진율 · 수수료", xaxis_title="순매출(원)", **LAYOUT)
    return fig


# ---------- 화면 ④ 추세 ----------
def fig_weekly(weekly: pd.DataFrame, col: str, title: str, color: str) -> go.Figure:
    g = weekly.groupby("iso_week")[col].sum().reset_index().sort_values("iso_week")
    fig = go.Figure(go.Scatter(x=g["iso_week"], y=g[col], mode="lines+markers",
                               line=dict(color=color, width=2)))
    if len(g):  # 마지막 주(부분주 가능) 강조
        last = g.iloc[-1]
        fig.add_annotation(x=last["iso_week"], y=last[col], text="부분주 주의",
                           showarrow=True, arrowhead=2, font=dict(color="#ED6C02"))
    fig.update_layout(title=title, xaxis_title="ISO 주", **LAYOUT)
    return fig


# ---------- 화면 ⑤ 액션 ----------
def fig_action_status(action: pd.DataFrame) -> go.Figure:
    g = action["action_status"].value_counts().reindex(STATUS_ORDER).fillna(0).reset_index()
    g.columns = ["상태", "건수"]
    fig = go.Figure(go.Bar(x=g["상태"], y=g["건수"], marker_color="#0072B2",
                           text=g["건수"].astype(int), textposition="outside"))
    fig.update_layout(title="액션 상태 분포", yaxis_title="건수", **LAYOUT)
    return fig
