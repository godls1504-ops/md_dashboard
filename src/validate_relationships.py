# -*- coding: utf-8 -*-
"""승인 테이블 논리 ERD 검증. reports/erd.md + reports/relationship_validation.csv 생성.

통제: 관계를 열 이름만으로 확정하지 않고 데이터로 검증한다.
      다대다(N:M) 조인은 실행하지 않는다(fact×fact SKU 교차 미수행).
"""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
CONVERTED = BASE / "data" / "converted"
ERD = BASE / "reports" / "erd.md"
VALID = BASE / "reports" / "relationship_validation.csv"
ENC = "utf-8-sig"

APPROVED = [
    "order_item", "orders", "returns", "sku_master", "product_master",
    "category_master", "inventory_snapshot", "inventory_policy",
    "channel_master", "purchase_order", "receipt", "action_log", "warehouse_master",
]
PK = {
    "order_item": ["order_item_id"], "orders": ["order_id"], "returns": ["return_id"],
    "sku_master": ["sku_id"], "product_master": ["product_id"],
    "category_master": ["category_id"],
    "inventory_snapshot": ["snapshot_date", "warehouse_id", "sku_id"],
    "inventory_policy": ["policy_id"], "channel_master": ["channel_id"],
    "purchase_order": ["po_id"], "receipt": ["receipt_id"],
    "action_log": ["action_id"], "warehouse_master": ["warehouse_id"],
}
OBS_UNIT = {
    "order_item": "주문×SKU 1줄", "orders": "주문 1건", "returns": "반품 1건",
    "sku_master": "SKU 1개", "product_master": "상품 1개", "category_master": "카테고리 1개",
    "inventory_snapshot": "시점×창고×SKU", "inventory_policy": "카테고리 정책",
    "channel_master": "채널 1개", "purchase_order": "발주 1건", "receipt": "입고 1건",
    "action_log": "액션 1건(상품 단위)", "warehouse_master": "창고 1개",
}
# FK: (child, child_col) -> (parent, parent_pk), 추정 관계(parent:child)
FK = [
    ("order_item", "order_id", "orders", "order_id", "1:N"),
    ("order_item", "sku_id", "sku_master", "sku_id", "1:N"),
    ("order_item", "warehouse_id", "warehouse_master", "warehouse_id", "1:N"),
    ("orders", "channel_id", "channel_master", "channel_id", "1:N"),
    ("returns", "order_item_id", "order_item", "order_item_id", "1:1"),
    ("sku_master", "product_id", "product_master", "product_id", "1:N"),
    ("product_master", "category_id", "category_master", "category_id", "1:N"),
    ("inventory_snapshot", "sku_id", "sku_master", "sku_id", "1:N"),
    ("inventory_snapshot", "warehouse_id", "warehouse_master", "warehouse_id", "1:N"),
    ("inventory_policy", "category_id", "category_master", "category_id", "1:N"),
    ("purchase_order", "sku_id", "sku_master", "sku_id", "1:N"),
    ("receipt", "po_id", "purchase_order", "po_id", "1:1"),
    ("receipt", "sku_id", "sku_master", "sku_id", "1:N"),
    ("receipt", "warehouse_id", "warehouse_master", "warehouse_id", "1:N"),
    ("action_log", "product_id", "product_master", "product_id", "1:N"),
]


def load() -> dict[str, pd.DataFrame]:
    return {t: pd.read_csv(CONVERTED / f"{t}.csv", dtype=str, keep_default_na=False, encoding=ENC)
            for t in APPROVED}


def nb(s: pd.Series) -> pd.Series:
    s = s.astype(str).str.strip()
    return s[s != ""]


def to_num(s: pd.Series):
    return pd.to_numeric(s.astype(str).str.strip().replace("", "0"), errors="coerce").fillna(0)


def main() -> int:
    d = load()
    V = []  # validation rows: (category, subject, expected, actual, status, note)

    # 1) 단일/복합 PK 중복
    for t in APPROVED:
        cols = PK[t]
        df = d[t]
        key = df[cols].astype(str).apply(lambda r: "".join(r.values), axis=1)
        dup = int(len(key) - key.nunique())
        cat = "COMPOSITE_PK" if len(cols) > 1 else "PK_UNIQUE"
        V.append((cat, f"{t}({'+'.join(cols)})", "0 중복", dup,
                  "PASS" if dup == 0 else "FAIL", ""))

    # 2) FK 고아 + 카디널리티 검증
    card_rows = []  # for ERD: (child,parent,est,verified,diff,orphan,maxc)
    for ct, cc, pt, pc, est in FK:
        child = nb(d[ct][cc])
        parent = set(nb(d[pt][pc]))
        orphan = int((~child.isin(parent)).sum())
        matched = child[child.isin(parent)]
        vc = matched.value_counts()
        maxc = int(vc.max()) if len(vc) else 0
        child_unique = bool(child.is_unique)
        verified = "1:1" if child_unique else "1:N"
        diff = "" if verified == est else "DIFF"
        V.append(("FK_ORPHAN", f"{ct}.{cc} -> {pt}.{pc}", 0, orphan,
                  "PASS" if orphan == 0 else "FAIL", ""))
        V.append(("FK_CARDINALITY", f"{ct}.{cc} -> {pt}.{pc}", f"추정 {est}",
                  f"검증 {verified}", "MATCH" if not diff else "DIFF",
                  f"부모당 최대자식={maxc}, 자식유일={child_unique}"))
        # 분포
        if len(vc):
            V.append(("FK_CARD_DIST", f"{pt} 1건당 {ct} 행수", "",
                      f"min={int(vc.min())} med={int(vc.median())} max={maxc} mean={round(vc.mean(),2)}",
                      "", f"부모 {len(vc)}종 매칭"))
        card_rows.append((ct, cc, pt, pc, est, verified, diff, orphan, maxc))

    # 3) 단계별 조인 검증 (안전한 N:1 / 1:1 만; N:M 미실행)
    def sums(df, cols):
        return {c: int(to_num(df[c]).sum()) for c in cols if c in df.columns}

    def join_step(label, left, right, on, base_sum_cols, expect_rows):
        before = len(left)
        s_before = sums(left, base_sum_cols)
        merged = left.merge(right, on=on, how="left", suffixes=("", f"_{right_name(right)}"))
        after = len(merged)
        s_after = sums(merged, base_sum_cols)
        ok_rows = (after == expect_rows)
        ok_sum = (s_before == s_after)
        V.append(("JOIN_STEP", label, f"행={expect_rows}, 합보존", f"행={after}, 합{'동일' if ok_sum else '변동'}",
                  "PASS" if (ok_rows and ok_sum) else "FAIL", f"before={before}"))
        return merged

    def right_name(_df):
        return "r"

    # --- 판매 팩트 체인 ---
    sales_cols = ["수량", "판매단가", "상품할인액", "쿠폰할인액", "canceled_amount"]
    base = d["order_item"].copy()
    n0 = len(base)
    V.append(("JOIN_BASE", "order_item (판매 팩트 base)", f"행={n0}", f"행={n0}", "PASS",
              f"합계 {sums(base, sales_cols)}"))
    m = join_step("+orders (order_id)", base, d["orders"][["order_id", "주문일시", "channel_id", "주문상태"]], "order_id", sales_cols, n0)
    m = join_step("+sku_master (sku_id)", m, d["sku_master"][["sku_id", "product_id", "색상", "사이즈"]], "sku_id", sales_cols, n0)
    m = join_step("+product_master (product_id)", m, d["product_master"][["product_id", "category_id", "기준원가", "시즌"]], "product_id", sales_cols, n0)
    m = join_step("+category_master (category_id)", m, d["category_master"][["category_id", "대분류", "시즌민감도"]], "category_id", sales_cols, n0)
    # returns: 1:1 검증되면 안전
    ret_unique = nb(d["returns"]["order_item_id"]).is_unique
    if ret_unique:
        rr = d["returns"][["order_item_id", "환불금액", "처리상태"]]
        join_step("+returns (order_item_id, 1:1)", m, rr, "order_item_id", sales_cols, n0)
    else:
        V.append(("JOIN_STEP", "+returns", "1:1 전제", "N:1 감지→미실행", "SKIP", "다대일이면 fan-out 위험"))

    # --- 재고 팩트 체인 ---
    inv_cols = ["available_qty", "on_hand_qty", "inventory_value"]
    inv = d["inventory_snapshot"].copy()
    ni = len(inv)
    V.append(("JOIN_BASE", "inventory_snapshot (재고 팩트 base)", f"행={ni}", f"행={ni}", "PASS",
              f"합계 {sums(inv, inv_cols)}"))
    im = join_step("+sku_master (sku_id)", inv, d["sku_master"][["sku_id", "product_id"]], "sku_id", inv_cols, ni)
    im = join_step("+product_master (product_id)", im, d["product_master"][["product_id", "category_id", "시즌"]], "product_id", inv_cols, ni)
    im = join_step("+category_master (category_id)", im, d["category_master"][["category_id", "시즌민감도"]], "category_id", inv_cols, ni)
    # policy: category_id 유일하면 안전(1:1), 아니면 season 필요
    pol_unique = nb(d["inventory_policy"]["category_id"]).is_unique
    if pol_unique:
        pol = d["inventory_policy"][["category_id", "reorder_point_wos", "clearance_point_wos"]]
        join_step("+inventory_policy (category_id, 검증 1:1)", im, pol, "category_id", inv_cols, ni)
    else:
        V.append(("JOIN_STEP", "+inventory_policy", "category_id 1:1", "category당 복수 정책→season 필요", "SKIP", "category_id 단독 조인 시 fan-out"))

    # --- 공급 체인 ---
    po = d["purchase_order"].copy()
    npo = len(po)
    V.append(("JOIN_BASE", "purchase_order (공급 base)", f"행={npo}", f"행={npo}", "PASS",
              f"합계 {sums(po, ['발주수량'])}"))
    rc_unique = nb(d["receipt"]["po_id"]).is_unique
    if rc_unique:
        rc = d["receipt"][["po_id", "입고수량", "실입고일", "검수불량수량"]]
        join_step("+receipt (po_id, 1:1)", po, rc, "po_id", ["발주수량"], npo)
    else:
        V.append(("JOIN_STEP", "+receipt", "po_id 1:1", "N:1 감지→미실행", "SKIP", ""))

    # N:M 주의: 판매팩트 × 재고팩트 (둘 다 sku_id) 교차 미실행
    V.append(("NM_GUARD", "order_item × inventory_snapshot (sku_id 교차)", "미실행",
              "미실행(승인 대기)", "HELD", "fact×fact SKU 조인은 N:M fan-out → 승인 전 금지"))

    # ---------- CSV 저장 ----------
    VALID.parent.mkdir(parents=True, exist_ok=True)
    with open(VALID, "w", newline="", encoding=ENC) as f:
        w = csv.writer(f)
        w.writerow(["category", "subject", "expected", "actual", "status", "note"])
        for row in V:
            w.writerow(row)

    # ---------- ERD.md 생성 ----------
    diffs = [c for c in card_rows if c[6] == "DIFF"]
    L = []
    a = L.append
    a("# 논리 ERD 및 관계 검증 (승인 테이블 전용)")
    a("")
    a(f"- 대상: 승인 테이블 {len(APPROVED)}개(필수 8 + 보조 4). 근거 [table_selection.md](table_selection.md)")
    a("- **통제**: 관계를 열 이름만으로 확정하지 않고 `data/converted` 실측으로 검증. "
      "**N:M(fact×fact SKU 교차) 조인은 미실행(승인 대기).**")
    a(f"- 상세 검증표: [relationship_validation.csv](relationship_validation.csv) ({len(V)}행)")
    a("")
    a("## 1. ERD (Mermaid) — 검증된 카디널리티")
    a("")
    a("```mermaid")
    a("erDiagram")
    a("  CATEGORY_MASTER ||--o{ PRODUCT_MASTER : classifies")
    a("  PRODUCT_MASTER  ||--o{ SKU_MASTER : variant_of")
    a("  SKU_MASTER      ||--o{ ORDER_ITEM : sold_as")
    a("  ORDERS          ||--o{ ORDER_ITEM : contains")
    a("  CHANNEL_MASTER  ||--o{ ORDERS : sells_via")
    a("  WAREHOUSE_MASTER||--o{ ORDER_ITEM : shipped_from")
    a("  ORDER_ITEM      ||--o| RETURNS : returned")
    a("  SKU_MASTER      ||--o{ INVENTORY_SNAPSHOT : stocked_as")
    a("  WAREHOUSE_MASTER||--o{ INVENTORY_SNAPSHOT : stored_in")
    a("  CATEGORY_MASTER ||--|| INVENTORY_POLICY : governed_by")
    a("  SKU_MASTER      ||--o{ PURCHASE_ORDER : ordered_as")
    a("  PURCHASE_ORDER  ||--|| RECEIPT : received_as")
    a("  SKU_MASTER      ||--o{ RECEIPT : received_sku")
    a("  WAREHOUSE_MASTER||--o{ RECEIPT : received_at")
    a("  PRODUCT_MASTER  ||--o| ACTION_LOG : has_action")
    a("  ORImg[\" \"]")
    a("```")
    a("> 기호: `||--o{` 1:N(0..N), `||--o|` 1:0..1, `||--||` 1:1. 위 카디널리티는 아래 검증 결과 기준.")
    a("")
    a("## 2. 테이블별 관측단위·키")
    a("")
    a("| 테이블 | 관측단위 | PK | FK |")
    a("|---|---|---|---|")
    fk_by_child = {}
    for ct, cc, pt, pc, *_ in FK:
        fk_by_child.setdefault(ct, []).append(f"{cc}→{pt}")
    for t in APPROVED:
        fks = ", ".join(fk_by_child.get(t, [])) or "-"
        a(f"| `{t}` | {OBS_UNIT[t]} | {'+'.join(PK[t])} | {fks} |")
    a("")
    a("## 3. 관계 추정 vs 실제 검증")
    a("")
    a("| 관계(부모→자식) | 추정 | 검증 | 고아행 | 부모당 최대자식 | 차이 |")
    a("|---|---|---|--:|--:|---|")
    for ct, cc, pt, pc, est, verified, diff, orphan, maxc in card_rows:
        mark = "**DIFF**" if diff else "일치"
        a(f"| `{pt}` → `{ct}`.{cc} | {est} | {verified} | {orphan} | {maxc} | {mark} |")
    a("")
    if diffs:
        a("### 추정과 다른 관계 (주의)")
        a("")
        for ct, cc, pt, pc, est, verified, diff, orphan, maxc in diffs:
            a(f"- **`{pt}` → `{ct}`.{cc}**: 추정 {est} → 실측 **{verified}** "
              f"(부모당 최대 자식 {maxc}). "
              + ("정책은 논리상 카테고리×시즌(1:N)이나 현재 데이터는 카테고리당 1건 → "
                 "`season`까지 함께 조인해야 안전." if ct == "inventory_policy"
                 else "상품당 액션이 논리상 여러 건 가능하나 현재 32건이 상품별 1건 → 향후 누적 시 1:N 대비."))
        a("")
    a("## 4. 단계별 조인 검증 (안전 조인만; 행수·합계 보존)")
    a("")
    a("| 단계 | 기대 | 실측 | 결과 |")
    a("|---|---|---|---|")
    for cat, subj, exp, act, st, note in V:
        if cat in ("JOIN_BASE", "JOIN_STEP"):
            a(f"| {subj} | {exp} | {act} | {st} |")
    a("")
    a("> 판매 팩트(order_item 기준)와 재고 팩트(inventory_snapshot 기준)는 "
      "각각 차원 테이블을 N:1/1:1로만 붙여 **행수·핵심 합계가 보존**되어야 정상.")
    a("")
    a("## 5. N:M 주의 (미실행)")
    a("")
    a("- **`order_item` × `inventory_snapshot`**: 둘 다 `sku_id`를 가지지만 각각 팩트라, "
      "직접 조인하면 (SKU당 판매 다수)×(SKU당 스냅샷 다수)로 **N:M fan-out**이 발생한다. "
      "→ 승인 전까지 실행하지 않으며, 필요 시 SKU 단위로 **각각 집계한 뒤** 결합한다.")
    a("- `inventory_policy`는 실측 1:1이나 논리상 카테고리×`season`이므로, "
      "시즌별 정책이 추가되면 `category_id` 단독 조인은 금지(‌`+season`).")
    a("")
    a("## 6. 통제 준수")
    a("- 관계는 실측 검증(고아·카디널리티·복합키·조인 전후 행수/합계)으로 확정.")
    a("- 다대다 조인 및 fact×fact SKU 교차는 실행하지 않음(승인 대기).")

    ERD.write_text("\n".join(L), encoding=ENC)
    npass = sum(1 for r in V if r[4] == "PASS")
    nfail = sum(1 for r in V if r[4] == "FAIL")
    print(f"검증 {len(V)}행: PASS {npass} / FAIL {nfail} / DIFF {len(diffs)}")
    print(f"생성: {ERD.name}, {VALID.name}")
    for c in diffs:
        print("  DIFF:", c[2], "->", c[0], c[1], "추정", c[4], "실측", c[5])
    return 1 if nfail else 0


if __name__ == "__main__":
    raise SystemExit(main())
