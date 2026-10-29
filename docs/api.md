# API guide

Base URL: `http://localhost:18000`. Swagger: `/docs`; schema: `/openapi.json`.

## Authentication

Kong requires an `X-API-Key` header on every `/api/v1` endpoint. Read your local Demo key from the ignored `.env.demo`; do not place keys in query strings or share environment files. In Swagger use **Authorize**. In Postman import the OpenAPI URL and configure collection-level API Key authorization: key `X-API-Key`, value stored in a private local variable, added to the header.

## Endpoints

| Method | Endpoint | Result |
| --- | --- | --- |
| GET | `/health` | Public health check |
| GET | `/api/v1/features` | Paginated records |
| GET | `/api/v1/features/{record_id}` | Record detail |
| POST | `/api/v1/features` | Creation, status 201 |
| PATCH | `/api/v1/features/{record_id}` | Partial feature/label update |
| GET | `/api/v1/features/export` | Flat CSV |
| GET | `/api/v1/patients/{patient_id}/features` | Patient-filtered list |
| GET | `/api/v1/scenarios/{scenario_type}/features` | Scenario-filtered list |
| GET | `/api/v1/stats` | Total/scenario/optional label counts |
| GET | `/api/v1/demo/features` | Fixed in-memory fictional reference fixture |

Lists/export accept `patient`, `scenario`, `label`. Pagination uses `limit` (1?500, default 50) and nonnegative `offset`. The sort is stable by `_id`. Stats accepts `include_labels=false`. Normal Demo endpoints read MongoDB; the reference fixture route is not the database and does not reflect CRUD edits.

```text
GET /api/v1/features?scenario=scenario_1&label=Health&limit=2&offset=0
```

Response shape:

```json
{"total":4,"limit":2,"offset":0,"items":["record objects with features and metadata"]}
```

The abbreviated `items` above illustrates the envelope, not an actual typed API response.

## Create and update

Use fictional data only. Example POST body:

```json
{
  "patient_id":"P99-999",
  "scenario":"scenario_1",
  "label":"Health",
  "configuration_hash":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "dataset":"fictional-api-example",
  "features":{"ECG_Rate_Mean":71.25,"SIM_Rea_cor_pos_5.0":0.5,"EEG_Alpha_AF7":null}
}
```

The API derives a deterministic string ID. Repeating a source identity returns 409. An optional known `source_scenario_id` must be a 24-character hex string; absent source IDs remain null. Names and arbitrary provenance fields are rejected. Patient codes outside the fictional P99 namespace are rejected in Demo.

PATCH body:

```json
{"label":"Left_Loss","features":{"SIM_Rea_cor_pos_5.0":0.75}}
```

Updates merge only supplied feature keys, preserving dotted names as literal keys. Patient/scenario/source identifiers, provenance and import metadata are immutable through PATCH. `updated_at` records API edits; the provenance hash describes the imported version. The idempotent startup seed does not overwrite edits to existing fixture IDs. No DELETE endpoint is provided.

Labels: `Health`, `Disease`, `Fake`, `Right_Loss`, `Left_Loss`. Feature families: ECG, EDA, EEG, EYE, HEAD, SIM, PRE. Values must be finite JSON numbers or null; numeric strings, booleans and out-of-range BSON integers are rejected. POST needs at least one numerical value. CSV preserves exact column names and leaves missing values blank; use `pandas.read_csv(..., float_precision="round_trip")` when checking values.

## Errors

Application errors use `{"error":{"code":"...","message":"..."}}`. Validation details include field locations/types without echoing input values. MongoDB errors do not expose connection details. HTTP statuses are 404, 409, 422 and 503 as appropriate. Kong uses its native JSON `message` envelope for 401 authentication failures and 429 rate limits, with retry headers on 429.
