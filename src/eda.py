# -*- coding: utf-8 -*-
"""data/converted CSV 기초 EDA. 값 수정 없이 reports/eda_report.md 생성.

통제: 어떤 값도 수정·대체·삭제하지 않으며 극단값을 오류로 확정하지 않는다.
      모든 판단은 '관측 사실'과 '확인 필요'로 분리해 근거 행 수와 함께 보고한다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent
CONVERTED = BASE / "data" / "converted"
REPORT = BASE / "reports" / "eda_report.md"
ENCODING = "utf-8-sig"
CUTOFF = "2026-07-31"  # 분석 기준일

# --- 도메인 메타 (관측단위·갱신주기) : 근거 있는 큐레이션, 편집 가능 ---
META = {
    "category_master":       ("카테고리 1건", "마스터(비정기)"),
    "product_master":        ("상품 1건", "마스터(등록 시)"),
    "sku_master":            ("SKU(옵션) 1건", "마스터(등록 시)"),
    "channel_master":        ("채널 1건", "마스터(비정기)"),
    "warehouse_master":      ("창고 1건", "마스터(비정기)"),
    "promotion":             ("프로모션 1건", "이벤트(기간별)"),
    "promotion_application": ("프로모션 적용(주문품목) 1건", "이벤트 발생 시"),
    "purchase_order":        ("발주 라인 1건", "발주 발생 시"),
    "receipt":               ("입고 라인 1건", "입고 발생 시"),
    "orders":                ("주문 1건", "연속(주문 발생)"),
    "order_item":            ("주문 품목 1건", "연속(주문 발생)"),
    "order_attribution":     ("주문 귀속 1건", "연속(주문 발생)"),
    "returns":               ("반품 1건", "반품 발생 시"),
    "inventory_snapshot":    ("스냅샷일×창고×SKU 1건", "주간(일요일)+월말 스냅샷"),
    "inventory_policy":      ("카테고리×시즌 정책 1건", "정책 승인 시"),
    "action_log":            ("액션 1건(상품 단위)", "액션 등록 시"),
    "traffic_daily":         ("일자×채널 1건", "일별"),
}

# --- 선언 PK (단일/복합) ---
PK = {
    "category_master": ["category_id"], "product_master": ["product_id"],
    "sku_master": ["sku_id"], "channel_master": ["channel_id"],
    "warehouse_master": ["warehouse_id"], "promotion": ["promotion_id"],
    "promotion_application": ["application_id"], "purchase_order": ["po_id"],
    "receipt": ["receipt_id"], "orders": ["order_id"], "order_item": ["order_item_id"],
    "order_attribution": ["attribution_id"], "returns": ["return_id"],
    "inventory_snapshot": ["snapshot_date", "warehouse_id", "sku_id"],
    "inventory_policy": ["policy_id"], "action_log": ["action_id"],
    "traffic_daily": ["date", "channel_id"],
}

# --- FK 후보 (child_table, child_col) -> (parent_table, parent_pk) ---
FK = {
    ("product_master", "category_id"): ("category_master", "category_id"),
    ("sku_master", "product_id"): ("product_master", "product_id"),
    ("promotion_application", "promotion_id"): ("promotion", "promotion_id"),
    ("promotion_application", "order_item_id"): ("order_item", "order_item_id"),
    ("purchase_order", "sku_id"): ("sku_master", "sku_id"),
    ("receipt", "po_id"): ("purchase_order", "po_id"),
    ("receipt", "sku_id"): ("sku_master", "sku_id"),
    ("receipt", "warehouse_id"): ("warehouse_master", "warehouse_id"),
    ("orders", "channel_id"): ("channel_master", "channel_id"),
    ("order_item", "order_id"): ("orders", "order_id"),
    ("order_item", "sku_id"): ("sku_master", "sku_id"),
    ("order_item", "warehouse_id"): ("warehouse_master", "warehouse_id"),
    ("order_attribution", "order_id"): ("orders", "order_id"),
    ("order_attribution", "channel_id"): ("channel_master", "channel_id"),
    ("returns", "order_item_id"): ("order_item", "order_item_id"),
    ("inventory_snapshot", "sku_id"): ("sku_master", "sku_id"),
    ("inventory_snapshot", "warehouse_id"): ("warehouse_master", "warehouse_id"),
    ("inventory_policy", "category_id"): ("category_master", "category_id"),
    ("action_log", "product_id"): ("product_master", "product_id"),
    ("action_log", "sku_id"): ("sku_master", "sku_id"),
    ("traffic_daily", "channel_id"): ("channel_master", "channel_id"),
}

# 마스터 부재로 검증 불가한 FK(구조적 한계)
NO_MASTER_FK = {
    ("product_master", "거래처_id"), ("purchase_order", "거래처_id"),
    ("orders", "customer_id"),
}

# 결측 판단 큐레이션: 근거 카운트는 실측에서 채움
NORMAL_BLANK = {
    ("order_item", "cancel_date"): "취소되지 않은 정상 건",
    ("order_item", "cancel_reason"): "취소되지 않은 정상 건",
    ("orders", "쿠폰코드"): "쿠폰 미사용 주문",
    ("purchase_order", "메모"): "메모는 선택 입력",
    ("action_log", "sku_id"): "상품 단위 액션(설계상 의도, 확정)",
    ("action_log", "completed_date"): "미완료 액션",
    ("action_log", "result_note"): "미완료·관찰 중",
    ("action_log", "decision_date"): "검토 전(미결정) 단계",
}
POSSIBLE_MISSING = {
    ("orders", "customer_id"): "비회원 주문 or 입력 누락 (마스터 없어 판별 불가)",
    ("sku_master", "보관로케이션"): "로케이션 미지정 가능",
    ("receipt", "송장번호"): "송장 누락 가능",
    ("returns", "반품사유"): "사유 미기재 가능",
    ("returns", "처리일"): "미처리(진행 중) or 누락",
    ("order_item", "주문시_상품명"): "주문 시 상품명 스냅샷 누락",
    ("inventory_snapshot", "last_count_date"): "실사일 누락",
}

IDLIKE = re.compile(r"(_id$|id$|코드|바코드|번호)")
RE_INT = re.compile(r"^-?\d+$")
RE_FLOAT = re.compile(r"^-?\d+\.\d+$")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def is_idlike(col: str) -> bool:
    return bool(IDLIKE.search(col.lower()))


def load_all() -> dict[str, pd.DataFrame]:
    dfs = {}
    for p in sorted(CONVERTED.glob("*.csv")):
        dfs[p.stem] = pd.read_csv(p, dtype=str, keep_default_na=False, encoding=ENCODING)
    return dfs


def classify(nonblank: pd.Series) -> str:
    if len(nonblank) == 0:
        return "blank"
    s = nonblank.astype(str)
    if s.str.match(RE_DATE).all():
        return "datetime" if s.str.contains(":").any() else "date"
    is_int = s.str.match(RE_INT)
    is_float = s.str.match(RE_FLOAT)
    if (is_int | is_float).all():
        if is_float.any() and is_int.any():
            return "num(int/float 혼재)"
        return "float" if is_float.any() else "int"
    return "text"


def col_stats(df: pd.DataFrame, table: str) -> list[dict]:
    out = []
    n = len(df)
    for col in df.columns:
        raw = df[col].astype(str)
        blank_mask = raw.str.strip() == ""
        nb = raw[~blank_mask]
        dtype = classify(nb)
        nmiss = int(blank_mask.sum())
        nuniq = int(nb.nunique())
        # 범주 표기 차이
        variant = ""
        if dtype == "text" and nuniq <= 40:
            stripped = nb.str.strip()
            lowered = stripped.str.lower()
            sp = nb.nunique() - stripped.nunique()
            ca = stripped.nunique() - lowered.nunique()
            flags = []
            if sp > 0:
                flags.append(f"공백변형 {sp}")
            if ca > 0:
                flags.append(f"대소문자변형 {ca}")
            variant = ", ".join(flags)
        # 수량·금액 분포 (ID 제외 수치형)
        qinfo = {}
        if dtype in ("int", "float", "num(int/float 혼재)") and not is_idlike(col):
            v = pd.to_numeric(nb, errors="coerce").dropna()
            if len(v):
                qinfo = {
                    "min": v.min(), "q25": v.quantile(.25), "med": v.median(),
                    "q75": v.quantile(.75), "max": v.max(), "mean": round(v.mean(), 1),
                    "neg": int((v < 0).sum()), "zero": int((v == 0).sum()),
                }
        out.append({
            "table": table, "col": col, "dtype": dtype,
            "miss": nmiss, "miss_pct": round(100 * nmiss / n, 1) if n else 0,
            "nuniq": nuniq, "variant": variant, "q": qinfo,
        })
    return out


def date_cols(colstats: list[dict]) -> list[str]:
    return [c["col"] for c in colstats if c["dtype"] in ("date", "datetime")]


def main() -> int:
    dfs = load_all()
    L = []  # markdown lines
    add = L.append

    add("# EDA 리포트 (data/converted)")
    add("")
    add(f"- 대상: `data/converted/*.csv` {len(dfs)}개 · 분석 기준일 **{CUTOFF}**")
    add("- **통제**: 값 수정·대체·삭제 없음. 극단값을 오류로 확정하지 않음. "
        "판단은 관측 사실과 확인 필요로 분리(근거 행수 표시).")
    add("- 로딩: 전 컬럼 문자열(`dtype=str`)로 읽어 ID·바코드 보존, 빈 문자열=결측으로 집계.")
    add("")

    # 컬럼 통계 사전 계산
    all_cols = {t: col_stats(dfs[t], t) for t in dfs}

    # ---------- 1. 테이블 수준 ----------
    add("## 1. 테이블 수준 요약")
    add("")
    add("| 테이블 | 관측단위 | 행 | 열 | PK | PK중복 | 날짜범위 | 갱신주기 |")
    add("|---|---|--:|--:|---|--:|---|---|")
    for t, df in dfs.items():
        unit, cadence = META.get(t, ("-", "-"))
        pk = PK.get(t, [])
        # PK 중복
        dup = 0
        if pk and all(c in df.columns for c in pk):
            key = df[pk].apply(lambda r: "".join(r.values), axis=1)
            nb = key[~(df[pk].apply(lambda r: (r.str.strip() == "").any(), axis=1))]
            dup = int(len(nb) - nb.nunique())
        # 날짜 범위(모든 날짜 컬럼 통합)
        dcs = date_cols(all_cols[t])
        drange = "-"
        if dcs:
            mn, mx = [], []
            for dc in dcs:
                s = df[dc].astype(str).str.strip()
                s = s[s.str.match(RE_DATE)]
                if len(s):
                    mn.append(s.str[:10].min())
                    mx.append(s.str[:10].max())
            if mn:
                drange = f"{min(mn)} ~ {max(mx)}"
        add(f"| `{t}` | {unit} | {len(df):,} | {len(df.columns)} | "
            f"{'+'.join(pk)} | {dup} | {drange} | {cadence} |")
    add("")
    add("> PK중복=선언 PK 기준 중복 행 수(복합키 포함). 0이면 유일. "
        "`inventory_snapshot`·`traffic_daily`는 복합키.")
    add("")

    # ---------- 2. 열 수준 ----------
    add("## 2. 열 수준 상세")
    add("")
    for t in dfs:
        add(f"### `{t}`")
        add("")
        add("| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |")
        add("|---|---|--:|--:|---|")
        for c in all_cols[t]:
            miss = f"{c['miss']:,} / {c['miss_pct']}%"
            add(f"| {c['col']} | {c['dtype']} | {miss} | {c['nuniq']:,} | {c['variant'] or '-'} |")
        add("")

    # ---------- 3. 수량·금액 분포 ----------
    add("## 3. 수량·금액 분포 (ID 제외 수치형) · 음수/0 포함")
    add("")
    add("| 테이블.열 | min | q25 | median | q75 | max | mean | 음수 | 0값 |")
    add("|---|--:|--:|--:|--:|--:|--:|--:|--:|")
    for t in dfs:
        for c in all_cols[t]:
            q = c["q"]
            if q:
                add(f"| `{t}`.{c['col']} | {q['min']:g} | {q['q25']:g} | {q['med']:g} | "
                    f"{q['q75']:g} | {q['max']:g} | {q['mean']:g} | {q['neg']} | {q['zero']} |")
    add("")

    # ---------- 4. 참조 무결성 관측 ----------
    add("## 4. 참조 무결성 관측 (FK 후보 · 고아 키)")
    add("")
    add("| child | col | → parent | 자식 고유값 | 부모 미존재(고아) 고유수 | 고아 행수 |")
    add("|---|---|---|--:|--:|--:|")
    orphan_notes = []
    for (ct, cc), (pt, pc) in FK.items():
        if ct not in dfs or pt not in dfs or cc not in dfs[ct].columns:
            continue
        child = dfs[ct][cc].astype(str).str.strip()
        childnb = child[child != ""]
        parent = set(dfs[pt][pc].astype(str).str.strip())
        missing_mask = ~childnb.isin(parent)
        orphan_rows = int(missing_mask.sum())
        orphan_uni = int(childnb[missing_mask].nunique())
        add(f"| `{ct}` | {cc} | `{pt}`.{pc} | {childnb.nunique():,} | {orphan_uni} | {orphan_rows} |")
        if orphan_rows:
            orphan_notes.append(f"`{ct}.{cc}` → `{pt}`: 고아 {orphan_rows}행({orphan_uni}종)")
    add("")

    # 커버리지(부모 중 자식에 안 나타난 것) 주요 관측
    add("**커버리지 관측(부모 대비 자식 미등장)**:")
    def coverage(parent_t, parent_c, child_t, child_c):
        p = set(dfs[parent_t][parent_c].astype(str).str.strip())
        c = set(dfs[child_t][child_c].astype(str).str.strip()) - {""}
        return len(p - c), len(p)
    miss_items, tot_items = coverage("orders", "order_id", "order_item", "order_id")
    miss_attr, _ = coverage("orders", "order_id", "order_attribution", "order_id")
    miss_sku, tot_sku = coverage("sku_master", "sku_id", "order_item", "sku_id")
    add(f"- 품목 없는 주문: **{miss_items}건** / 전체 {tot_items:,} 주문")
    add(f"- 귀속 없는 주문: **{miss_attr}건** / 전체 {tot_items:,} 주문")
    add(f"- 판매 이력 없는 SKU: **{miss_sku}건** / 전체 {tot_sku} SKU")
    add("")

    # ---------- 5. 판단 분리 ----------
    add("## 5. 판단 분리 (근거 행수 포함)")
    add("")
    miss_lookup = {(c["table"], c["col"]): c["miss"] for t in dfs for c in all_cols[t]}

    add("### (A) 정상 공란 — 업무상 비어 있는 것이 정상")
    add("")
    add("| 위치 | 결측행수 | 근거 |")
    add("|---|--:|---|")
    for (t, col), why in NORMAL_BLANK.items():
        add(f"| `{t}.{col}` | {miss_lookup.get((t,col),0):,} | {why} |")
    add("")

    add("### (B) 입력 누락 가능성 — 정상/누락 판별 불가, 확인 권장")
    add("")
    add("| 위치 | 결측행수 | 성격 |")
    add("|---|--:|---|")
    for (t, col), why in POSSIBLE_MISSING.items():
        add(f"| `{t}.{col}` | {miss_lookup.get((t,col),0):,} | {why} |")
    add("")

    add("### (C) 구조적 분석 한계 — 데이터 구성상 분석이 제한됨")
    add("")
    nv = dfs["product_master"]["거래처_id"].nunique()
    ncust = dfs["orders"]["customer_id"].astype(str).str.strip().replace("", pd.NA).nunique()
    add(f"- **거래처 마스터 없음**: `거래처_id` {nv}종 참조하나 vendor_master 부재 → 거래처명·조건 분석 불가.")
    add(f"- **고객 마스터 없음**: `customer_id` {ncust:,}종이나 customer_master 부재 → 고객 속성·재구매 정밀 분석 제한.")
    add("- **귀속 모델 단일**: `order_attribution`이 last_touch 위주 → 멀티터치 기여 재해석 불가.")
    add(f"- **창고 2개·프로모션 {len(dfs['promotion'])}건·액션 {len(dfs['action_log'])}건**: 소표본 → 세분 비교의 통계적 신뢰 낮음.")
    add("- **재고 스냅샷 주간+월말**: 일 단위 재고 변동·정확한 일별 WOS 재현 제한.")
    add("- **`action_log`는 상품(product_id) 단위로 통일(확정)**: sku_id를 적용범위로 쓰지 않음 → SKU 단위 액션 분석은 범위 밖.")
    add("")

    add("### (D) 확인 필요 — 관측된 이상 신호(오류로 미확정)")
    add("")
    # 기준일 이후
    post = 0
    for t, col in [("order_item", "cancel_date"), ("returns", "처리일")]:
        s = dfs[t][col].astype(str).str.strip()
        s = s[s.str.match(RE_DATE)]
        post += int((s.str[:10] > CUTOFF).sum())
    # 귀속 가중치 합 != 1
    at = dfs["order_attribution"].copy()
    at["w"] = pd.to_numeric(at["attribution_weight"], errors="coerce")
    wsum = at.groupby("order_id")["w"].sum()
    bad_w = int((wsum.sub(1).abs() > 1e-9).sum())
    # 음수 수치 스캔
    neg_cols = [(c["table"], c["col"], c["q"]["neg"]) for t in dfs for c in all_cols[t]
                if c["q"] and c["q"]["neg"] > 0]
    add(f"- **기준일 이후 이벤트 {post}건**: `cancel_date`·`처리일`이 {CUTOFF} 초과 → 확정 규칙상 '미발생' 처리 대상(재확인).")
    add(f"- **품목 없는 주문 {miss_items}건 / 귀속 없는 주문 {miss_attr}건 / 미판매 SKU {miss_sku}건**: 매출·귀속 집계 시 취급 확인.")
    add(f"- **귀속 가중치 합 != 1 주문 {bad_w}건**: README상 합=1이어야 함 → 대사 필요.")
    if neg_cols:
        add(f"- **음수 값 관측**: " + "; ".join(f"`{t}.{c}` {n}건" for t, c, n in neg_cols) + " → 취소·환불 등 정상 부호인지 확인.")
    else:
        add("- **음수 값**: ID 제외 수치형에서 관측되지 않음.")
    if orphan_notes:
        add("- **FK 고아 키**: " + "; ".join(orphan_notes) + ".")
    else:
        add("- **FK 고아 키**: 검증 대상 FK에서 고아 키 없음.")
    add("")

    add("## 6. 통제 준수")
    add("- 읽기 전용 EDA. 값 수정·대체·삭제·극단값 오류확정 없음.")
    add("- 산출물은 본 리포트와 `src/eda.py`뿐이며, 재실행 시 동일 결과로 갱신된다.")
    add("")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(L), encoding=ENCODING)
    print(f"EDA 리포트 생성: {REPORT}")
    print(f"품목없는주문={miss_items} 귀속없는주문={miss_attr} 미판매SKU={miss_sku} "
          f"기준일이후={post} 가중치합!=1 주문={bad_w} 음수컬럼={len(neg_cols)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
