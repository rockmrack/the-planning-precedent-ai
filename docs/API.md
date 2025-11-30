# Planning Precedent AI - API Documentation

## Overview

The Planning Precedent AI API provides programmatic access to our planning decision database and AI analysis capabilities.

**Base URL:** `https://api.planningprecedent.ai/api/v1`

## Authentication

Currently, the API is open for development. Production will use API keys:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     https://api.planningprecedent.ai/api/v1/search
```

## Rate Limits

- **Free tier:** 60 requests/minute, 500 requests/hour
- **Pro tier:** 300 requests/minute, 5000 requests/hour

## Endpoints

### Search Precedents

Find planning decisions similar to your proposed development.

#### `POST /search`

```bash
curl -X POST https://api.planningprecedent.ai/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Single storey rear extension in Hampstead conservation area with glazed roof",
    "limit": 10,
    "similarity_threshold": 0.7,
    "filters": {
      "wards": ["Hampstead Town"],
      "outcome": "Granted"
    }
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Natural language description of your development |
| `limit` | integer | No | Number of results (1-50, default: 10) |
| `similarity_threshold` | float | No | Minimum similarity score (0-1, default: 0.7) |
| `include_refused` | boolean | No | Include refused applications (default: false) |
| `filters.wards` | string[] | No | Filter by ward names |
| `filters.outcome` | string | No | Filter by outcome (Granted/Refused) |
| `filters.development_types` | string[] | No | Filter by development type |
| `filters.conservation_areas` | string[] | No | Filter by conservation area |
| `filters.date_from` | string | No | Start date (YYYY-MM-DD) |
| `filters.date_to` | string | No | End date (YYYY-MM-DD) |

**Response:**

```json
{
  "query": "Single storey rear extension...",
  "total_matches": 15,
  "search_time_ms": 245.3,
  "precedents": [
    {
      "decision": {
        "id": 1234,
        "case_reference": "2023/1234/P",
        "address": "10 Hampstead High Street, London NW3 1QP",
        "ward": "Hampstead Town",
        "decision_date": "2023-06-15",
        "outcome": "Granted",
        "description": "Erection of single storey rear extension...",
        "conservation_area": "Hampstead Conservation Area"
      },
      "similarity_score": 0.89,
      "relevant_excerpt": "The proposed extension is considered acceptable in terms of design and would preserve the character of the conservation area...",
      "key_policies": ["Policy D1", "Policy D2", "NPPF 130"]
    }
  ]
}
```

---

#### `GET /search/quick`

Quick search with basic filters.

```bash
curl "https://api.planningprecedent.ai/api/v1/search/quick?q=rear%20dormer%20belsize&limit=5"
```

**Query Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `q` | string | Yes | Search query (min 5 chars) |
| `ward` | string | No | Filter by ward |
| `outcome` | string | No | Filter by outcome |
| `limit` | integer | No | Number of results (1-20, default: 5) |

---

### Analysis

Generate AI-powered planning arguments.

#### `POST /analyse`

```bash
curl -X POST https://api.planningprecedent.ai/api/v1/analyse \
  -H "Content-Type: application/json" \
  -d '{
    "query": "I want to build a rear dormer window in a Conservation Area in Belsize Park. It will be clad in zinc and set back 1m from the eaves.",
    "address": "45 Belsize Avenue, London NW3",
    "ward": "Belsize",
    "conservation_area": "Belsize Conservation Area",
    "include_counter_arguments": true
  }'
```

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | Detailed development description (min 20 chars) |
| `address` | string | No | Site address |
| `ward` | string | No | Camden ward |
| `conservation_area` | string | No | Conservation area if applicable |
| `include_counter_arguments` | boolean | No | Include potential objections (default: true) |

**Response:**

```json
{
  "summary": "Based on 8 similar approved applications in Belsize Park, your proposed dormer has a good chance of approval...",
  "recommendation": "Proceed with confidence. Strong precedent support exists.",
  "arguments": [
    {
      "heading": "Design and Visual Impact",
      "content": "The proposed zinc-clad dormer is consistent with approvals at similar properties...",
      "supporting_cases": ["2023/1234/P", "2022/5678/P"],
      "policy_references": ["Policy D1", "Policy D3"],
      "officer_quotes": [
        {
          "case": "2023/1234/P",
          "quote": "The zinc cladding is considered subordinate and appropriate to the rear elevation."
        }
      ]
    }
  ],
  "risk_assessment": {
    "approval_likelihood": "High",
    "confidence_score": 0.82,
    "key_risks": ["Potential neighbour objection on overlooking"],
    "mitigation_suggestions": ["Consider obscured glazing for privacy"]
  },
  "precedents_used": [...],
  "policies_referenced": ["Policy D1", "Policy D2", "Policy D3", "NPPF 130"],
  "generated_at": "2024-01-15T10:30:00Z",
  "model_version": "gpt-4o"
}
```

---

#### `POST /analyse/appeal`

Generate appeal arguments for a refused application.

```bash
curl -X POST https://api.planningprecedent.ai/api/v1/analyse/appeal \
  -H "Content-Type: application/json" \
  -d '{
    "case_reference": "2024/0001/P",
    "refusal_reasons": "The proposed dormer would be out of keeping with the character of the conservation area."
  }'
```

**Response:**

```json
{
  "refused_case": {
    "reference": "2024/0001/P",
    "address": "12 Example Road, NW3",
    "refusal_reasons": "..."
  },
  "similar_approved_cases": [
    {
      "reference": "2023/4567/P",
      "address": "14 Example Road, NW3",
      "similarity": 0.91,
      "decision_date": "2023-08-20"
    }
  ],
  "appeal_argument": "The Local Planning Authority's decision is inconsistent with their approval of application 2023/4567/P at 14 Example Road...",
  "strength_assessment": {
    "rating": "Strong",
    "score": 0.85,
    "reason": "Found 3 recent similar approvals with high similarity"
  }
}
```

---

### Cases

Browse and retrieve individual planning cases.

#### `GET /cases/{case_reference}`

```bash
curl https://api.planningprecedent.ai/api/v1/cases/2023%2F1234%2FP
```

**Response:**

```json
{
  "decision": {
    "id": 1234,
    "case_reference": "2023/1234/P",
    "address": "10 Hampstead High Street",
    "ward": "Hampstead Town",
    "decision_date": "2023-06-15",
    "outcome": "Granted",
    "description": "...",
    "conservation_area": "Hampstead Conservation Area"
  },
  "full_text": "DELEGATED REPORT\n\n1. PROPOSAL...",
  "related_cases": [...],
  "similar_cases": [...],
  "key_policies": ["Policy D1", "Policy D2"],
  "officer_conclusions": "The proposal is acceptable..."
}
```

---

#### `GET /cases`

List cases with filters and pagination.

```bash
curl "https://api.planningprecedent.ai/api/v1/cases?ward=Hampstead%20Town&outcome=Granted&page=1&page_size=20"
```

**Query Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `ward` | string | Filter by ward |
| `outcome` | string | Filter by outcome |
| `development_type` | string | Filter by development type |
| `date_from` | string | Start date (YYYY-MM-DD) |
| `date_to` | string | End date (YYYY-MM-DD) |
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Results per page (1-100, default: 20) |

---

### Export

Generate PDF reports.

#### `POST /export/pdf`

```bash
curl -X POST https://api.planningprecedent.ai/api/v1/export/pdf \
  -H "Content-Type: application/json" \
  -d '{"site_address": "10 Hampstead High Street", "client_name": "Mr Smith"}' \
  --output report.pdf
```

---

### Reference Data

#### `GET /stats`

Database statistics.

```json
{
  "total_decisions": 12456,
  "granted_count": 9234,
  "refused_count": 3222,
  "date_range_start": "2015-01-01",
  "date_range_end": "2024-12-31",
  "wards_covered": ["Hampstead Town", "Belsize", ...],
  "total_chunks": 245678
}
```

#### `GET /wards`

List all wards with statistics.

#### `GET /policies`

Reference list of planning policies.

#### `GET /conservation-areas`

List Camden conservation areas.

---

## Error Handling

All errors return JSON with this structure:

```json
{
  "detail": "Error message explaining what went wrong"
}
```

**HTTP Status Codes:**

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid parameters) |
| 404 | Resource not found |
| 422 | Validation error |
| 429 | Rate limit exceeded |
| 500 | Server error |

---

## Webhooks (Coming Soon)

Subscribe to events:
- New decisions added
- Scraping completed
- Weekly digest

---

## SDKs

### Python

```python
from planning_precedent import Client

client = Client(api_key="your-key")

results = client.search("rear extension hampstead")
for precedent in results.precedents:
    print(f"{precedent.decision.case_reference}: {precedent.similarity_score}")
```

### JavaScript/TypeScript

```typescript
import { PlanningPrecedentClient } from '@planning-precedent/client';

const client = new PlanningPrecedentClient({ apiKey: 'your-key' });

const results = await client.search({
  query: 'rear extension hampstead',
  limit: 10,
});
```

---

## Support

- **Documentation:** https://docs.planningprecedent.ai
- **Email:** api-support@planningprecedent.ai
- **Status:** https://status.planningprecedent.ai
