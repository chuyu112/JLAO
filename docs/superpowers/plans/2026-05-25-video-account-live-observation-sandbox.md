# Video Account Live Observation Sandbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reposition the MVP from a self-owned live operations brain to a public WeChat Channels jade live observation sandbox with virtual control-room replies.

**Architecture:** Reuse the existing FastAPI services and Vue dashboard. Backend suggestions, multi-agent utterances, and replay reports are relabeled and generated as observation/simulation artifacts. The frontend makes the safety boundary visible: replies are simulated in JLAO only and are never sent to the platform.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Vue 3, TypeScript, Vite, Naive UI.

---

### Task 1: Backend Virtual Reply Semantics

**Files:**
- Modify: `backend/tests/test_mvp_services.py`
- Modify: `backend/app/services/agent_service.py`

- [ ] Write a failing test where a price question produces a `用户问题模拟回复`.
- [ ] Verify the generated content includes `仅模拟，不发送`.
- [ ] Change suggestion generation so public-live replies use `虚拟场控` and simulation-safe wording.
- [ ] Re-run the targeted backend test and confirm it passes.

### Task 2: Backend Virtual Control Agent Flow

**Files:**
- Modify: `backend/tests/test_mvp_services.py`
- Modify: `backend/app/services/multi_agent_service.py`

- [ ] Write a failing test that every agent utterance target includes `仅模拟，不发送`.
- [ ] Update generated utterance target/status wording to `虚拟场控沙盘（仅模拟，不发送）`.
- [ ] Keep risk blocking behavior for high-risk expressions.
- [ ] Re-run the targeted backend test and confirm it passes.

### Task 3: Observation Report Semantics

**Files:**
- Modify: `backend/tests/test_mvp_services.py`
- Modify: `backend/app/services/replay_service.py`

- [ ] Write a failing test that `build_replay_report()` returns an observation report summary for public WeChat Channels jade lives.
- [ ] Rename report text from internal replay language to observation/training language.
- [ ] Ensure `next_suggestions` contains training/sample-building actions rather than next-live operating commands.
- [ ] Re-run the targeted backend test and confirm it passes.

### Task 4: Frontend Product Language

**Files:**
- Modify: `frontend/src/pages/LiveDashboard.vue`
- Modify: `frontend/src/pages/ReplayReport.vue`
- Modify: `frontend/src/components/AgentUtterancePanel.vue`
- Modify: `frontend/src/components/SuggestionPanel.vue`

- [ ] Rename the live console subtitle to observation sandbox language.
- [ ] Rename `多 Agent 发言流` to `虚拟场控回复流`.
- [ ] Add visible `仅模拟，不发送` copy near the virtual reply list.
- [ ] Rename replay report page to observation report and training samples.

### Task 5: Verification

**Files:**
- Test: `backend/tests/test_mvp_services.py`
- Build: `frontend`

- [ ] Run `python -m unittest discover backend\tests`.
- [ ] Run `npm run build` in `frontend`.
- [ ] Report exact verification output and any remaining risks.
