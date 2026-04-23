# Implementation Plan: Route-Based Inventory Check

## Overview

Implement the geospatially-aware inventory checking pipeline: database migrations, backend service layer, Celery task, API endpoints, and frontend components. Tasks are ordered so each step builds on the previous, with property-based tests placed close to the code they validate.

## Tasks

- [x] 1. Database migrations and data models
  - [x] 1.1 Create `stores` table migration with PostGIS GIST index
    - Add `id`, `name`, `address`, `location GEOMETRY(Point, 4326)`, `api_adapter`, `api_config JSONB`, `created_at`
    - Add `CREATE INDEX idx_stores_location ON stores USING GIST(location)`
    - _Requirements: 1.2, 5.1_
  - [x] 1.2 Alter `bom_items` table migration
    - Add `client_supplied BOOLEAN NOT NULL DEFAULT FALSE` and `client_supplied_at TIMESTAMPTZ`
    - _Requirements: 3.2, 3.5_
  - [x] 1.3 Create `inventory_check_runs` table migration
    - Add `id`, `job_id`, `route_polyline JSONB`, `corridor_meters INT`, `status`, `started_at`, `completed_at`, `result_summary JSONB`
    - _Requirements: 5.3_
  - [x] 1.4 Create `inventory_notifications` table migration
    - Add `id`, `job_id`, `artisan_id`, `bom_item_id`, `store_id`, `sent_at`, `delivery_status`, `pre_pay_url`
    - Add `UNIQUE (job_id, bom_item_id)` constraint to enforce one notification per item per job
    - _Requirements: 4.4_
  - [x] 1.5 Create SQLAlchemy ORM models for `Store`, `InventoryCheckRun`, and `InventoryNotification`
    - Use GeoAlchemy2 `Geometry('POINT', srid=4326)` for `Store.location`
    - _Requirements: 1.2, 4.4, 5.1_

- [x] 2. RoutingService
  - [x] 2.1 Implement `RoutingService` in `app/services/routing_service.py`
    - Define `Coordinate` and `RouteResult` dataclasses
    - Implement `compute_route(origin, destination) -> RouteResult` wrapping an external routing provider (Google Maps or OpenRouteService)
    - Raise `RoutingError` when origin is unavailable or the external call fails
    - _Requirements: 1.1, 1.4_
  - [ ]* 2.2 Write unit tests for `RoutingService`
    - Mock external routing API; assert correct `RouteResult` GeoJSON LineString output
    - Assert `RoutingError` raised when GPS is missing or routing fails
    - _Requirements: 1.1, 1.4_

- [ ] 3. StoreAPIAdapter
  - [x] 3.1 Implement abstract `StoreAPIAdapter` base class and `StockResult` dataclass in `app/adapters/store_api_adapter.py`
    - Define `check_stock(store_id, bom_items) -> list[StockResult]` abstract method
    - Include `data_timestamp` field on `StockResult` for staleness checks
    - _Requirements: 2.2, 2.3, 5.4_
  - [x] 3.2 Implement at least one concrete adapter (e.g., `HomeDepotAdapter`)
    - Normalize external HTTP response into `StockResult` objects
    - Enforce 5-second timeout on HTTP calls
    - _Requirements: 2.2, 2.4_
  - [ ]* 3.3 Write unit tests for `StoreAPIAdapter` implementations
    - Mock HTTP responses for success, timeout, and HTTP error cases
    - Assert correct normalization to `StockResult`
    - Assert timeout raises/returns appropriately within 5 seconds
    - _Requirements: 2.3, 2.4_

- [ ] 4. InventoryService
  - [x] 4.1 Implement `InventoryService` in `app/services/inventory_service.py`
    - Implement PostGIS corridor query using `ST_Buffer` + `ST_Intersects` via SQLAlchemy + GeoAlchemy2
    - Fetch BOM for job, filtering out `client_supplied=True` items before any adapter call
    - Fan out async `check_stock` calls with `asyncio.gather` and per-adapter 5-second timeout
    - Mark timed-out or errored stores as `unavailable`; continue processing remaining stores
    - Aggregate in-stock results into `InventoryCheckResult`
    - _Requirements: 1.2, 1.3, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 5.3_
  - [ ]* 4.2 Write property test: corridor containment (Property 1)
    - **Property 1: Corridor containment**
    - Generate random route polylines and store point sets; assert every returned store's location intersects the buffered polyline
    - Tag: `Feature: route-based-inventory-check, Property 1: corridor containment`
    - **Validates: Requirements 1.2, 5.1**
  - [ ]* 4.3 Write property test: client-supplied exclusion (Property 2)
    - **Property 2: Client-supplied items are excluded from queries**
    - Generate random BOM lists with random `client_supplied` flags; assert no client-supplied item appears in any adapter call
    - Tag: `Feature: route-based-inventory-check, Property 2: client-supplied items excluded`
    - **Validates: Requirements 2.5, 3.4**
  - [ ]* 4.4 Write property test: timeout isolation (Property 5)
    - **Property 5: Store query fan-out timeout isolation**
    - Generate adapter sets with random timeout patterns; assert non-timing-out adapters always contribute results regardless of which adapters fail
    - Tag: `Feature: route-based-inventory-check, Property 5: store query fan-out timeout isolation`
    - **Validates: Requirements 2.4**
  - [ ]* 4.5 Write unit tests for `InventoryService`
    - Mock PostGIS query and Store_API adapters
    - Test edge cases: empty BOM, all items client-supplied, zero stores in corridor, all stores time out
    - _Requirements: 1.5, 2.1–2.5_

- [ ] 5. NotificationService
  - [x] 5.1 Implement `NotificationService` in `app/services/notification_service.py`
    - Group `StoreMatch` results by store before sending
    - Send one push notification per store via FCM or Web Push
    - Build `Pre_Pay_Link` per item using `StockResult.item_url`
    - Include staleness warning in payload when `StockResult.data_timestamp` is older than 1 hour
    - Schedule single retry via Celery `countdown=60` on delivery failure
    - Log invalid device tokens and skip retry
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.4_
  - [ ]* 5.2 Write property test: one notification per BOM item per job (Property 3)
    - **Property 3: One notification per BOM item per job**
    - Generate random multi-store match sets; assert deduplication produces at most one `inventory_notifications` row per `(job_id, bom_item_id)` pair
    - Tag: `Feature: route-based-inventory-check, Property 3: one notification per BOM item per job`
    - **Validates: Requirements 4.4**
  - [ ]* 5.3 Write property test: stale data flagging (Property 4)
    - **Property 4: Stale data flagging**
    - Generate `StockResult` objects with random `data_timestamp` values; assert staleness warning is present in the notification payload if and only if the timestamp is more than 1 hour before `started_at`
    - Tag: `Feature: route-based-inventory-check, Property 4: stale data flagging`
    - **Validates: Requirements 5.4**
  - [ ]* 5.4 Write property test: notification grouping by store (Property 6)
    - **Property 6: Notification grouping by store**
    - Generate random match lists with N items across K distinct stores; assert exactly K push notifications are sent, not N
    - Tag: `Feature: route-based-inventory-check, Property 6: notification grouping by store`
    - **Validates: Requirements 4.6**
  - [ ]* 5.5 Write unit tests for `NotificationService`
    - Mock FCM client; assert grouping logic, retry scheduling, and failure logging
    - _Requirements: 4.1–4.6_

- [x] 6. Checkpoint — ensure all service-layer tests pass
  - Run `pytest app/services/ app/adapters/` and confirm all tests pass. Ask the user if any questions arise.

- [ ] 7. Celery task
  - [x] 7.1 Implement `run_inventory_check_task` in `app/tasks/inventory_check_task.py`
    - Orchestrate `RoutingService → InventoryService → NotificationService` in sequence
    - On `RoutingError` (GPS unavailable), log and exit without querying stores
    - Create and update an `InventoryCheckRun` record (`pending → completed/failed`)
    - Support cancellation of in-flight tasks when a re-route event arrives
    - _Requirements: 1.1, 1.4, 5.2, 5.3_
  - [ ]* 7.2 Write unit tests for the Celery task
    - Mock all three services; assert correct orchestration, error handling, and run record lifecycle
    - _Requirements: 1.1, 1.4, 5.2, 5.3_

- [ ] 8. API endpoints
  - [x] 8.1 Implement `POST /jobs/{job_id}/inventory-check` in `app/routers/inventory.py`
    - Validate artisan GPS location in request body
    - Enqueue `run_inventory_check_task` as a Celery task
    - Return `202 Accepted` with the `InventoryCheckRun` id
    - _Requirements: 1.1, 5.2_
  - [x] 8.2 Implement `PATCH /jobs/{job_id}/bom-items/{item_id}/supply-override`
    - Accept `{ "client_supplied": true/false }` body
    - Persist `client_supplied` and `client_supplied_at` on the `BOMItem`
    - _Requirements: 3.1, 3.2, 3.5_
  - [x] 8.3 Implement `GET /jobs/{job_id}/bom-items`
    - Return all BOM items for the job including `client_supplied` status
    - _Requirements: 3.3_
  - [ ]* 8.4 Write property test: supply override round-trip (Property 7)
    - **Property 7: Supply override round-trip**
    - Generate random BOM items; call PATCH to set `client_supplied=true`, call GET and assert item shows as client-supplied; call PATCH to set `client_supplied=false`, call GET and assert item shows as not client-supplied
    - Tag: `Feature: route-based-inventory-check, Property 7: supply override round-trip`
    - **Validates: Requirements 3.2, 3.5**
  - [ ]* 8.5 Write unit tests for API endpoints
    - Test request validation, 202 response, and error cases for each endpoint
    - _Requirements: 1.1, 3.1–3.3, 5.2_

- [x] 9. Checkpoint — ensure all backend tests pass
  - Run `pytest` across the full backend test suite and confirm all tests pass. Ask the user if any questions arise.

- [ ] 10. Frontend: BOM item supply override UI
  - [x] 10.1 Implement `BOMItemList.tsx` in `app/jobs/[id]/`
    - Render each BOM line item with a "Client will supply" toggle
    - Call `PATCH /jobs/{job_id}/bom-items/{item_id}/supply-override` on toggle change
    - Display current `client_supplied` status fetched from `GET /jobs/{job_id}/bom-items`
    - _Requirements: 3.1, 3.3_
  - [ ]* 10.2 Write unit tests for `BOMItemList.tsx`
    - Mock API calls; assert toggle renders correct state and fires correct PATCH request
    - _Requirements: 3.1, 3.3_

- [ ] 11. Frontend: inventory alert and pre-pay components
  - [x] 11.1 Implement `InventoryAlertBanner.tsx`
    - Display in-app summary of found items mirroring the push notification content
    - Show staleness warning when present in the payload
    - _Requirements: 4.2, 5.4_
  - [x] 11.2 Implement `PrePayModal.tsx`
    - Handle the `Pre_Pay_Link` deep link flow, pre-populating the artisan's account for payment
    - _Requirements: 4.3_
  - [ ]* 11.3 Write unit tests for `InventoryAlertBanner.tsx` and `PrePayModal.tsx`
    - Assert correct rendering of item name, store name, address, pre-pay link, and staleness warning
    - _Requirements: 4.2, 4.3, 5.4_

- [x] 12. Final checkpoint — full test suite
  - Run the complete test suite (backend + frontend). Ensure all tests pass. Ask the user if any questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each property-based test must run a minimum of 100 Hypothesis iterations (`@settings(max_examples=100)`)
- Each property test must include the tag comment referencing the design document property number
- Checkpoints ensure incremental validation before moving to the next layer
