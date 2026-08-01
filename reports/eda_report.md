# EDA 리포트 (data/converted)

- 대상: `data/converted/*.csv` 17개 · 분석 기준일 **2026-07-31**
- **통제**: 값 수정·대체·삭제 없음. 극단값을 오류로 확정하지 않음. 판단은 관측 사실과 확인 필요로 분리(근거 행수 표시).
- 로딩: 전 컬럼 문자열(`dtype=str`)로 읽어 ID·바코드 보존, 빈 문자열=결측으로 집계.

## 1. 테이블 수준 요약

| 테이블 | 관측단위 | 행 | 열 | PK | PK중복 | 날짜범위 | 갱신주기 |
|---|---|--:|--:|---|--:|---|---|
| `action_log` | 액션 1건(상품 단위) | 32 | 13 | action_id | 0 | 2026-04-13 ~ 2026-07-10 | 액션 등록 시 |
| `category_master` | 카테고리 1건 | 19 | 6 | category_id | 0 | - | 마스터(비정기) |
| `channel_master` | 채널 1건 | 5 | 6 | channel_id | 0 | - | 마스터(비정기) |
| `inventory_policy` | 카테고리×시즌 정책 1건 | 19 | 11 | policy_id | 0 | 2026-02-01 ~ 2026-08-31 | 정책 승인 시 |
| `inventory_snapshot` | 스냅샷일×창고×SKU 1건 | 12,369 | 10 | snapshot_date+warehouse_id+sku_id | 0 | 2026-02-01 ~ 2026-07-31 | 주간(일요일)+월말 스냅샷 |
| `order_attribution` | 주문 귀속 1건 | 7,470 | 7 | attribution_id | 0 | 2026-02-01 ~ 2026-07-31 | 연속(주문 발생) |
| `order_item` | 주문 품목 1건 | 8,831 | 20 | order_item_id | 0 | 2026-02-06 ~ 2026-08-02 | 연속(주문 발생) |
| `orders` | 주문 1건 | 7,044 | 9 | order_id | 0 | 2026-02-01 ~ 2026-07-31 | 연속(주문 발생) |
| `product_master` | 상품 1건 | 58 | 14 | product_id | 0 | 2025-10-03 ~ 2026-07-31 | 마스터(등록 시) |
| `promotion` | 프로모션 1건 | 4 | 9 | promotion_id | 0 | 2026-03-06 ~ 2026-07-19 | 이벤트(기간별) |
| `promotion_application` | 프로모션 적용(주문품목) 1건 | 1,300 | 6 | application_id | 0 | 2026-03-06 ~ 2026-07-19 | 이벤트 발생 시 |
| `purchase_order` | 발주 라인 1건 | 741 | 10 | po_id | 0 | 2026-02-01 ~ 2026-06-18 | 발주 발생 시 |
| `receipt` | 입고 라인 1건 | 741 | 9 | receipt_id | 0 | 2026-03-07 ~ 2026-06-23 | 입고 발생 시 |
| `returns` | 반품 1건 | 410 | 12 | return_id | 0 | 2026-02-05 ~ 2026-08-06 | 반품 발생 시 |
| `sku_master` | SKU(옵션) 1건 | 399 | 9 | sku_id | 0 | - | 마스터(등록 시) |
| `traffic_daily` | 일자×채널 1건 | 905 | 9 | date+channel_id | 0 | 2026-02-01 ~ 2026-07-31 | 일별 |
| `warehouse_master` | 창고 1건 | 2 | 5 | warehouse_id | 0 | - | 마스터(비정기) |

> PK중복=선언 PK 기준 중복 행 수(복합키 포함). 0이면 유일. `inventory_snapshot`·`traffic_daily`는 복합키.

## 2. 열 수준 상세

### `action_log`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| action_id | text | 0 / 0.0% | 32 | - |
| product_id | text | 0 / 0.0% | 32 | - |
| sku_id | text | 21 / 65.6% | 11 | - |
| recommended_action | text | 0 / 0.0% | 6 | - |
| final_action | text | 0 / 0.0% | 6 | - |
| action_status | text | 0 / 0.0% | 6 | - |
| owner | text | 0 / 0.0% | 3 | - |
| priority | text | 0 / 0.0% | 3 | - |
| decision_date | date | 12 / 37.5% | 20 | - |
| due_date | date | 0 / 0.0% | 32 | - |
| completed_date | date | 27 / 84.4% | 5 | - |
| expected_effect | text | 0 / 0.0% | 4 | - |
| result_note | text | 28 / 87.5% | 2 | - |

### `category_master`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| category_id | text | 0 / 0.0% | 19 | - |
| 대분류 | text | 0 / 0.0% | 6 | - |
| 중분류 | text | 0 / 0.0% | 10 | - |
| 소분류 | text | 0 / 0.0% | 18 | - |
| 시즌민감도 | text | 0 / 0.0% | 3 | - |
| 사용여부 | text | 0 / 0.0% | 1 | - |

### `channel_master`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| channel_id | text | 0 / 0.0% | 5 | - |
| 채널명 | text | 0 / 0.0% | 5 | - |
| 채널유형 | text | 0 / 0.0% | 4 | - |
| 수수료율 | float | 0 / 0.0% | 5 | - |
| 정산주기_일 | int | 0 / 0.0% | 5 | - |
| 운영상태 | text | 0 / 0.0% | 1 | - |

### `inventory_policy`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| policy_id | text | 0 / 0.0% | 19 | - |
| category_id | text | 0 / 0.0% | 19 | - |
| season | text | 0 / 0.0% | 2 | - |
| lifecycle_stage | text | 0 / 0.0% | 1 | - |
| target_wos_min | int | 0 / 0.0% | 3 | - |
| target_wos_max | int | 0 / 0.0% | 3 | - |
| reorder_point_wos | int | 0 / 0.0% | 3 | - |
| clearance_point_wos | int | 0 / 0.0% | 3 | - |
| effective_from | date | 0 / 0.0% | 1 | - |
| effective_to | date | 0 / 0.0% | 1 | - |
| approved_by | text | 0 / 0.0% | 2 | - |

### `inventory_snapshot`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| snapshot_date | date | 0 / 0.0% | 31 | - |
| warehouse_id | text | 0 / 0.0% | 2 | - |
| sku_id | text | 0 / 0.0% | 399 | - |
| on_hand_qty | int | 0 / 0.0% | 101 | - |
| available_qty | int | 0 / 0.0% | 103 | - |
| reserved_qty | int | 0 / 0.0% | 3 | - |
| in_transit_qty | int | 0 / 0.0% | 1 | - |
| damaged_qty | int | 0 / 0.0% | 2 | - |
| last_count_date | date | 1 / 0.0% | 7 | - |
| inventory_value | int | 0 / 0.0% | 1,901 | - |

### `order_attribution`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| attribution_id | text | 0 / 0.0% | 7,470 | - |
| order_id | text | 0 / 0.0% | 6,905 | - |
| channel_id | text | 0 / 0.0% | 5 | - |
| attribution_model | text | 0 / 0.0% | 2 | - |
| attribution_weight | num(int/float 혼재) | 0 / 0.0% | 3 | - |
| lookback_days | int | 0 / 0.0% | 1 | - |
| attributed_at | datetime | 0 / 0.0% | 6,903 | - |

### `order_item`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| order_item_id | text | 0 / 0.0% | 8,831 | - |
| order_id | text | 0 / 0.0% | 7,041 | - |
| sku_id | text | 0 / 0.0% | 398 | - |
| 주문시_상품명 | text | 20 / 0.2% | 58 | - |
| 수량 | int | 0 / 0.0% | 2 | - |
| 정상가 | int | 0 / 0.0% | 42 | - |
| 판매단가 | int | 0 / 0.0% | 521 | - |
| 상품할인액 | int | 0 / 0.0% | 152 | - |
| 쿠폰할인액 | int | 0 / 0.0% | 55 | - |
| 배송비배부액 | int | 0 / 0.0% | 2 | - |
| 채널수수료액 | int | 0 / 0.0% | 1,086 | - |
| warehouse_id | text | 0 / 0.0% | 2 | - |
| order_item_status | text | 0 / 0.0% | 3 | - |
| canceled_qty | int | 0 / 0.0% | 3 | - |
| canceled_amount | int | 0 / 0.0% | 72 | - |
| cancel_date | date | 8,625 / 97.7% | 120 | - |
| cancel_reason | text | 8,647 / 97.9% | 5 | - |
| payment_fee_amount | int | 0 / 0.0% | 2,074 | - |
| fulfillment_cost_amount | int | 0 / 0.0% | 4 | - |
| packaging_cost_amount | int | 0 / 0.0% | 4 | - |

### `orders`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| order_id | text | 0 / 0.0% | 7,044 | - |
| 주문일시 | datetime | 0 / 0.0% | 7,042 | - |
| channel_id | text | 0 / 0.0% | 5 | - |
| customer_id | text | 1,008 / 14.3% | 3,035 | - |
| 주문상태 | text | 0 / 0.0% | 3 | - |
| 결제수단 | text | 0 / 0.0% | 4 | - |
| 쿠폰코드 | text | 6,011 / 85.3% | 3 | - |
| 배송지역 | text | 0 / 0.0% | 8 | - |
| 주문수집일시 | datetime | 0 / 0.0% | 2,479 | - |

### `product_master`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| product_id | text | 0 / 0.0% | 58 | - |
| 상품명 | text | 0 / 0.0% | 58 | - |
| 브랜드 | text | 0 / 0.0% | 10 | - |
| category_id | text | 0 / 0.0% | 19 | - |
| 출시일 | date | 0 / 0.0% | 24 | - |
| 정상가 | int | 0 / 0.0% | 42 | - |
| 기준원가 | int | 0 / 0.0% | 53 | - |
| 거래처_id | text | 0 / 0.0% | 12 | - |
| 리드타임_일 | int | 0 / 0.0% | 5 | - |
| 상품상태 | text | 0 / 0.0% | 2 | - |
| 담당MD | text | 0 / 0.0% | 3 | - |
| 시즌 | text | 0 / 0.0% | 2 | - |
| 등록일시 | datetime | 0 / 0.0% | 24 | - |
| 수정일시 | datetime | 0 / 0.0% | 1 | - |

### `promotion`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| promotion_id | text | 0 / 0.0% | 4 | - |
| 프로모션명 | text | 0 / 0.0% | 4 | - |
| 시작일 | date | 0 / 0.0% | 4 | - |
| 종료일 | date | 0 / 0.0% | 4 | - |
| 할인유형 | text | 0 / 0.0% | 1 | - |
| 할인값 | float | 0 / 0.0% | 4 | - |
| 적용채널 | text | 0 / 0.0% | 4 | - |
| 예산 | int | 0 / 0.0% | 4 | - |
| 담당자 | text | 0 / 0.0% | 2 | - |

### `promotion_application`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| application_id | text | 0 / 0.0% | 1,300 | - |
| promotion_id | text | 0 / 0.0% | 4 | - |
| order_item_id | text | 0 / 0.0% | 1,300 | - |
| discount_amount | int | 0 / 0.0% | 147 | - |
| funded_by | text | 0 / 0.0% | 2 | - |
| applied_at | datetime | 0 / 0.0% | 1,041 | - |

### `purchase_order`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| po_id | text | 0 / 0.0% | 741 | - |
| 발주일 | date | 0 / 0.0% | 91 | - |
| 거래처_id | text | 0 / 0.0% | 12 | - |
| sku_id | text | 0 / 0.0% | 388 | - |
| 발주수량 | int | 0 / 0.0% | 25 | - |
| 단위원가 | int | 0 / 0.0% | 53 | - |
| 예정입고일 | date | 0 / 0.0% | 5 | - |
| 발주상태 | text | 0 / 0.0% | 1 | - |
| 발주담당자 | text | 0 / 0.0% | 2 | - |
| 메모 | text | 715 / 96.5% | 1 | - |

### `receipt`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| receipt_id | text | 0 / 0.0% | 741 | - |
| po_id | text | 0 / 0.0% | 741 | - |
| 실입고일 | date | 0 / 0.0% | 35 | - |
| warehouse_id | text | 0 / 0.0% | 2 | - |
| sku_id | text | 0 / 0.0% | 388 | - |
| 입고수량 | int | 0 / 0.0% | 25 | - |
| 검수불량수량 | int | 0 / 0.0% | 3 | - |
| 입고담당자 | text | 0 / 0.0% | 2 | - |
| 송장번호 | text | 12 / 1.6% | 729 | - |

### `returns`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| return_id | text | 0 / 0.0% | 410 | - |
| order_item_id | text | 0 / 0.0% | 410 | - |
| 접수일 | date | 0 / 0.0% | 155 | - |
| 처리일 | date | 32 / 7.8% | 152 | - |
| 반품수량 | int | 0 / 0.0% | 1 | - |
| 반품사유 | text | 66 / 16.1% | 5 | - |
| 귀책주체 | text | 0 / 0.0% | 2 | - |
| 환불금액 | int | 0 / 0.0% | 133 | - |
| 재판매가능 | text | 0 / 0.0% | 2 | - |
| 처리상태 | text | 0 / 0.0% | 2 | - |
| return_shipping_cost | int | 0 / 0.0% | 2 | - |
| return_handling_cost | int | 0 / 0.0% | 296 | - |

### `sku_master`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| sku_id | text | 0 / 0.0% | 399 | - |
| product_id | text | 0 / 0.0% | 58 | - |
| 색상 | text | 0 / 0.0% | 10 | - |
| 사이즈 | text | 0 / 0.0% | 10 | - |
| 바코드 | int | 0 / 0.0% | 399 | - |
| 옵션상태 | text | 0 / 0.0% | 1 | - |
| 최소진열재고 | int | 0 / 0.0% | 3 | - |
| 안전재고 | int | 0 / 0.0% | 5 | - |
| 보관로케이션 | text | 1 / 0.3% | 190 | - |

### `traffic_daily`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| date | date | 0 / 0.0% | 181 | - |
| channel_id | text | 0 / 0.0% | 5 | - |
| sessions | int | 0 / 0.0% | 799 | - |
| product_views | int | 0 / 0.0% | 851 | - |
| add_to_cart | int | 0 / 0.0% | 302 | - |
| checkout_start | int | 0 / 0.0% | 167 | - |
| attributed_order_credit | num(int/float 혼재) | 0 / 0.0% | 164 | - |
| ad_spend | int | 0 / 0.0% | 723 | - |
| new_customers | int | 0 / 0.0% | 39 | - |

### `warehouse_master`

| 열 | 자료형 | 결측(n / %) | 고유수 | 범주 표기차이 |
|---|---|--:|--:|---|
| warehouse_id | text | 0 / 0.0% | 2 | - |
| 창고명 | text | 0 / 0.0% | 2 | - |
| 유형 | text | 0 / 0.0% | 2 | - |
| 지역 | text | 0 / 0.0% | 2 | - |
| 운영상태 | text | 0 / 0.0% | 1 | - |

## 3. 수량·금액 분포 (ID 제외 수치형) · 음수/0 포함

| 테이블.열 | min | q25 | median | q75 | max | mean | 음수 | 0값 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| `channel_master`.수수료율 | 0.025 | 0.029 | 0.058 | 0.105 | 0.16 | 0.1 | 0 | 0 |
| `channel_master`.정산주기_일 | 2 | 7 | 10 | 15 | 30 | 12.8 | 0 | 0 |
| `inventory_policy`.target_wos_min | 14 | 14 | 16 | 18 | 18 | 16.2 | 0 | 0 |
| `inventory_policy`.target_wos_max | 32 | 32 | 38 | 42 | 42 | 37.7 | 0 | 0 |
| `inventory_policy`.reorder_point_wos | 8 | 8 | 10 | 12 | 12 | 10.2 | 0 | 0 |
| `inventory_policy`.clearance_point_wos | 44 | 44 | 50 | 56 | 56 | 50.6 | 0 | 0 |
| `inventory_snapshot`.on_hand_qty | 0 | 12 | 22 | 36 | 104 | 25.5 | 0 | 621 |
| `inventory_snapshot`.available_qty | 0 | 12 | 21 | 35 | 104 | 25.2 | 0 | 669 |
| `inventory_snapshot`.reserved_qty | 0 | 0 | 0 | 0 | 2 | 0.3 | 0 | 9621 |
| `inventory_snapshot`.in_transit_qty | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 12369 |
| `inventory_snapshot`.damaged_qty | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 12270 |
| `inventory_snapshot`.inventory_value | 0 | 285000 | 533400 | 969000 | 3.5409e+06 | 696805 | 0 | 621 |
| `order_attribution`.attribution_weight | 0.3 | 1 | 1 | 1 | 1 | 0.9 | 0 | 0 |
| `order_attribution`.lookback_days | 7 | 7 | 7 | 7 | 7 | 7 | 0 | 0 |
| `order_item`.수량 | 1 | 1 | 1 | 1 | 2 | 1 | 0 | 0 |
| `order_item`.정상가 | 15000 | 50000 | 61000 | 78000 | 90000 | 60501.1 | 0 | 0 |
| `order_item`.판매단가 | 12800 | 47300 | 60000 | 77000 | 90000 | 59161.1 | 0 | 0 |
| `order_item`.상품할인액 | 0 | 0 | 0 | 0 | 26600 | 1388.8 | 0 | 6638 |
| `order_item`.쿠폰할인액 | 0 | 0 | 0 | 0 | 8800 | 563.5 | 0 | 7203 |
| `order_item`.배송비배부액 | 0 | 0 | 0 | 3000 | 3000 | 779.6 | 0 | 6536 |
| `order_item`.채널수수료액 | 353 | 1666.5 | 2407 | 4741.5 | 28160 | 3640.5 | 0 | 0 |
| `order_item`.canceled_qty | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 8625 |
| `order_item`.canceled_amount | 0 | 0 | 0 | 0 | 172000 | 1438.6 | 0 | 8625 |
| `order_item`.payment_fee_amount | 0 | 1044.5 | 1402 | 1806 | 4482 | 1415.8 | 0 | 205 |
| `order_item`.fulfillment_cost_amount | 0 | 2200 | 2200 | 2200 | 2550 | 2033.1 | 0 | 205 |
| `order_item`.packaging_cost_amount | 0 | 450 | 450 | 450 | 550 | 418.8 | 0 | 205 |
| `product_master`.정상가 | 15000 | 31500 | 50000 | 63750 | 90000 | 49913.8 | 0 | 0 |
| `product_master`.기준원가 | 7300 | 14575 | 22000 | 29275 | 41500 | 22527.6 | 0 | 0 |
| `product_master`.리드타임_일 | 18 | 25 | 32 | 39 | 46 | 31.6 | 0 | 0 |
| `promotion`.할인값 | 0.1 | 0.115 | 0.135 | 0.1575 | 0.18 | 0.1 | 0 | 0 |
| `promotion`.예산 | 7e+06 | 8.5e+06 | 1e+07 | 1.275e+07 | 1.8e+07 | 1.125e+07 | 0 | 0 |
| `promotion_application`.discount_amount | 1200 | 4900 | 6900 | 9025 | 26600 | 7243.8 | 0 | 0 |
| `purchase_order`.발주수량 | 8 | 14 | 20 | 26 | 32 | 20 | 0 | 0 |
| `purchase_order`.단위원가 | 7300 | 22300 | 27300 | 34600 | 41500 | 27306.3 | 0 | 0 |
| `receipt`.입고수량 | 8 | 14 | 20 | 26 | 32 | 20 | 0 | 0 |
| `receipt`.검수불량수량 | 0 | 0 | 0 | 0 | 2 | 0.1 | 0 | 711 |
| `returns`.반품수량 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 0 |
| `returns`.환불금액 | 14200 | 50000 | 62000 | 77000 | 90000 | 61578.3 | 0 | 0 |
| `returns`.return_shipping_cost | 0 | 0 | 0 | 3000 | 3000 | 1119.5 | 0 | 257 |
| `returns`.return_handling_cost | 0 | 1309.5 | 1492.5 | 1705 | 1899 | 1420.5 | 0 | 32 |
| `sku_master`.최소진열재고 | 2 | 2 | 3 | 4 | 4 | 3 | 0 | 0 |
| `sku_master`.안전재고 | 5 | 6 | 7 | 8 | 9 | 7 | 0 | 0 |
| `traffic_daily`.sessions | 446 | 945 | 1664 | 2660 | 5359 | 1953.9 | 0 | 0 |
| `traffic_daily`.product_views | 1265 | 2870 | 5033 | 8084 | 17339 | 5854.9 | 0 | 0 |
| `traffic_daily`.add_to_cart | 33 | 73 | 129 | 206 | 467 | 151.3 | 0 | 0 |
| `traffic_daily`.checkout_start | 13 | 32 | 55 | 91 | 197 | 66.3 | 0 | 0 |
| `traffic_daily`.attributed_order_credit | 0 | 3 | 5.7 | 10.7 | 28.9 | 7.6 | 0 | 16 |
| `traffic_daily`.ad_spend | 0 | 89089 | 162059 | 263557 | 620390 | 179682 | 0 | 181 |
| `traffic_daily`.new_customers | 2 | 6 | 10 | 16 | 42 | 11.7 | 0 | 0 |

## 4. 참조 무결성 관측 (FK 후보 · 고아 키)

| child | col | → parent | 자식 고유값 | 부모 미존재(고아) 고유수 | 고아 행수 |
|---|---|---|--:|--:|--:|
| `product_master` | category_id | `category_master`.category_id | 19 | 0 | 0 |
| `sku_master` | product_id | `product_master`.product_id | 58 | 0 | 0 |
| `promotion_application` | promotion_id | `promotion`.promotion_id | 4 | 0 | 0 |
| `promotion_application` | order_item_id | `order_item`.order_item_id | 1,300 | 0 | 0 |
| `purchase_order` | sku_id | `sku_master`.sku_id | 388 | 0 | 0 |
| `receipt` | po_id | `purchase_order`.po_id | 741 | 0 | 0 |
| `receipt` | sku_id | `sku_master`.sku_id | 388 | 0 | 0 |
| `receipt` | warehouse_id | `warehouse_master`.warehouse_id | 2 | 0 | 0 |
| `orders` | channel_id | `channel_master`.channel_id | 5 | 0 | 0 |
| `order_item` | order_id | `orders`.order_id | 7,041 | 0 | 0 |
| `order_item` | sku_id | `sku_master`.sku_id | 398 | 0 | 0 |
| `order_item` | warehouse_id | `warehouse_master`.warehouse_id | 2 | 0 | 0 |
| `order_attribution` | order_id | `orders`.order_id | 6,905 | 0 | 0 |
| `order_attribution` | channel_id | `channel_master`.channel_id | 5 | 0 | 0 |
| `returns` | order_item_id | `order_item`.order_item_id | 410 | 0 | 0 |
| `inventory_snapshot` | sku_id | `sku_master`.sku_id | 399 | 0 | 0 |
| `inventory_snapshot` | warehouse_id | `warehouse_master`.warehouse_id | 2 | 0 | 0 |
| `inventory_policy` | category_id | `category_master`.category_id | 19 | 0 | 0 |
| `action_log` | product_id | `product_master`.product_id | 32 | 0 | 0 |
| `action_log` | sku_id | `sku_master`.sku_id | 11 | 0 | 0 |
| `traffic_daily` | channel_id | `channel_master`.channel_id | 5 | 0 | 0 |

**커버리지 관측(부모 대비 자식 미등장)**:
- 품목 없는 주문: **3건** / 전체 7,044 주문
- 귀속 없는 주문: **139건** / 전체 7,044 주문
- 판매 이력 없는 SKU: **1건** / 전체 399 SKU

## 5. 판단 분리 (근거 행수 포함)

### (A) 정상 공란 — 업무상 비어 있는 것이 정상

| 위치 | 결측행수 | 근거 |
|---|--:|---|
| `order_item.cancel_date` | 8,625 | 취소되지 않은 정상 건 |
| `order_item.cancel_reason` | 8,647 | 취소되지 않은 정상 건 |
| `orders.쿠폰코드` | 6,011 | 쿠폰 미사용 주문 |
| `purchase_order.메모` | 715 | 메모는 선택 입력 |
| `action_log.sku_id` | 21 | 상품 단위 액션(설계상 의도, 확정) |
| `action_log.completed_date` | 27 | 미완료 액션 |
| `action_log.result_note` | 28 | 미완료·관찰 중 |
| `action_log.decision_date` | 12 | 검토 전(미결정) 단계 |

### (B) 입력 누락 가능성 — 정상/누락 판별 불가, 확인 권장

| 위치 | 결측행수 | 성격 |
|---|--:|---|
| `orders.customer_id` | 1,008 | 비회원 주문 or 입력 누락 (마스터 없어 판별 불가) |
| `sku_master.보관로케이션` | 1 | 로케이션 미지정 가능 |
| `receipt.송장번호` | 12 | 송장 누락 가능 |
| `returns.반품사유` | 66 | 사유 미기재 가능 |
| `returns.처리일` | 32 | 미처리(진행 중) or 누락 |
| `order_item.주문시_상품명` | 20 | 주문 시 상품명 스냅샷 누락 |
| `inventory_snapshot.last_count_date` | 1 | 실사일 누락 |

### (C) 구조적 분석 한계 — 데이터 구성상 분석이 제한됨

- **거래처 마스터 없음**: `거래처_id` 12종 참조하나 vendor_master 부재 → 거래처명·조건 분석 불가.
- **고객 마스터 없음**: `customer_id` 3,035종이나 customer_master 부재 → 고객 속성·재구매 정밀 분석 제한.
- **귀속 모델 단일**: `order_attribution`이 last_touch 위주 → 멀티터치 기여 재해석 불가.
- **창고 2개·프로모션 4건·액션 32건**: 소표본 → 세분 비교의 통계적 신뢰 낮음.
- **재고 스냅샷 주간+월말**: 일 단위 재고 변동·정확한 일별 WOS 재현 제한.
- **`action_log`는 상품(product_id) 단위로 통일(확정)**: sku_id를 적용범위로 쓰지 않음 → SKU 단위 액션 분석은 범위 밖.

### (D) 확인 필요 — 관측된 이상 신호(오류로 미확정)

- **기준일 이후 이벤트 9건**: `cancel_date`·`처리일`이 2026-07-31 초과 → 확정 규칙상 '미발생' 처리 대상(재확인).
- **품목 없는 주문 3건 / 귀속 없는 주문 139건 / 미판매 SKU 1건**: 매출·귀속 집계 시 취급 확인.
- **귀속 가중치 합 != 1 주문 0건**: README상 합=1이어야 함 → 대사 필요.
- **음수 값**: ID 제외 수치형에서 관측되지 않음.
- **FK 고아 키**: 검증 대상 FK에서 고아 키 없음.

## 6. 통제 준수
- 읽기 전용 EDA. 값 수정·대체·삭제·극단값 오류확정 없음.
- 산출물은 본 리포트와 `src/eda.py`뿐이며, 재실행 시 동일 결과로 갱신된다.
