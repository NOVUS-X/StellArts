# AI Job Matching and Pricing Features

This document describes the implementation of two AI-powered features for the StellArts platform:

1. **Advanced AI Job Matching Engine** (#375)
2. **AI-Powered Price Estimation Tool** (#376)

## Features

### 1. Advanced AI Job Matching Engine

Automatically processes natural language job descriptions to:
- Extract specialty tags using LLM (OpenAI/Gemini)
- Match jobs with qualified artisans within 10km radius
- Notify top 5 highest-rated artisans

**Example:**
```
Client input: "my sink is leaking brown water"
AI Output: ["Plumbing", "Water Heater"]
Action: Notifies top 5 plumbers within 10km
```

### 2. AI-Powered Price Estimation Tool

Provides clients with AI-generated cost estimates:
- Uses LLM to estimate job costs based on description and location
- Falls back to historical data when LLM unavailable
- Displays estimate range (e.g., "$50 - $80") on booking screen

## Configuration

### Environment Variables

Add the following to your `.env` file:

```bash
# LLM Provider (choose 'openai' or 'gemini')
LLM_PROVIDER=openai

# OpenAI Configuration
OPENAI_API_KEY=sk-proj-xxx
OPENAI_MODEL=gpt-4o-mini

# Gemini Configuration (alternative)
GEMINI_API_KEY=AIzaSyXXX
GEMINI_MODEL=gemini-1.5-flash

# Job Matching Settings
JOB_MATCHING_PROXIMITY_KM=10.0
JOB_MATCHING_MAX_ARTISANS=5
SPECIALTY_CONFIDENCE_THRESHOLD=0.70

# Price Estimation Settings
PRICE_ESTIMATE_TIMEOUT_SECONDS=3
HISTORICAL_DATA_MIN_SAMPLE_SIZE=5
```

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run database migration:
```bash
alembic upgrade head
```

3. Start the server:
```bash
uvicorn app.main:app --reload
```

## API Endpoints

### Create Job with AI Matching

**POST** `/api/v1/jobs/create`

Request:
```json
{
  "description": "Fix leaking kitchen sink pipe",
  "location": "123 Main St, New York, NY",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "estimated_hours": 2.0
}
```

Response:
```json
{
  "job_id": "uuid",
  "specialty_tags": ["Plumbing"],
  "matched_artisans": [
    {
      "artisan_id": 1,
      "business_name": "Joe's Plumbing",
      "rating": 4.8,
      "distance_km": 2.3
    }
  ],
  "price_estimate": {
    "min_price": 150.00,
    "max_price": 300.00,
    "confidence": 0.85,
    "method": "llm",
    "reasoning": "Based on typical pipe repair costs"
  },
  "requires_clarification": false,
  "clarification_questions": []
}
```

### Get Price Estimate

**GET** `/api/v1/jobs/{job_id}/estimate`

Response:
```json
{
  "min_price": 150.00,
  "max_price": 300.00,
  "confidence": 0.85,
  "method": "llm",
  "cached": false
}
```

### Admin: LLM Statistics

**GET** `/api/v1/admin/llm/stats`

Query parameters:
- `start_date` (optional): ISO datetime
- `end_date` (optional): ISO datetime

Response:
```json
{
  "total_requests": 1000,
  "successful": 980,
  "errors": 15,
  "rate_limited": 5,
  "success_rate": 0.98,
  "avg_response_time_ms": 1250.5,
  "by_provider": {
    "openai": {
      "total": 1000,
      "successful": 980,
      "errors": 15
    }
  }
}
```

### Admin: Specialty Taxonomy

**GET** `/api/v1/admin/specialty-taxonomy`

Response:
```json
{
  "specialties": ["Plumbing", "Electrical", "HVAC", ...],
  "count": 20
}
```

**POST** `/api/v1/admin/specialty-taxonomy`

Request:
```json
{
  "specialty": "Solar Panel Installation"
}
```

## Architecture

```
Client Request
    ↓
Job Matcher Service
    ↓
LLM Service → OpenAI/Gemini Provider
    ↓
Specialty Validation (Fuzzy Matching)
    ↓
Geospatial Query (Redis)
    ↓
Database Query (PostgreSQL)
    ↓
Notification Dispatch (WebSocket)
    ↓
Price Estimator Service
    ↓
Historical Data Fallback (if needed)
    ↓
Response to Client
```

## Key Components

### Services
- `llm_service.py` - LLM provider abstraction with retry logic
- `job_matcher.py` - Specialty extraction and artisan matching
- `price_estimator.py` - AI-powered price estimation with fallback
- `historical_data_service.py` - Historical pricing analysis

### LLM Providers
- `openai_provider.py` - OpenAI GPT integration
- `gemini_provider.py` - Google Gemini integration

### Models
- `llm_request.py` - LLM request tracking for monitoring
- Extended `booking.py` with AI fields

## Error Handling

The system includes comprehensive error handling:

1. **Rate Limiting**: Exponential backoff with jitter (1s, 2s, 4s)
2. **Retries**: Up to 3 attempts for transient failures
3. **Fallback**: Historical data when LLM unavailable
4. **Validation**: Input validation and sanity checks on estimates

## Monitoring

Track LLM usage through:
- Admin dashboard (`/api/v1/admin/llm/stats`)
- Database table (`llm_requests`)
- Application logs

## Testing

Run tests:
```bash
pytest app/tests/
```

## Specialty Taxonomy

The system supports 20 predefined specialties:
- Plumbing
- Electrical
- HVAC
- Carpentry
- Painting
- Roofing
- Flooring
- Landscaping
- Cleaning
- Appliance Repair
- Handyman
- Pest Control
- Masonry
- Welding
- Drywall
- Tiling
- Locksmith
- Window Installation
- Fence Installation
- Garage Door Repair

Admins can add new specialties through the API.

## Future Enhancements

- Multi-language support
- Image analysis for job requirements
- Dynamic taxonomy expansion
- Machine learning model for pricing
- Caching layer for similar job descriptions

## Support

For issues or questions, refer to:
- GitHub Issues #375 and #376
- Design document: `.kiro/specs/ai-job-matching-and-pricing/design.md`
- Requirements document: `.kiro/specs/ai-job-matching-and-pricing/requirements.md`
