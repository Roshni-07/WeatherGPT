# Backend Data Schema
## WeatherGPT — PostgreSQL (PostGIS) + MongoDB + Redis

---

### 1. PostgreSQL (Structured, Geo-Indexed)

#### `users`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| phone_number | TEXT (unique) | primary identity for IVR/WhatsApp linkage |
| preferred_language | TEXT | ISO code |
| persona | ENUM | farmer / fisherman / general / aviation / researcher / disaster_officer |
| home_location | GEOGRAPHY(Point) | PostGIS point |
| home_geohash | TEXT | indexed, used for fast crowd-report joins |
| notification_channels | TEXT[] | e.g. {push, whatsapp, sms, ivr} |
| reliability_score | FLOAT | for crowd-report weighting |
| created_at | TIMESTAMP | |

#### `persona_context`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| user_id | UUID (FK → users) | |
| crop_type | TEXT | nullable, farmer only |
| sowing_date | DATE | nullable |
| fishing_route | GEOGRAPHY(LineString) | nullable, fisherman only |
| commute_path | GEOGRAPHY(LineString) | nullable, general/urban |

#### `weather_cache`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| geohash | TEXT (indexed) | |
| source | TEXT | imd / openweather / nasa_power / gfs |
| payload | JSONB | raw normalized response |
| fetched_at | TIMESTAMP | TTL enforced via cron/Redis mirror |

#### `alerts`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| source_bulletin_id | TEXT | IMD/NDMA reference |
| severity | ENUM | advisory / moderate / severe |
| affected_area | GEOGRAPHY(Polygon) | PostGIS polygon |
| message | TEXT | canonical English message |
| translations | JSONB | {lang_code: translated_text} |
| issued_at | TIMESTAMP | |
| expires_at | TIMESTAMP | |

#### `alert_dispatch_log`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| alert_id | UUID (FK → alerts) | |
| user_id | UUID (FK → users) | |
| channel | TEXT | push/whatsapp/sms/ivr |
| status | ENUM | sent / delivered / acknowledged / failed |
| dispatched_at | TIMESTAMP | |
| escalated | BOOLEAN | true if channel escalation was triggered |

#### `crowd_reports`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| user_id | UUID (FK → users) | |
| geohash | TEXT (indexed) | |
| report_type | ENUM | text / voice / photo |
| content_url | TEXT | nullable, media storage reference |
| extracted_condition | TEXT | e.g. "heavy_rain", "clear" |
| confidence_weight | FLOAT | derived from user reliability_score |
| submitted_at | TIMESTAMP | |

#### `confidence_scores`
| Column | Type | Notes |
|---|---|---|
| id | UUID (PK) | |
| geohash | TEXT | |
| parameter | TEXT | rainfall/temp/wind |
| score | FLOAT | 0-1 |
| computed_at | TIMESTAMP | |
| contributing_factors | JSONB | source_agreement, recency, crowd_corroboration_count |

---

### 2. MongoDB (Unstructured / High-Write)

#### `chat_logs`
```json
{
  "_id": "ObjectId",
  "user_id": "uuid",
  "session_id": "uuid",
  "channel": "app | whatsapp | ivr",
  "turns": [
    {
      "role": "user | assistant",
      "raw_text": "string",
      "detected_language": "string",
      "translated_text": "string",
      "intent": { "location": "", "time_window": "", "parameter": "" },
      "timestamp": "ISODate"
    }
  ],
  "created_at": "ISODate"
}
```

#### `raw_bulletin_ingest`
```json
{
  "_id": "ObjectId",
  "source": "IMD | NDMA",
  "raw_payload": "string/JSON as received",
  "ingested_at": "ISODate",
  "processed": "boolean"
}
```

---

### 3. Redis (Cache / Session / Rate Limiting)
- `session:{user_id}` — active conversation state, TTL 30 min
- `weather:{geohash}:current` — cached current conditions, TTL 10–15 min
- `ratelimit:{user_id}` — sliding window counter for API abuse prevention
- `ivr_call_state:{call_sid}` — transient IVR call session data

---

### 4. Indexing Notes
- GIST index on all `GEOGRAPHY` columns for fast radius/polygon queries during alert fan-out
- Composite index on `weather_cache(geohash, source, fetched_at)` for freshest-source lookup
- TTL/partial index on `alerts(expires_at)` to auto-exclude expired alerts from active queries
