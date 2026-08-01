# -*- coding: utf-8 -*-
"""상품 운영 진단 파이프라인.

승인 문서 기준 구현:
- 품질 처리: reports/eda_report.md, reports/xlsx_structure_review.md 「판단 분리」
- 지표 정의: reports/metric_definitions.md (지표 1~8, 결정 D1~D8)
- 마트 명세: reports/mart_design.md (마트 ①~⑤)

원칙: 원천 CSV(data/converted) 미수정. 검증 실패 시 마트를 성공으로 확정하지 않음.
계산식 주석의 [지표N]/[D#]는 metric_definitions.md ID와 연결된다.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
CONVERTED = BASE / "data" / "converted"
MARTS = BASE / "data" / "marts"
LOGS = BASE / "logs"
ENC = "utf-8-sig"

CUTOFF = pd.Timestamp("2026-07-31")          # 분석 기준일 (확정)
WINDOW_START = CUTOFF - timedelta(days=27)    # 최근 28일: 07-04 ~ 07-31 [지표6]

# --- 결정 파라미터 (metric_definitions.md 기본 제안값; 미확정 → 변경 시 여기만 수정) ---
DECISIONS = {
    "D1_partial_cancel": "qty=수량-canceled_qty, amount=canceled_amount",
    "D2_coupon_prorate": True,     # 쿠폰할인액을 유효수량 비례 배부
    "D3_completed_return": "처리상태='완료' AND 처리일<=기준일",
    "D4_cost_basis": "기준원가",   # (대안: purchase_order.단위원가)
    "D5_velocity": "판매일 기준 28일, 순판매수량(완료반품 차감)",
    "D6_wos_zero": "속도 0 → WOS null + 무판매과잉 플래그",
    "D7_price_dup": "판매단가 그대로 사용(상품할인액 중복차감 안 함), 검증으로 확인",
    "D8_season_match": "category_id 조인(정책 category 유일), season 정보 동반",
}

NUM = {  # 자료형 변환 대상 (ID·코드는 문자열 유지)
    "order_item": ["수량", "정상가", "판매단가", "상품할인액", "쿠폰할인액", "배송비배부액",
                   "채널수수료액", "canceled_qty", "canceled_amount", "payment_fee_amount",
                   "fulfillment_cost_amount", "packaging_cost_amount"],
    "returns": ["반품수량", "환불금액", "return_handling_cost", "return_shipping_cost"],
    "inventory_snapshot": ["available_qty", "on_hand_qty", "inventory_value",
                           "reserved_qty", "in_transit_qty", "damaged_qty"],
    "product_master": ["정상가", "기준원가", "리드타임_일"],
    "inventory_policy": ["target_wos_min", "target_wos_max", "reorder_point_wos", "clearance_point_wos"],
}
DATECOL = {
    "orders": ["주문일시"], "order_item": ["cancel_date"],
    "returns": ["접수일", "처리일"], "inventory_snapshot": ["snapshot_date"],
}

_LOG: list[str] = []


def log(msg: str) -> None:
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    _LOG.append(line)
    print(line)


# ----------------------------- 1. 로드 -----------------------------
def load() -> dict[str, pd.DataFrame]:
    tables = ["order_item", "orders", "returns", "sku_master", "product_master",
              "category_master", "inventory_snapshot", "inventory_policy",
              "channel_master", "action_log"]
    d = {}
    for t in tables:
        df = pd.read_csv(CONVERTED / f"{t}.csv", dtype=str, keep_default_na=False, encoding=ENC)
        d[t] = df
        log(f"load {t}: {len(df):,}행 x {len(df.columns)}열")
    return d


# ----------------------------- 2. 자료형 변환 -----------------------------
def cast_types(d: dict[str, pd.DataFrame]) -> None:
    for t, cols in NUM.items():
        for c in cols:
            if c in d[t].columns:
                d[t][c] = pd.to_numeric(d[t][c].str.strip().replace("", "0"), errors="coerce").fillna(0)
    for t, cols in DATECOL.items():
        for c in cols:
            if c in d[t].columns:
                s = d[t][c].astype(str).str.strip().replace("", pd.NA)
                d[t][c + "_dt"] = pd.to_datetime(s.str[:10], errors="coerce")
    log("cast_types 완료 (ID·코드는 문자열 유지, 날짜는 *_dt 파생)")


# ----------------------------- 3. 품질 플래그 -----------------------------
def quality_flags(d: dict[str, pd.DataFrame]) -> None:
    oi = d["order_item"]
    # [D1] 기준일 이후 취소(2건)는 미발생 → 유효 취소수량 0
    post_cancel = oi["cancel_date_dt"].notna() & (oi["cancel_date_dt"] > CUTOFF)
    oi["eff_canceled_qty"] = oi["canceled_qty"].where(~post_cancel, 0)
    log(f"품질: 기준일 이후 취소 {int(post_cancel.sum())}건 → 미발생 처리")

    r = d["returns"]
    # [D3] 완료 반품 = 처리상태='완료' AND 처리일<=기준일 (기준일 이후 7건 미완료 취급)
    completed = (r["처리상태"].str.strip() == "완료") & r["처리일_dt"].notna() & (r["처리일_dt"] <= CUTOFF)
    post_ret = r["처리일_dt"].notna() & (r["처리일_dt"] > CUTOFF)
    r["is_completed_return"] = completed
    log(f"품질: 완료 반품 {int(completed.sum())}건 / 기준일 이후 처리 {int(post_ret.sum())}건 미완료 취급 "
        f"/ 진행중(처리일 결측) {int(r['처리일_dt'].isna().sum())}건")


# ----------------------------- 4. 조인 + 5. 파생 (판매 마트 ①) -----------------------------
def build_sales_mart(d: dict[str, pd.DataFrame]) -> pd.DataFrame:
    oi = d["order_item"].copy()
    n0 = len(oi)
    # +orders (N:1)
    o = d["orders"][["order_id", "주문일시_dt", "channel_id", "주문상태"]]
    m = oi.merge(o, on="order_id", how="left"); _chk_rows("①+orders", n0, len(m))
    # 기준일 필터: 주문일 <= 기준일
    m = m[m["주문일시_dt"] <= CUTOFF].copy()
    log(f"① 기준일 필터 후: {len(m):,}행 (기준일 이후 주문 제외 {n0-len(m):,})")
    n1 = len(m)
    # +sku_master → +product_master → +category_master (모두 N:1)
    m = m.merge(d["sku_master"][["sku_id", "product_id"]], on="sku_id", how="left"); _chk_rows("①+sku", n1, len(m))
    m = m.merge(d["product_master"][["product_id", "category_id", "기준원가", "시즌", "상품명"]],
                on="product_id", how="left"); _chk_rows("①+product", n1, len(m))
    m = m.merge(d["category_master"][["category_id", "대분류", "시즌민감도"]],
                on="category_id", how="left"); _chk_rows("①+category", n1, len(m))
    # +returns 완료건만 (1:0..1)
    rc = d["returns"]
    rc = rc[rc["is_completed_return"]][["order_item_id", "반품수량", "환불금액",
                                        "return_handling_cost", "return_shipping_cost"]]
    if not rc["order_item_id"].is_unique:
        raise ValueError("returns.order_item_id 중복 → 1:0..1 위반, 조인 중단")
    m = m.merge(rc, on="order_item_id", how="left"); _chk_rows("①+returns(완료)", n1, len(m))
    for c in ["반품수량", "환불금액", "return_handling_cost", "return_shipping_cost"]:
        m[c] = m[c].fillna(0)

    # ---- 파생 지표 (계산식 ↔ 정의서 ID) ----
    m["유효판매수량"] = m["수량"] - m["eff_canceled_qty"]                       # [지표1][D1]
    m["완료반품수량"] = m["반품수량"]                                            # [지표2][D3]
    m["순판매수량"] = m["유효판매수량"] - m["완료반품수량"]                      # [지표2]
    ratio = (m["유효판매수량"] / m["수량"].where(m["수량"] != 0, 1))            # 유효수량 비율
    m["쿠폰차감"] = (m["쿠폰할인액"] * ratio) if DECISIONS["D2_coupon_prorate"] else m["쿠폰할인액"]  # [D2]
    m["매출_gross"] = m["판매단가"] * m["유효판매수량"]                          # [지표3][D1][D7]
    m["유효매출"] = m["매출_gross"] - m["쿠폰차감"]                              # [지표3][D2]
    m["순매출"] = m["유효매출"] - m["환불금액"]                                  # [지표3][D3]
    m["원가"] = m["기준원가"] * m["순판매수량"]                                  # [지표4][D4]
    m["반품처리비"] = m["return_handling_cost"] + m["return_shipping_cost"]      # [지표4][D3]
    m["가용공헌이익"] = m["순매출"] - (                                          # [지표4][D4]
        m["원가"] + m["채널수수료액"] + m["payment_fee_amount"]
        + m["fulfillment_cost_amount"] + m["packaging_cost_amount"] + m["반품처리비"])

    cols = ["order_item_id", "order_id", "sku_id", "product_id", "category_id",
            "channel_id", "주문일시_dt", "대분류", "시즌", "시즌민감도",
            "수량", "eff_canceled_qty", "유효판매수량", "완료반품수량", "순판매수량",
            "판매단가", "쿠폰차감", "순매출", "원가", "채널수수료액", "가용공헌이익",
            "환불금액", "반품처리비"]
    return m[cols]


# ----------------------------- 파생: SKU 28일 판매속도 [지표6] -----------------------------
def sku_velocity28(sales: pd.DataFrame) -> pd.DataFrame:
    w = sales[(sales["주문일시_dt"] >= WINDOW_START) & (sales["주문일시_dt"] <= CUTOFF)]
    v = w.groupby("sku_id")["순판매수량"].sum().rename("net_qty_28d")          # [지표6][D5]
    out = v.reset_index()
    out["velocity_wk"] = out["net_qty_28d"] / 4.0                              # 주 환산
    log(f"판매속도: 최근28일({WINDOW_START:%Y-%m-%d}~{CUTOFF:%Y-%m-%d}) SKU {len(out):,}개")
    return out


# ----------------------------- 재고 마트 ② -----------------------------
def build_inventory_mart(d: dict[str, pd.DataFrame], vel: pd.DataFrame) -> pd.DataFrame:
    inv = d["inventory_snapshot"]
    a = inv[inv["snapshot_date_dt"] == CUTOFF].copy()
    log(f"② 기준일 재고: {len(a):,}행")
    # SKU별 창고 합산 (N:M 회피: order_item과 직접 결합하지 않음)
    g = a.groupby("sku_id", as_index=False).agg(
        available_qty=("available_qty", "sum"),
        on_hand_qty=("on_hand_qty", "sum"),
        inventory_value=("inventory_value", "sum"))
    _chk_rows("②재고 SKU합산", g["sku_id"].nunique(), len(g))
    # +sku→product→category→policy (N:1 / 1:1)
    g = g.merge(d["sku_master"][["sku_id", "product_id", "색상", "사이즈"]], on="sku_id", how="left")
    g = g.merge(d["product_master"][["product_id", "category_id", "시즌", "상품명"]], on="product_id", how="left")
    g = g.merge(d["category_master"][["category_id", "시즌민감도"]], on="category_id", how="left")
    pol = d["inventory_policy"][["category_id", "season", "target_wos_min", "target_wos_max",
                                 "reorder_point_wos", "clearance_point_wos"]]
    if not pol["category_id"].is_unique:                                       # [D8]
        raise ValueError("inventory_policy.category_id 중복 → season 조인 필요")
    g = g.merge(pol, on="category_id", how="left")
    # +판매속도 (SKU 사전 집계 파생만 LEFT)
    g = g.merge(vel, on="sku_id", how="left")
    g["net_qty_28d"] = g["net_qty_28d"].fillna(0)
    g["velocity_wk"] = g["velocity_wk"].fillna(0)
    # WOS [지표7][D6]
    g["재고주수_WOS"] = g.apply(
        lambda r: (r["available_qty"] / r["velocity_wk"]) if r["velocity_wk"] > 0 else pd.NA, axis=1)
    g["무판매과잉_플래그"] = (g["velocity_wk"] == 0) & (g["available_qty"] > 0)   # [D6]
    # 정책 초과 여부 [지표8]
    def policy_flag(r):
        w = r["재고주수_WOS"]
        if pd.isna(w):
            return "판정보류"
        if w <= r["reorder_point_wos"]:
            return "리오더후보"
        if w >= r["clearance_point_wos"]:
            return "클리어런스후보"
        if w < r["target_wos_min"] or w > r["target_wos_max"]:
            return "주의"
        return "정상"
    g["정책초과"] = g.apply(policy_flag, axis=1)
    return g


# ----------------------------- 상품 성과 마트 ③ (누적, 상품 집계 후 1:1) -----------------------------
def build_product_mart(sales: pd.DataFrame, invmart: pd.DataFrame,
                       d: dict[str, pd.DataFrame]) -> pd.DataFrame:
    # 판매 → 상품 집계
    s = sales.groupby("product_id", as_index=False).agg(
        유효판매수량=("유효판매수량", "sum"), 순판매수량=("순판매수량", "sum"),
        완료반품수량=("완료반품수량", "sum"), 순매출=("순매출", "sum"),
        가용공헌이익=("가용공헌이익", "sum"), 환불금액=("환불금액", "sum"))
    # 재고 → 상품 집계 (order_item×snapshot 직접 결합 없음)
    inv = invmart.groupby("product_id", as_index=False).agg(
        available_qty=("available_qty", "sum"), inventory_value=("inventory_value", "sum"),
        net_qty_28d=("net_qty_28d", "sum"),
        정책초과_리오더=("정책초과", lambda x: (x == "리오더후보").sum()),
        정책초과_클리어런스=("정책초과", lambda x: (x == "클리어런스후보").sum()))
    m = s.merge(inv, on="product_id", how="outer")                            # 1:1 (상품 집계 후)
    _chk_rows("③상품 1:1결합", max(s["product_id"].nunique(), inv["product_id"].nunique()), len(m))
    m = m.merge(d["product_master"][["product_id", "상품명", "브랜드", "category_id",
                                     "시즌", "상품상태", "담당MD"]], on="product_id", how="left")
    m = m.merge(d["category_master"][["category_id", "대분류", "중분류", "시즌민감도"]],
                on="category_id", how="left")
    # 파생율
    m["마진율"] = m["가용공헌이익"] / m["순매출"].where(m["순매출"] != 0, pd.NA)     # 순매출 0 → 정의불가
    m["반품률"] = m["완료반품수량"] / m["유효판매수량"].where(m["유효판매수량"] != 0, pd.NA)  # [지표5]
    m["상품WOS"] = (m["available_qty"] / (m["net_qty_28d"] / 4.0).where(m["net_qty_28d"] > 0, pd.NA))  # [지표7]
    # 액션 상태 요약 (상품 단위)
    al = d["action_log"].groupby("product_id", as_index=False).agg(
        액션수=("action_id", "count"),
        최근액션=("recommended_action", "last"), 액션상태=("action_status", "last"))
    m = m.merge(al, on="product_id", how="left")
    m["액션수"] = m["액션수"].fillna(0).astype(int)
    return m


# ----------------------------- 주·상품 추세 마트 ④ (추세, 누적과 분리) -----------------------------
def build_weekly_trend(sales: pd.DataFrame) -> pd.DataFrame:
    s = sales.copy()
    s["iso_week"] = s["주문일시_dt"].dt.strftime("%G-W%V")
    g = s.groupby(["iso_week", "product_id"], as_index=False).agg(
        판매수량=("유효판매수량", "sum"), 순판매수량=("순판매수량", "sum"),
        순매출=("순매출", "sum"))
    log(f"④ 주·상품 추세: {len(g):,}행 (주 {s['iso_week'].nunique()} x 상품)")
    return g


# ----------------------------- 액션 상태 마트 ⑤ -----------------------------
def build_action_mart(d: dict[str, pd.DataFrame]) -> pd.DataFrame:
    a = d["action_log"].merge(
        d["product_master"][["product_id", "상품명", "category_id"]], on="product_id", how="left")
    a = a.merge(d["category_master"][["category_id", "대분류"]], on="category_id", how="left")
    cols = ["action_id", "product_id", "상품명", "대분류", "recommended_action",
            "action_status", "priority", "owner", "expected_effect", "due_date"]
    _chk_rows("⑤액션", len(d["action_log"]), len(a))
    return a[[c for c in cols if c in a.columns]]


# ----------------------------- 검증 -----------------------------
def _chk_rows(step: str, expected: int, actual: int) -> None:
    ok = expected == actual
    log(f"조인 {step}: 기대 {expected:,} / 실측 {actual:,} {'OK' if ok else '!! 불일치'}")


def validate(sales, invmart, prodmart, weekly, action, d) -> list[tuple]:
    V = []

    def add(name, expected, actual):
        st = "PASS" if expected == actual else "FAIL"
        V.append((name, expected, actual, st))
        log(f"검증 {name}: 기대={expected} 실측={actual} → {st}")

    # 행 수
    n_oi_cut = int((d["order_item"].merge(d["orders"][["order_id", "주문일시_dt"]], on="order_id", how="left")["주문일시_dt"] <= CUTOFF).sum())
    add("①판매 행수=기준일이하 order_item", n_oi_cut, len(sales))
    add("②재고 행수=기준일 distinct SKU", d["inventory_snapshot"].loc[d["inventory_snapshot"]["snapshot_date_dt"] == CUTOFF, "sku_id"].nunique(), len(invmart))
    add("⑤액션 행수=action_log", len(d["action_log"]), len(action))
    # PK 중복
    for name, df, pk in [("①", sales, "order_item_id"), ("②", invmart, "sku_id"),
                         ("③", prodmart, "product_id"), ("⑤", action, "action_id")]:
        add(f"{name}PK 중복0 {pk}", 0, int(len(df) - df[pk].nunique()))
    add("④PK 중복0 (주,상품)", 0, int(len(weekly) - weekly.groupby(["iso_week", "product_id"]).ngroups))
    # 합계 정합
    add("순매출 ①합=③합(원)", int(round(sales["순매출"].sum())), int(round(prodmart["순매출"].sum())))
    add("환불 ①합=완료반품 환불합(원)",
        int(round(d["returns"].loc[d["returns"]["is_completed_return"], "환불금액"].sum())),
        int(round(sales["환불금액"].sum())))
    add("재고금액 ②합=기준일 스냅샷합(원)",
        int(round(d["inventory_snapshot"].loc[d["inventory_snapshot"]["snapshot_date_dt"] == CUTOFF, "inventory_value"].sum())),
        int(round(invmart["inventory_value"].sum())))
    add("판매수량 ①합=④합", int(round(sales["유효판매수량"].sum())), int(round(weekly["판매수량"].sum())))
    return V


# ----------------------------- 저장 -----------------------------
def save_all(marts: dict[str, pd.DataFrame]) -> None:
    MARTS.mkdir(parents=True, exist_ok=True)
    for name, df in marts.items():
        p = MARTS / f"{name}.csv"
        df.to_csv(p, index=False, encoding=ENC)
        log(f"저장 {p.name}: {len(df):,}행")


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    log("=== 파이프라인 시작 ===")
    log(f"결정 파라미터(D1~D8): {DECISIONS}")
    d = load()
    cast_types(d)
    quality_flags(d)

    sales = build_sales_mart(d)                 # ①
    vel = sku_velocity28(sales)
    invmart = build_inventory_mart(d, vel)      # ②
    prodmart = build_product_mart(sales, invmart, d)  # ③
    weekly = build_weekly_trend(sales)          # ④
    action = build_action_mart(d)               # ⑤

    marts = {
        "fct_sales_orderitem": sales,
        "fct_inventory_asof_sku": invmart,
        "mart_product_performance": prodmart,
        "fct_weekly_product_trend": weekly,
        "mart_action_status": action,
    }

    V = validate(sales, invmart, prodmart, weekly, action, d)
    fails = [v for v in V if v[3] == "FAIL"]

    if fails:
        log("!!! 검증 실패 → 마트를 성공으로 확정하지 않음(미저장)")
        for name, exp, act, _ in fails:
            log(f"  실패: {name} (기대 {exp} != 실측 {act})")
        _write_log()
        print("\n[수정 범위] 위 실패 항목의 조인 키/필터/집계 로직 점검 필요. 원천 CSV는 수정하지 말 것.")
        return 1

    save_all(marts)
    log(f"=== 완료: 마트 {len(marts)}개, 검증 {len(V)}건 전부 PASS ===")
    _write_log()
    return 0


def _write_log() -> None:
    p = LOGS / f"pipeline_run_{datetime.now():%Y%m%d_%H%M%S}.log"
    p.write_text("\n".join(_LOG), encoding=ENC)
    print(f"실행 로그: {p}")


if __name__ == "__main__":
    raise SystemExit(main())
