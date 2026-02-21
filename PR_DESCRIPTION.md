# Fix: Integrate IN_PROGRESS state into booking state machine

## Problem
The `IN_PROGRESS` status was defined in the `BookingStatus` enum but completely orphaned from the state machine logic. There were no transitions to enter or exit this state, making it impossible to represent the real-world lifecycle of a service booking (start work → finish work). This blocked proper escrow release triggers and left both parties without clear signals when work begins.

## Solution
Integrated `IN_PROGRESS` into the booking state machine with proper authorization guards:

**New State Flow:**
```
PENDING → CONFIRMED → IN_PROGRESS → COMPLETED
```

**Key Changes:**
- Added `CONFIRMED → IN_PROGRESS` transition (artisan only)
- Changed `COMPLETED` to require `IN_PROGRESS` state (was `CONFIRMED`)
- Updated cancellation rules to allow artisan cancellation from `IN_PROGRESS`
- Added explicit rejection of invalid status transitions
- Updated frontend `BookingCard` component with `in_progress` type and violet styling

## Changes

### Backend
- **`backend/app/api/v1/endpoints/booking.py`**
  - Added `CONFIRMED → IN_PROGRESS` branch with artisan-only guard
  - Updated `COMPLETED` branch to require `IN_PROGRESS` (not `CONFIRMED`)
  - Updated `CANCELLED` branch to include `IN_PROGRESS` for artisan
  - Added `else` clause to reject unhandled status transitions

### Frontend
- **`frontend/components/booking/BookingCard.tsx`**
  - Added `"in_progress"` to status union type
  - Added violet color styling for `in_progress` state

### Tests
- **`backend/app/tests/test_booking_state_machine.py`**
  - Added `TestConfirmedToInProgress` class (3 tests)
  - Added `TestInProgressToCompleted` class (2 tests)
  - Updated `TestCancellationRules` with 2 new tests
  - Updated `TestInvalidTransitions` with 1 new test
  - Updated 2 existing tests to expect new behavior
  - **Total: 8 new tests, 21 total tests**

## Testing
```bash
cd backend
docker-compose exec backend pytest app/tests/test_booking_state_machine.py -v
```

All tests pass ✅

## Acceptance Criteria
- ✅ Artisan can transition CONFIRMED → IN_PROGRESS
- ✅ Client cannot transition to IN_PROGRESS (403)
- ✅ IN_PROGRESS only from CONFIRMED state (400 otherwise)
- ✅ Client can mark IN_PROGRESS → COMPLETED
- ✅ CONFIRMED → COMPLETED blocked (400)
- ✅ Artisan can cancel IN_PROGRESS bookings
- ✅ Client cannot cancel IN_PROGRESS bookings (403)
- ✅ Admin bypass unchanged
- ✅ Frontend renders `in_progress` with distinct styling
- ✅ All existing tests pass
- ✅ 8 new tests cover all transitions

## Impact
- **Escrow Integration:** Payment release can now be cleanly tied to `IN_PROGRESS → COMPLETED`
- **User Experience:** Clear signals for work start/completion
- **Security:** All transitions properly authorized, no unguarded updates
- **Maintainability:** Explicit error handling prevents silent failures
