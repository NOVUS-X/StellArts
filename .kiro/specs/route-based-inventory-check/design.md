# Design Document: Route-Based Inventory Check

## Overview

This feature adds a geospatially-aware inventory checking pipeline to the artisan marketplace. When an artisan accepts a job, the system computes a route corridor, queries hardware store APIs for BOM items located along that corridor, and delivers pre-emptive push notifications with pre-pay links. Clients can mark materials as already supplied to suppress unnecessary queries.

The implementation spans the FastAPI backend (new service layer + async task pipeline), the Next.js frontend (client supply override UI), and leverages PostGIS for geospatial corridor queries. No Soroban smart contract changes are required for this feature — pre-payment links route to the existing payment flow.

---

## Architecture

```mermaid
flowchart TD
    A[Artisan accepts job] --> B[POST /jobs/{id}/start-route]
    B --> C[RoutingService: compute route polyline]
    C --> D[InventoryService: find stores in corridor\nPostGIS ST_Buffer + ST_Intersects]
    D --> E{Stores found?}
    E -- No --> F[Log: no stores on route]
    E -- Yes --> G[Fetch BOM for job\nexclude client-supplied items]
    G --> H[Fan-out: async query each Store_API\nasync gather with 5s timeout]
    H --> I[Aggregate in-stock results]
    I --> J[NotificationService: send push notifications\ngrouped by store]
    J --> K[Artisan device receives push\nwith Pre_Pay_Link]

    L[Client edits job] --> M[PATCH /jobs/{id}/bom-items/{item_id}/supply-override]
    M --> N[Persist Client_Supply_Override]
```

The pipeline is triggered asynchronously via a Celery task (not a FastAPI BackgroundTask) because it involves multiple external HTTP calls, a 30-second SLA, and retry logic — all of which benefit from a dedicated worker process rather than the request event loop.

---

## Components and Interfaces

### 1. RoutingService (`app/services/routing_service.py`)

Wraps an external routing provider (e.g., Google Maps Directions API or OpenRouteService) to return a GeoJSON LineString representing the route.

```python
class RoutingService:
    async def compute_route(
        self,
        origin: Coordinate,       # artisan's current GPS location
        destination: Coordinate,  # job site location
    ) -> RouteResult:
        """
        Returns a GeoJSON LineString polyline and estimated duration.
        Raises RoutingError if origin is unavailable or routing fails.
        """
```

**RouteResult**:
```python
@dataclass
class RouteResult:
    polyline: dict          # GeoJSON LineString
    duration_seconds: int
    distance_meters: int
```

### 2. InventoryService (`app/services/inventory_service.py`)

Core orchestrator. Finds stores in the corridor, fetches BOM, fans out store queries, aggregates results.

```python
class InventoryService:
    async def run_inventory_check(
        self,
        job_id: UUID,
        route: RouteResult,
        corridor_meters: int = 500,
    ) -> InventoryCheckResult:
        """
        1. Queries PostGIS for stores within corridor_meters of route polyline.
        2. Fetches BOM for job_id, excluding client-supplied items.
        3. Fans out async Store_API queries (5s timeout each).
        4. Returns aggregated in-stock matches.
        """
```

**PostGIS corridor query** (executed via SQLAlchemy + GeoAlchemy2):
```sql
SELECT s.*
FROM stores s
WHERE ST_Intersects(
    s.location::geography,
    ST_Buffer(
        ST_GeomFromGeoJSON(:polyline)::geography,
        :corridor_meters
    )
);
```

### 3. StoreAPIAdapter (`app/adapters/store_api_adapter.py`)

Abstract base + concrete implementations per store chain. Each adapter normalizes the external store's inventory response into a common `StockResult`.

```python
class StoreAPIAdapter(ABC):
    @abstractmethod
    async def check_stock(
        self,
        store_id: str,
        bom_items: list[BOMItem],
    ) -> list[StockResult]:
        """Query a single store for a list of BOM items."""

@dataclass
class StockResult:
    bom_item_id: UUID
    store_id: str
    in_stock: bool
    quantity_available: int
    item_url: str           # used to build Pre_Pay_Link
    data_timestamp: datetime  # for staleness check
```

### 4. NotificationService (`app/services/notification_service.py`)

Sends push notifications via Firebase Cloud Messaging (FCM) or Web Push. Groups results by store before sending.

```python
class NotificationService:
    async def send_inventory_alerts(
        self,
        artisan_id: UUID,
        matches: list[StoreMatch],  # grouped by store
    ) -> list[NotificationResult]:
        """
        Sends one push notification per store with in-stock items.
        Includes Pre_Pay_Link per item.
        Retries once after 60s on delivery failure.
        """
```

**Push notification payload**:
```json
{
  "title": "Parts available on your route",
  "body": "Found copper coupling + 2 others at Store #402 (0.3 mi ahead)",
  "data": {
    "store_id": "402",
    "store_name": "Store #402",
    "store_address": "123 Main St",
    "items": [
      {
        "name": "Copper Coupling 3/4\"",
        "pre_pay_url": "https://app.example.com/prepay?store=402&item=SKU-9981&job=JOB-123"
      }
    ]
  }
}
```

### 5. Celery Task (`app/tasks/inventory_check_task.py`)

Wraps the full pipeline as a Celery task triggered on job acceptance.

```python
@celery_app.task(bind=True, max_retries=0)
def run_inventory_check_task(self, job_id: str, artisan_location: dict):
    """
    Orchestrates: RoutingService → InventoryService → NotificationService.
    Runs in a Celery worker, not the FastAPI event loop.
    """
```

### 6. API Endpoints (`app/routers/inventory.py`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/jobs/{job_id}/inventory-check` | Trigger inventory check (called on job acceptance) |
| `PATCH` | `/jobs/{job_id}/bom-items/{item_id}/supply-override` | Set/unset client supply override |
| `GET` | `/jobs/{job_id}/bom-items` | List BOM items with supply override status |

### 7. Frontend Components (`app/jobs/[id]/`)

- `BOMItemList.tsx` — renders BOM items with a "Client will supply" toggle per item
- `InventoryAlertBanner.tsx` — shows in-app summary of found items (mirrors push notification)
- `PrePayModal.tsx` — handles the pre-pay deep link flow

---

## Data Models

### Store (new table)

```sql
CREATE TABLE stores (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    address     TEXT NOT NULL,
    location    GEOMETRY(Point, 4326) NOT NULL,  -- PostGIS point
    api_adapter VARCHAR(100) NOT NULL,            -- e.g. "home_depot", "lowes"
    api_config  JSONB,                            -- adapter-specific credentials/config
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_stores_location ON stores USING GIST(location);
```

### BOMItem (extends existing Issue-17 model)

```sql
ALTER TABLE bom_items
    ADD COLUMN client_supplied BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN client_supplied_at TIMESTAMPTZ;
```

### InventoryCheckRun (new table)

```sql
CREATE TABLE inventory_check_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID NOT NULL REFERENCES jobs(id),
    route_polyline  JSONB NOT NULL,
    corridor_meters INT NOT NULL DEFAULT 500,
    status          VARCHAR(50) NOT NULL,  -- pending, completed, failed
    started_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ,
    result_summary  JSONB
);
```

### InventoryNotification (new table)

```sql
CREATE TABLE inventory_notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id          UUID NOT NULL REFERENCES jobs(id),
    artisan_id      UUID NOT NULL REFERENCES users(id),
    bom_item_id     UUID NOT NULL REFERENCES bom_items(id),
    store_id        UUID NOT NULL REFERENCES stores(id),
    sent_at         TIMESTAMPTZ,
    delivery_status VARCHAR(50),  -- sent, failed, retried
    pre_pay_url     TEXT NOT NULL,
    UNIQUE (job_id, bom_item_id)  -- enforce one notification per item per job
);
```

---

## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Corridor containment

*For any* route polyline and corridor width, every store returned by the corridor query must have its location geometry intersecting the buffered polyline — no store outside the corridor should appear in results.

**Validates: Requirements 1.2, 5.1**

---

### Property 2: Client-supplied items are excluded from queries

*For any* job with one or more BOM items marked as client-supplied, the set of items sent to any Store_API adapter must not contain any client-supplied item.

**Validates: Requirements 2.5, 3.4**

---

### Property 3: One notification per BOM item per job

*For any* job and any BOM item, after a completed inventory check run, the `inventory_notifications` table must contain at most one row for that (job_id, bom_item_id) pair.

**Validates: Requirements 4.4**

---

### Property 4: Stale data flagging

*For any* StockResult whose `data_timestamp` is more than 1 hour before the check run's `started_at`, the resulting push notification payload must include a staleness warning field.

**Validates: Requirements 5.4**

---

### Property 5: Store query fan-out timeout isolation

*For any* set of Store_API adapters where one or more adapters time out (exceed 5 seconds), the remaining adapters' results must still be collected and processed — a single adapter failure must not prevent results from other adapters.

**Validates: Requirements 2.4**

---

### Property 6: Notification grouping by store

*For any* inventory check run that finds N BOM items in stock across K distinct stores (K ≤ N), the number of push notifications sent must equal K, not N.

**Validates: Requirements 4.6**

---

### Property 7: Supply override round-trip

*For any* BOM item, setting the client_supplied flag to true and then reading back the BOM item list must show that item as client-supplied; setting it back to false must show it as not client-supplied.

**Validates: Requirements 3.2, 3.5**

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Artisan GPS unavailable | `RoutingService` raises `RoutingError`; Celery task logs and exits without querying stores |
| No stores in corridor | Log "no stores on route", mark run as `completed` with empty result |
| Store_API timeout (>5s) | Mark that store as `unavailable`, continue with remaining stores |
| Store_API HTTP error | Same as timeout — mark unavailable, continue |
| FCM push delivery failure | Log failure, schedule single retry after 60 seconds via Celery `countdown=60` |
| Invalid artisan device token | Log and skip retry; surface in admin dashboard |
| Route re-computation (re-routing) | Cancel any in-flight Celery task for the job, enqueue a new one with updated route |

---

## Testing Strategy

### Unit Tests (pytest)

- `RoutingService`: mock external routing API, assert correct GeoJSON LineString output and error on missing GPS
- `InventoryService.run_inventory_check`: mock PostGIS query and Store_API adapters, assert correct BOM filtering and result aggregation
- `StoreAPIAdapter` implementations: mock HTTP responses, assert normalization to `StockResult`
- `NotificationService`: mock FCM client, assert grouping logic and retry scheduling
- Edge cases: empty BOM, all items client-supplied, zero stores in corridor, all stores time out

### Property-Based Tests (Hypothesis)

Each property test runs a minimum of 100 iterations.

- **Property 1** — `test_corridor_containment`: generate random polylines and store point sets; assert all returned stores intersect the buffer. Tag: `Feature: route-based-inventory-check, Property 1: corridor containment`
- **Property 2** — `test_client_supplied_exclusion`: generate random BOM lists with random client-supplied flags; assert no client-supplied item appears in any adapter call. Tag: `Feature: route-based-inventory-check, Property 2: client-supplied items excluded`
- **Property 3** — `test_one_notification_per_item`: generate random multi-store match sets; assert deduplication produces at most one notification row per (job, bom_item). Tag: `Feature: route-based-inventory-check, Property 3: one notification per BOM item per job`
- **Property 4** — `test_stale_data_flagging`: generate StockResults with random timestamps; assert staleness flag present iff timestamp > 1 hour old. Tag: `Feature: route-based-inventory-check, Property 4: stale data flagging`
- **Property 5** — `test_timeout_isolation`: generate adapter sets with random timeout patterns; assert non-timing-out adapters always contribute results. Tag: `Feature: route-based-inventory-check, Property 5: store query fan-out timeout isolation`
- **Property 6** — `test_notification_grouping`: generate random match lists with repeated stores; assert notification count equals distinct store count. Tag: `Feature: route-based-inventory-check, Property 6: notification grouping by store`
- **Property 7** — `test_supply_override_round_trip`: generate random BOM items; set override, read back, unset, read back; assert round-trip consistency. Tag: `Feature: route-based-inventory-check, Property 7: supply override round-trip`
