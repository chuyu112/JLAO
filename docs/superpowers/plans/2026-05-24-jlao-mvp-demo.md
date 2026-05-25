# JLAO MVP Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP demo vertical slice with frontend, backend, database, and knowledge base.

**Architecture:** Add SQLAlchemy persistence while preserving the current FastAPI and Vue dashboard flow. Keep runtime process state in memory, but persist business facts and PRD demo objects in SQLite/PostgreSQL-backed tables.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Pinia, Naive UI, TypeScript.

---

### Task 1: Backend Tests

**Files:**
- Create: `backend/tests/test_mvp_services.py`

- [ ] Add failing tests for wiki splitting/search, database seeding, virtual customer events, and agent utterance risk modes.
- [ ] Run `python -m unittest discover backend/tests` and verify the tests fail because modules do not exist.

### Task 2: Database Foundation

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/db_models.py`
- Create: `backend/app/repositories.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/state.py`

- [ ] Implement SQLAlchemy engine/session setup with SQLite default and `DATABASE_URL` override.
- [ ] Define tables for existing facts and new PRD demo objects.
- [ ] Seed products, virtual customers, and agent profiles.
- [ ] Hydrate existing `app_state` from database at startup.
- [ ] Run backend tests.

### Task 3: Knowledge Base

**Files:**
- Create: `backend/app/services/wiki_service.py`
- Create: `backend/app/api/wiki.py`
- Create: `data/samples/wiki.md`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`

- [ ] Read `JLAO_WIKI_PATH` or default `C:\Users\chuyu\Desktop\wiki.md`.
- [ ] Fall back to `data/samples/wiki.md` for demo reliability.
- [ ] Split Markdown by headings and search relevant chunks.
- [ ] Persist indexed chunks.
- [ ] Expose reload/search APIs.
- [ ] Run backend tests.

### Task 4: Virtual Customers And Agents

**Files:**
- Create: `backend/app/services/virtual_customer_service.py`
- Create: `backend/app/services/multi_agent_service.py`
- Create: `backend/app/api/customers.py`
- Create: `backend/app/api/agents.py`
- Create: `data/samples/virtual_customers.json`
- Create: `data/samples/agents.json`
- Modify: `backend/app/services/transcript_service.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`

- [ ] Generate customer events from transcript/product context.
- [ ] Generate five-agent utterances from transcript, product, wiki hits, and customer events.
- [ ] Classify send mode as simulated, review, or blocked.
- [ ] Persist and broadcast events.
- [ ] Run backend tests.

### Task 5: Existing Persistence Hooks

**Files:**
- Modify: `backend/app/api/products.py`
- Modify: `backend/app/api/sessions.py`
- Modify: `backend/app/api/suggestions.py`
- Modify: `backend/app/services/transcript_service.py`
- Modify: `backend/app/services/frame_service.py`
- Modify: `backend/app/api/replay.py`

- [ ] Persist create/update operations for products, sessions, suggestions, transcripts, frames, and replay reports.
- [ ] Keep existing frontend API shapes unchanged.
- [ ] Run backend compile/test checks.

### Task 6: Frontend Panels

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api/jlao.ts`
- Modify: `frontend/src/stores/jlao.ts`
- Create: `frontend/src/components/KnowledgePanel.vue`
- Create: `frontend/src/components/VirtualCustomerPanel.vue`
- Create: `frontend/src/components/AgentUtterancePanel.vue`
- Modify: `frontend/src/pages/LiveDashboard.vue`

- [ ] Add types and API functions.
- [ ] Store wiki hits, customers, customer events, agents, and utterances.
- [ ] Handle new WebSocket events.
- [ ] Render operational panels in the live dashboard.
- [ ] Run frontend build.

### Task 7: Verification

- [ ] Run `python -m unittest discover backend/tests`.
- [ ] Run `python -m compileall backend\app`.
- [ ] Run `npm run build` in `frontend`.
- [ ] Report remaining gaps and next PRD slice.
