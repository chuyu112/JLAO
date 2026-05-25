# JLAO MVP Demo Design

Date: 2026-05-24
Status: approved direction from user

## Goal

Build the first real vertical slice of the new JLAO PRD: frontend, backend, database, and knowledge base all present in the MVP demo.

The demo must show that JLAO is no longer only a live suggestion tool. It should behave as a live AI operation brain that can see/hear the live room, read knowledge, remember customer facts, simulate customers, coordinate agents, and persist the session.

## Scope

This slice includes:

- Database foundation with SQLAlchemy models and repositories.
- Local SQLite default (`data/jlao-mvp.sqlite`) plus PostgreSQL support through `DATABASE_URL`.
- Knowledge base reader for `C:\Users\chuyu\Desktop\wiki.md`.
- Virtual customer pool with customer memory and high-value alerts.
- Five MVP agents: atmosphere, product expert, customer relationship, risk control, and conversion.
- Agent utterance persistence and WebSocket push to the live dashboard.
- Frontend panels for knowledge hits, virtual customers, customer events, and agent utterances.

This slice does not include real automated comment sending. The existing scrcpy and adb capture path stays intact. Real low-risk comment sending is the next slice after pause, queue, throttling, and anti-misfire controls exist.

## Architecture

The backend remains FastAPI. Existing routes continue to work, but core fact data moves from process memory into the database.

Runtime-only state remains in memory:

- WebSocket connections.
- STT socket state.
- scrcpy subprocess state.
- adb screenshot loops.

Persistent fact data moves to SQLAlchemy:

- Products.
- Live sessions.
- Transcript segments.
- Suggestions.
- Frame snapshots.
- Replay reports.
- Wiki chunks.
- Virtual customers.
- Customer memories.
- Virtual customer events.
- Agent profiles.
- Agent utterances.

The MVP uses `Base.metadata.create_all()` at startup. This avoids migration overhead for the demo while keeping the model layout ready for Alembic later.

## Data Flow

On startup:

1. Initialize the database.
2. Seed products from `data/samples/products.json` if empty.
3. Seed virtual customers and agent profiles from sample data if empty.
4. Read and index `C:\Users\chuyu\Desktop\wiki.md` if present.

On every final transcript:

1. Persist the transcript.
2. Update product recognition using text signals.
3. Search wiki chunks using transcript keywords and current product fields.
4. Generate virtual customer events from current context.
5. Generate agent utterances from product, transcript, wiki hits, and customer events.
6. Run risk classification.
7. Persist customer events and agent utterances.
8. Push WebSocket events to the dashboard.

## Backend Interfaces

New routes:

- `GET /api/wiki/chunks`
- `GET /api/wiki/search?q=...`
- `POST /api/wiki/reload`
- `GET /api/sessions/{session_id}/virtual-customers`
- `GET /api/sessions/{session_id}/customer-events`
- `GET /api/sessions/{session_id}/agent-utterances`
- `GET /api/agents`

New WebSocket events:

- `wiki_hits`
- `virtual_customer_event`
- `agent_utterance`
- `high_value_customer_alert`

## Frontend

The existing dashboard gets a new PRD demo area without replacing the current panels.

Panels:

- Wiki hits: shows matching headings and short excerpts.
- Virtual customers: shows nickname, level, preference tags, budget, and status.
- Customer event stream: shows进房, 提问, 兴趣表达, and high-value alerts.
- Agent utterance stream: shows agent name, role, risk level, send mode, status, and content.

The UI should be dense and operational, not a marketing page. It should keep the existing dark dashboard style.

## Risk Rules

Agent utterances use three send modes:

- `auto_simulated`: low-risk content that can be shown as simulated auto speech in JLAO.
- `needs_review`: medium-risk personalized or sales content.
- `blocked`: high-risk content, privacy content, promises, price guarantees, investment claims, or dispute replies.

No utterance is sent to the real live room in this slice.

## Testing

Backend tests cover:

- Database startup and product seed.
- Wiki markdown splitting and search.
- Virtual customer event generation.
- Agent utterance generation and risk classification.
- Transcript flow producing persisted events and utterances.

Frontend verification:

- TypeScript build passes.
- Dashboard loads new panels without breaking existing live session flow.

## Acceptance

The MVP demo slice is done when:

- The app can run with SQLite by default.
- `DATABASE_URL` can point to PostgreSQL without code changes.
- The dashboard shows persisted products, sessions, transcripts, suggestions, frames, customer events, and agent utterances.
- The backend can read `C:\Users\chuyu\Desktop\wiki.md`.
- A transcript triggers wiki hits, virtual customer events, and five-agent output.
- High-value virtual customers trigger visible alerts.
- High-risk agent output is marked blocked and not auto-sendable.
- Existing scrcpy, phone capture, STT, suggestion, and replay flows are not broken.
