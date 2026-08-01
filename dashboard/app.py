# -*- coding: utf-8 -*-
"""가나 스윔 MD 대시보드 (Streamlit). data/marts만 읽고 계산하지 않는다.

실행: streamlit run dashboard/app.py  (사전: python -m src.run_pipeline)
"""
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))  # dashboard/ 모듈 임포트
import data_access as da  # noqa: E402
import viz  # noqa: E402

st.set_page_config(page_title="가나 스윔 MD 대시보드", layout="wide")


@st.cache_data
def _load():
    return da.load()


st.title("가나 스윔 · 시즌 중간 상품 운영/재고 진단")
st.caption("기준일 2026-07-31 · data/marts 기반 · 지표는 D1~D8 기본값 · 정책 임계는 교육용(정답 아님)")

if not da.marts_exist():
    st.error("마트 파일이 없습니다. 터미널에서 먼저 실행하세요:\n\n`python -m src.run_pipeline`")
    st.stop()

d = _load()

# ---- 필터 ----
st.sidebar.header("필터")
cats = st.sidebar.multiselect("대분류", da.CAT_ORDER, default=da.CAT_ORDER)
prod = d["mart_product_performance"]
inv = d["fct_inventory_asof_sku"]
sales = d["fct_sales_orderitem"]
action = d["mart_action_status"]
weekly = d["fct_weekly_product_trend"]
if cats:
    prod = prod[prod["대분류"].isin(cats)]
    inv = inv[inv["대분류"].isin(cats)]
    sales = sales[sales["대분류"].isin(cats)]
    action = action[action["대분류"].isin(cats)]
    weekly = weekly[weekly["product_id"].isin(prod["product_id"])]

t1, t3, t2, t4, t5 = st.tabs(
    ["① 요약", "③ 재고 건전성", "② 상품 성과", "④ 추세", "⑤ 액션"])

# ---- ① 요약 ----
with t1:
    rev = prod["순매출"].sum(); cm = prod["가용공헌이익"].sum()
    sold = prod["유효판매수량"].sum(); ret = prod["완료반품수량"].sum()
    invval = inv["inventory_value"].sum()
    wos = inv["available_qty"].sum() / max(inv["net_qty_28d"].sum() / 4, 1e-9)
    c = st.columns(4)
    c[0].metric("순매출", f"{rev/1e8:.2f}억")
    c[1].metric("가용공헌이익", f"{cm/1e8:.2f}억", f"{cm/rev*100:.1f}%" if rev else "-")
    c[2].metric("반품률", f"{ret/sold*100:.2f}%" if sold else "-")
    c[3].metric("재고금액 · 전사 WOS", f"{invval/1e8:.2f}억", f"{wos:.1f}주")
    st.divider()
    st.subheader("재고 경보")
    a = st.columns(3)
    cl = inv[inv["정책초과"] == "클리어런스후보"]
    ro = inv[inv["정책초과"] == "리오더후보"]
    dead = inv[inv["무판매과잉_플래그"]]
    a[0].metric("🔴 클리어런스 후보", f"{len(cl)} SKU", f"{cl['inventory_value'].sum()/1e8:.2f}억")
    a[1].metric("🔵 리오더 후보(발주중단)", f"{len(ro)} SKU", f"{ro['inventory_value'].sum()/1e8:.2f}억")
    a[2].metric("⚫ 무판매 과잉", f"{len(dead)} SKU", f"{dead['inventory_value'].sum()/1e8:.2f}억")

# ---- ③ 재고 건전성 ----
with t3:
    st.plotly_chart(viz.fig_policy_stack(inv), use_container_width=True)
    cc = st.columns(2)
    cc[0].plotly_chart(viz.fig_wos_hist(inv), use_container_width=True)
    cc[1].plotly_chart(viz.fig_heatmap_wos(inv), use_container_width=True)
    st.subheader("클리어런스 후보 (재고금액순)")
    cl = inv[inv["정책초과"] == "클리어런스후보"].copy()
    cl = cl.sort_values("inventory_value", ascending=False)
    st.dataframe(cl[["sku_id", "상품명", "색상", "사이즈", "재고주수_WOS",
                     "available_qty", "inventory_value", "net_qty_28d"]].head(30),
                 use_container_width=True)
    st.caption("발주 중단 상태 — 리오더 후보는 '재개 시' 관점. 소량 판매 SKU의 WOS는 불안정(표본 주의).")

# ---- ② 상품 성과 ----
with t2:
    st.plotly_chart(viz.fig_bubble(prod), use_container_width=True)
    cc = st.columns(2)
    cc[0].plotly_chart(viz.fig_category_sales(prod), use_container_width=True)
    cc[1].plotly_chart(viz.fig_channel(sales, d["channel"]), use_container_width=True)
    st.subheader("반품 위험 상품 (판매수 병기 · 표본 주의)")
    rr = prod.assign(반품률p=lambda x: x["반품률"].astype(float) * 100)
    rr = rr[rr["유효판매수량"] >= 30].sort_values("반품률p", ascending=False)
    st.dataframe(rr[["상품명", "대분류", "반품률p", "유효판매수량", "순매출", "마진율"]].head(15),
                 use_container_width=True)

# ---- ④ 추세 ----
with t4:
    cc = st.columns(2)
    cc[0].plotly_chart(viz.fig_weekly(weekly, "순매출", "주별 순매출", "#0072B2"),
                       use_container_width=True)
    cc[1].plotly_chart(viz.fig_weekly(weekly, "판매수량", "주별 판매수량", "#E69F00"),
                       use_container_width=True)
    st.caption("매출·물량을 분리 라인으로(이중축 금지). 마지막 주는 부분주라 낮게 보일 수 있음.")

# ---- ⑤ 액션 ----
with t5:
    cc = st.columns([1, 1])
    cc[0].plotly_chart(viz.fig_action_status(action), use_container_width=True)
    cc[1].subheader("진단 → 액션 갭")
    gap = prod[(prod["정책초과_클리어런스"] > 0) & (prod["액션수"] == 0)]
    cc[1].write(f"클리어런스 후보 SKU가 있으나 **액션 미등록** 상품: {len(gap)}개")
    cc[1].dataframe(gap[["상품명", "대분류", "정책초과_클리어런스", "inventory_value", "순매출"]]
                    .sort_values("inventory_value", ascending=False).head(15),
                    use_container_width=True)
