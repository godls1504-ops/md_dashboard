# 논리 ERD 및 관계 검증 (승인 테이블 전용)

- 대상: 승인 테이블 13개(필수 8 + 보조 4). 근거 [table_selection.md](table_selection.md)
- **통제**: 관계를 열 이름만으로 확정하지 않고 `data/converted` 실측으로 검증. **N:M(fact×fact SKU 교차) 조인은 미실행(승인 대기).**
- 상세 검증표: [relationship_validation.csv](relationship_validation.csv) (72행)

## 1. ERD (Mermaid) — 검증된 카디널리티

```mermaid
erDiagram
  CATEGORY_MASTER ||--o{ PRODUCT_MASTER : classifies
  PRODUCT_MASTER  ||--o{ SKU_MASTER : variant_of
  SKU_MASTER      ||--o{ ORDER_ITEM : sold_as
  ORDERS          ||--o{ ORDER_ITEM : contains
  CHANNEL_MASTER  ||--o{ ORDERS : sells_via
  WAREHOUSE_MASTER||--o{ ORDER_ITEM : shipped_from
  ORDER_ITEM      ||--o| RETURNS : returned
  SKU_MASTER      ||--o{ INVENTORY_SNAPSHOT : stocked_as
  WAREHOUSE_MASTER||--o{ INVENTORY_SNAPSHOT : stored_in
  CATEGORY_MASTER ||--|| INVENTORY_POLICY : governed_by
  SKU_MASTER      ||--o{ PURCHASE_ORDER : ordered_as
  PURCHASE_ORDER  ||--|| RECEIPT : received_as
  SKU_MASTER      ||--o{ RECEIPT : received_sku
  WAREHOUSE_MASTER||--o{ RECEIPT : received_at
  PRODUCT_MASTER  ||--o| ACTION_LOG : has_action
  ORImg[" "]
```
> 기호: `||--o{` 1:N(0..N), `||--o|` 1:0..1, `||--||` 1:1. 위 카디널리티는 아래 검증 결과 기준.

## 2. 테이블별 관측단위·키

| 테이블 | 관측단위 | PK | FK |
|---|---|---|---|
| `order_item` | 주문×SKU 1줄 | order_item_id | order_id→orders, sku_id→sku_master, warehouse_id→warehouse_master |
| `orders` | 주문 1건 | order_id | channel_id→channel_master |
| `returns` | 반품 1건 | return_id | order_item_id→order_item |
| `sku_master` | SKU 1개 | sku_id | product_id→product_master |
| `product_master` | 상품 1개 | product_id | category_id→category_master |
| `category_master` | 카테고리 1개 | category_id | - |
| `inventory_snapshot` | 시점×창고×SKU | snapshot_date+warehouse_id+sku_id | sku_id→sku_master, warehouse_id→warehouse_master |
| `inventory_policy` | 카테고리 정책 | policy_id | category_id→category_master |
| `channel_master` | 채널 1개 | channel_id | - |
| `purchase_order` | 발주 1건 | po_id | sku_id→sku_master |
| `receipt` | 입고 1건 | receipt_id | po_id→purchase_order, sku_id→sku_master, warehouse_id→warehouse_master |
| `action_log` | 액션 1건(상품 단위) | action_id | product_id→product_master |
| `warehouse_master` | 창고 1개 | warehouse_id | - |

## 3. 관계 추정 vs 실제 검증

| 관계(부모→자식) | 추정 | 검증 | 고아행 | 부모당 최대자식 | 차이 |
|---|---|---|--:|--:|---|
| `orders` → `order_item`.order_id | 1:N | 1:N | 0 | 3 | 일치 |
| `sku_master` → `order_item`.sku_id | 1:N | 1:N | 0 | 50 | 일치 |
| `warehouse_master` → `order_item`.warehouse_id | 1:N | 1:N | 0 | 8002 | 일치 |
| `channel_master` → `orders`.channel_id | 1:N | 1:N | 0 | 3009 | 일치 |
| `order_item` → `returns`.order_item_id | 1:1 | 1:1 | 0 | 1 | 일치 |
| `product_master` → `sku_master`.product_id | 1:N | 1:N | 0 | 12 | 일치 |
| `category_master` → `product_master`.category_id | 1:N | 1:N | 0 | 4 | 일치 |
| `sku_master` → `inventory_snapshot`.sku_id | 1:N | 1:N | 0 | 31 | 일치 |
| `warehouse_master` → `inventory_snapshot`.warehouse_id | 1:N | 1:N | 0 | 11129 | 일치 |
| `category_master` → `inventory_policy`.category_id | 1:N | 1:1 | 0 | 1 | **DIFF** |
| `sku_master` → `purchase_order`.sku_id | 1:N | 1:N | 0 | 3 | 일치 |
| `purchase_order` → `receipt`.po_id | 1:1 | 1:1 | 0 | 1 | 일치 |
| `sku_master` → `receipt`.sku_id | 1:N | 1:N | 0 | 3 | 일치 |
| `warehouse_master` → `receipt`.warehouse_id | 1:N | 1:N | 0 | 634 | 일치 |
| `product_master` → `action_log`.product_id | 1:N | 1:1 | 0 | 1 | **DIFF** |

### 추정과 다른 관계 (주의)

- **`category_master` → `inventory_policy`.category_id**: 추정 1:N → 실측 **1:1** (부모당 최대 자식 1). 정책은 논리상 카테고리×시즌(1:N)이나 현재 데이터는 카테고리당 1건 → `season`까지 함께 조인해야 안전.
- **`product_master` → `action_log`.product_id**: 추정 1:N → 실측 **1:1** (부모당 최대 자식 1). 상품당 액션이 논리상 여러 건 가능하나 현재 32건이 상품별 1건 → 향후 누적 시 1:N 대비.

## 4. 단계별 조인 검증 (안전 조인만; 행수·합계 보존)

| 단계 | 기대 | 실측 | 결과 |
|---|---|---|---|
| order_item (판매 팩트 base) | 행=8831 | 행=8831 | PASS |
| +orders (order_id) | 행=8831, 합보존 | 행=8831, 합동일 | PASS |
| +sku_master (sku_id) | 행=8831, 합보존 | 행=8831, 합동일 | PASS |
| +product_master (product_id) | 행=8831, 합보존 | 행=8831, 합동일 | PASS |
| +category_master (category_id) | 행=8831, 합보존 | 행=8831, 합동일 | PASS |
| +returns (order_item_id, 1:1) | 행=8831, 합보존 | 행=8831, 합동일 | PASS |
| inventory_snapshot (재고 팩트 base) | 행=12369 | 행=12369 | PASS |
| +sku_master (sku_id) | 행=12369, 합보존 | 행=12369, 합동일 | PASS |
| +product_master (product_id) | 행=12369, 합보존 | 행=12369, 합동일 | PASS |
| +category_master (category_id) | 행=12369, 합보존 | 행=12369, 합동일 | PASS |
| +inventory_policy (category_id, 검증 1:1) | 행=12369, 합보존 | 행=12369, 합동일 | PASS |
| purchase_order (공급 base) | 행=741 | 행=741 | PASS |
| +receipt (po_id, 1:1) | 행=741, 합보존 | 행=741, 합동일 | PASS |

> 판매 팩트(order_item 기준)와 재고 팩트(inventory_snapshot 기준)는 각각 차원 테이블을 N:1/1:1로만 붙여 **행수·핵심 합계가 보존**되어야 정상.

## 5. N:M 주의 (미실행)

- **`order_item` × `inventory_snapshot`**: 둘 다 `sku_id`를 가지지만 각각 팩트라, 직접 조인하면 (SKU당 판매 다수)×(SKU당 스냅샷 다수)로 **N:M fan-out**이 발생한다. → 승인 전까지 실행하지 않으며, 필요 시 SKU 단위로 **각각 집계한 뒤** 결합한다.
- `inventory_policy`는 실측 1:1이나 논리상 카테고리×`season`이므로, 시즌별 정책이 추가되면 `category_id` 단독 조인은 금지(‌`+season`).

## 6. 통제 준수
- 관계는 실측 검증(고아·카디널리티·복합키·조인 전후 행수/합계)으로 확정.
- 다대다 조인 및 fact×fact SKU 교차는 실행하지 않음(승인 대기).