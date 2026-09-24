# CareCloud Voice AI Patient Registration

A small end-to-end take-home implementation for a voice-based patient registration workflow.

## Architecture

Caller → Vapi voice assistant → FastAPI Vapi function-tool endpoint → service/database layer → PostgreSQL (production) or SQLite (local)

The same backend also exposes the required patient REST API and a lightweight dashboard.

## Why this stack

- **Vapi** abstracts telephony, STT, TTS, interruption handling, and LLM orchestration so the implementation can focus on conversational behavior and integration.
- **FastAPI + Pydantic** provides concise REST endpoints and server-side validation.
- **PostgreSQL** is recommended for deployed persistence. SQLite is included as a zero-setup local fallback.
- **Jinja2 dashboard** is deliberately minimal because the assessment prioritizes a working end-to-end voice system over frontend complexity.

## Required REST API

- `GET /patients` — list patients; supports `last_name`, `date_of_birth`, `phone_number`
- `GET /patients/{patient_id}` — get one patient
- `POST /patients` — create a patient
- `PUT /patients/{patient_id}` — partial update
- `DELETE /patients/{patient_id}` — soft delete (`deleted_at`)

All API responses use the envelope:

```json
{"data": {}, "error": null}
```

Validation failures also use the same envelope.

## Voice integration

Vapi Custom/Function Tools point to:

`POST https://YOUR-DOMAIN/vapi/tool`

Supported tool names:

- `lookup_patient_by_phone`
- `save_patient`
- `update_patient`

`save_patient` is intended to be invoked only after an explicit caller confirmation. The Vapi system prompt is included in `VAPI_SYSTEM_PROMPT.md`; tool definitions are in `vapi_tools.json`.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open:

- API docs: `http://127.0.0.1:8000/docs`
- Dashboard: `http://127.0.0.1:8000/dashboard`
- Health: `http://127.0.0.1:8000/health`

## Production database

Set `DATABASE_URL` to a persistent PostgreSQL connection string, for example a Railway/Supabase/Neon database. The app also accepts `postgres://` and `postgresql://` prefixes and converts them to the psycopg SQLAlchemy driver.

## Vapi setup

1. Create a Vapi assistant.
2. Put the contents of `VAPI_SYSTEM_PROMPT.md` into the assistant system prompt.
3. Create three Custom/Function Tools matching `vapi_tools.json`.
4. Replace `https://YOUR-DOMAIN/vapi/tool` with the deployed backend URL.
5. Attach the tools to the assistant.
6. Provision a U.S. Vapi phone number and assign the assistant to inbound calls.
7. Make a test registration call, confirm the data, then verify it via `/patients` and `/dashboard`.

## Security

- Secrets/database credentials are supplied only through environment variables.
- Pydantic validates caller-influenced data again at the server boundary.
- No real patient data should be used; this is an assessment/demo system and is not represented as HIPAA-compliant production software.

## Observability

Successful voice registrations log the call ID and final persisted payload to stdout. API creates and updates are also logged.

## Known trade-offs / limitations

- Database migrations are not included; tables are created on startup to fit the assessment time constraint.
- Authentication is omitted from the demo CRUD endpoints. In a real healthcare system, API auth/RBAC and audit controls would be mandatory.
- Phone validation checks U.S. digit length, not carrier ownership/line type.
- The dashboard is read-only and intentionally simple.

## Tests

```bash
pytest -q
```

Tests cover successful creation and key invalid-input cases.

## Next steps

If more time were available: persist call transcripts, add structured audit logs, add authentication/RBAC, migrations, stronger duplicate rules, and integration tests against the deployed Vapi assistant.
