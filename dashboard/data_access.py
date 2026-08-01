# -*- coding: utf-8 -*-
"""대시보드 데이터 접근 — data/marts만 읽는다(계산 없음). 표시용 경량 가공만."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
MARTS = BASE / "data" / "marts"
CONVERTED = BASE / "data" / "converted"
ENC = "utf-8-sig"

CAT_ORDER = ["여성", "남성", "아동", "장비", "용품", "스킨케어"]
POLICY_ORDER = ["리오더후보", "정상", "주의", "클리어런스후보", "판정보류"]
STATUS_ORDER = ["검토 전", "검토 중", "승인", "실행", "완료", "보류"]

MART_FILES = ["mart_product_performance", "fct_inventory_asof_sku",
              "fct_sales_orderitem", "fct_weekly_product_trend", "mart_action_status"]


def marts_exist() -> bool:
    return MARTS.exists() and all((MARTS / f"{n}.csv").exists() for n in MART_FILES)


def load() -> dict[str, pd.DataFrame]:
    d = {n: pd.read_csv(MARTS / f"{n}.csv", encoding=ENC) for n in MART_FILES}
    # 재고 마트: 대분류 보강 + 불리언 변환
    cat = pd.read_csv(CONVERTED / "category_master.csv", encoding=ENC)[["category_id", "대분류"]]
    inv = d["fct_inventory_asof_sku"].merge(cat, on="category_id", how="left")
    if inv["무판매과잉_플래그"].dtype == object:
        inv["무판매과잉_플래그"] = inv["무판매과잉_플래그"].astype(str).str.lower().eq("true")
    d["fct_inventory_asof_sku"] = inv
    d["channel"] = pd.read_csv(CONVERTED / "channel_master.csv", encoding=ENC)[
        ["channel_id", "채널명", "수수료율"]]
    return d
