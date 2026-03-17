# Helixa Connect: The Engine behind Mimora

Helixa provides the "Digital Soul" factory and the "Hybrid GraphRAG Brain" that powers the Mimora artificial society simulation and serves as the primary "Soul Provider" for the **Vivida** AI-Model creation platform.

> [!IMPORTANT]
> **Vivida Integration**: For the "Selection Stage" in Vivida, use the `GET /external/agents` endpoint. It returns essential fields like `avatar_url` and `ci_score` (Quality Audit), allowing you to build a rich soul-selection gallery.

---

## 1. Authentication

All requests to the Helixa Connect API must be authenticated using an **API Key**. 

- **Header Name**: `X-API-Key`
- **Method**: Include your unique API key in the request header.

Example:
```http
X-API-Key: your_secret_api_key_here
```

---

## 2. Agent Management

Internal Helixa agents (Souls and Vessels) can be created and retrieved through the following endpoints.

### 2.1. Create a Single Agent
Queue the generation of a new AI agent based on provided hints.

- **Endpoint**: `POST /api/v1/external/agents`
- **Content-Type**: `application/json`

**Request Body**:
| Field | Type | Description |
| :--- | :--- | :--- |
| `name_hint` | string | (Optional) Desired name of the agent. |
| `role_hint` | string | (Optional) Desired role or occupation. |
| `personality_hint`| string | (Optional) Personality traits description. |
| `webhook_url` | string | (Optional) URL to notify when generation is complete. |
| `client_reference_id`| string | (Optional) Your internal ID for tracking. |

**Response**:
```json
{
  "job_id": "uuid-v4-string",
  "status": "queued",
  "message": "External agent generation queued."
}
```

### 2.2. Batch Create Agents
Create multiple agents in a single request.

- **Endpoint**: `POST /api/v1/external/batch-agents`
- **Request Body**: An array of objects (see 2.1).

**Response**:
```json
{
  "job_ids": ["uuid-1", "uuid-2", ...],
  "status": "queued",
  "message": "X external agent generations queued."
}
```

### 2.3. List Your Agents
Retrieve a paginated list of all agents belonging to your API key.

- **Endpoint**: `GET /api/v1/external/agents`
- **Query Params**:
    - `limit`: Default 100, max 1000.
    - `offset`: Default 0.

**Response**:
```json
[
  {
    "id": "agent-uuid",
    "name": "Alex Riviera",
    "role": "Cybersecurity Expert",
    "created_at": "2026-03-17T14:00:00"
  },
  ...
]
```

### 2.4. Get Agent Details
Retrieve the full JSON profile of a specific agent.

- **Endpoint**: `GET /api/v1/external/agents/{agent_id}`

---

## 3. Job Tracking & Webhooks

Since agent generation is a complex process (reasoning, lifecycle planning, memory creation), it is performed asynchronously.

### 3.1. Job Status Polling
You can poll the status of a specific generation job.

- **Endpoint**: `GET /api/v1/external/jobs/{job_id}`

**Possible Statuses**: `queued`, `running`, `deferred`, `complete`, `failed`.

### 3.2. Webhooks
If you provide a `webhook_url` in the creation request, Helixa will send an HTTP POST request to that URL once the agent is ready.

**Webhook Payload**:
```json
{
  "job_id": "uuid",
  "status": "completed",
  "result": { ... full agent data ... },
  "client_reference_id": "your-ref-id"
}
```

---

## 4. Error Handling

- **401 Unauthorized**: Missing `X-API-Key` header.
- **403 Forbidden**: Invalid API Key or attempting to access an agent you don't own.
- **404 Not Found**: Agent or Job ID does not exist.
- **422 Unprocessable Entity**: Validation error in request body.

---

*For technical support or feature requests, contact the Helixa Team.*
