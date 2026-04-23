# Requirements Document

## Introduction

This feature enables the marketplace platform to dynamically check hardware store inventory along an artisan's route to a job site, ensuring the artisan has all required parts before arriving. The system cross-references the job's Bill of Materials (BOM) with store APIs for stores geographically located along the route, sends pre-emptive push notifications when matching items are found, and allows clients to indicate they already possess certain materials to avoid unnecessary stops.

## Glossary

- **Artisan**: A skilled tradesperson registered on the platform who travels to job sites to perform work.
- **Client**: A person or business that hires an artisan through the platform.
- **Job_Site**: The physical location where an artisan is scheduled to perform work.
- **BOM**: Bill of Materials — the list of parts and quantities required to complete a specific job.
- **Route**: The navigable path from the artisan's current GPS location to the Job_Site.
- **Route_Corridor**: The geographic buffer zone around the Route within which stores are considered "on route".
- **Store_API**: An external third-party inventory API provided by a hardware or supply store.
- **Inventory_Service**: The internal backend service responsible for querying Store_APIs and correlating results with the BOM.
- **Notification_Service**: The internal backend service responsible for sending push notifications to artisans.
- **Push_Notification**: A mobile or web push message delivered to the artisan's device.
- **Pre_Pay_Link**: A deep link embedded in a Push_Notification that directs the artisan to a pre-payment flow for a specific store item.
- **Client_Supply_Override**: A flag set by the client indicating they already possess one or more BOM items, exempting those items from inventory checks.
- **Routing_Service**: The internal or external service that computes the Route and Route_Corridor between two geographic points.

## Requirements

### Requirement 1: Route-Based Store Discovery

**User Story:** As an artisan, I want the system to identify hardware stores along my route to the job site, so that I only receive inventory suggestions for stores I will actually pass.

#### Acceptance Criteria

1. WHEN an artisan accepts a job, THE Routing_Service SHALL compute the Route from the artisan's current GPS location to the Job_Site.
2. WHEN the Route is computed, THE Inventory_Service SHALL identify all registered Store_APIs whose physical locations fall within the Route_Corridor.
3. THE Route_Corridor SHALL be defined as a configurable lateral distance (default: 500 meters) on either side of the Route polyline.
4. IF the artisan's current GPS location is unavailable, THEN THE Routing_Service SHALL return an error and THE Inventory_Service SHALL not perform any store queries.
5. IF no stores are found within the Route_Corridor, THEN THE Inventory_Service SHALL record a "no stores on route" result and take no further action.

---

### Requirement 2: Bill of Materials Cross-Reference

**User Story:** As an artisan, I want the system to check whether stores on my route stock the parts I need, so that I can pick them up without making a detour.

#### Acceptance Criteria

1. WHEN stores within the Route_Corridor are identified, THE Inventory_Service SHALL retrieve the BOM for the associated job.
2. THE Inventory_Service SHALL query each identified Store_API for each BOM line item, including part name, part number, and required quantity.
3. WHEN a Store_API returns a result, THE Inventory_Service SHALL record whether each BOM item is in stock, out of stock, or unavailable at that store.
4. IF a Store_API request fails or times out after 5 seconds, THEN THE Inventory_Service SHALL mark that store's result as "unavailable" and continue processing remaining stores.
5. WHERE a Client_Supply_Override is active for a BOM item, THE Inventory_Service SHALL exclude that item from all Store_API queries.

---

### Requirement 3: Client Supply Override

**User Story:** As a client, I want to indicate which materials I already have on hand, so that the artisan is not directed to purchase items I will supply.

#### Acceptance Criteria

1. WHEN a client creates or edits a job, THE system SHALL present each BOM line item with an option to mark it as client-supplied.
2. WHEN a client marks a BOM item as client-supplied, THE system SHALL persist the Client_Supply_Override for that item on that job.
3. THE system SHALL display the current Client_Supply_Override status for each BOM item to both the client and the artisan before the job begins.
4. WHEN a Client_Supply_Override is set, THE Inventory_Service SHALL exclude the overridden item from inventory queries and Push_Notifications.
5. WHEN a client removes a Client_Supply_Override, THE system SHALL re-include that item in subsequent inventory checks.

---

### Requirement 4: Pre-Emptive Push Notifications

**User Story:** As an artisan, I want to receive a push notification when a required part is available at a store on my route, so that I can pre-pay and pick it up without delay.

#### Acceptance Criteria

1. WHEN the Inventory_Service confirms that a BOM item is in stock at a store within the Route_Corridor, THE Notification_Service SHALL send a Push_Notification to the artisan's registered device.
2. THE Push_Notification SHALL include the item name, the store name, the store address, and a Pre_Pay_Link.
3. THE Pre_Pay_Link SHALL resolve to the correct store item page and pre-populate the artisan's account for payment.
4. THE Notification_Service SHALL send at most one Push_Notification per BOM item per job, regardless of how many stores stock that item.
5. IF the artisan's device token is invalid or the push delivery fails, THEN THE Notification_Service SHALL log the failure and retry delivery once after 60 seconds.
6. WHERE multiple BOM items are available at the same store, THE Notification_Service SHALL consolidate them into a single Push_Notification for that store rather than sending one notification per item.

---

### Requirement 5: Inventory Check Accuracy and Constraints

**User Story:** As a platform operator, I want inventory checks to be geographically accurate and reliable, so that artisans receive only actionable and relevant suggestions.

#### Acceptance Criteria

1. THE Inventory_Service SHALL only query stores whose physical location falls within the computed Route_Corridor.
2. WHEN the artisan's route changes (e.g., due to re-routing), THE Inventory_Service SHALL re-evaluate the Route_Corridor and re-run inventory checks for the updated route.
3. THE Inventory_Service SHALL complete all Store_API queries and deliver results to the Notification_Service within 30 seconds of route computation.
4. IF a Store_API returns inventory data older than 1 hour, THEN THE Inventory_Service SHALL flag the result as potentially stale and include a staleness warning in the Push_Notification.
