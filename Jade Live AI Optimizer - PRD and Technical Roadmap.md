# Jade Live AI Optimizer (JLAO) PRD and Technical Roadmap

Date: 2026-05-05
Version: v0.2
Status: Draft
Owner: Solo full-stack development

## 1. Product Positioning

Jade Live AI Optimizer, short name JLAO, is a real-time AI optimization system for jadeite live commerce rooms.

The product acts as an AI co-pilot for the anchor, control room operator, customer service operator, and live operations team. It listens to the live stream, watches the live screen, reads product information, observes live metrics, and gives real-time suggestions for product explanation, audience interaction, risk control, and post-live replay.

JLAO is not designed to create fake traffic, automated spam, or platform evasion. Its core model is:

```text
AI observes and recommends
-> human reviews and executes
-> system records and learns from results
```

## 2. Target Users

### 2.1 Primary Users

- Jadeite live stream anchors
- Live room control operators
- Customer service operators
- Live commerce operation managers
- Small jadeite merchants that already run live selling rooms

### 2.2 Initial Use Case

One jadeite live room with one anchor and one control operator.

The first version helps the team:

- Reduce missed product explanation points
- Generate better jadeite-specific selling scripts
- Recommend natural interaction prompts
- Remind the team of compliance and overclaiming risks
- Analyze live session performance after the stream

## 3. Product Goals

### 3.1 MVP Goals

- Convert live audio to real-time transcript
- Capture live screen frames every 2-5 seconds
- Maintain a structured live context
- Match current live content with jadeite product data
- Generate real-time anchor script suggestions
- Generate operator interaction suggestions
- Detect missed jadeite product explanation points
- Detect risky sales language
- Produce a post-live replay report

### 3.2 Business Goals

- Help new anchors speak closer to experienced anchors
- Help operators know when to guide comments and questions
- Improve explanation quality for jadeite products
- Build reusable script assets for each product type
- Build a data feedback loop from live session to next live session

## 4. Non-Goals

JLAO v1 does not include:

- Automatic control of third-party live platform apps
- Automatic comment posting
- Automatic liking or following
- Device fingerprint bypass
- Platform risk-control evasion
- Fake identities or fake audience behavior
- Fine-tuned model training in the first MVP

The first MVP uses role prompts, product knowledge, live context, and human approval.

## 5. Core Product Concept

JLAO should answer four real-time questions:

1. What is the anchor saying now?
2. What product or object is being shown now?
3. What should the anchor or operator do next?
4. What should be reviewed after the live session?

## 6. User Workflow

### 6.1 Before Live

1. Operator creates a live session.
2. Operator imports or enters product data.
3. Operator selects the live room category: jadeite hand bangle, pendant, bead string, ring face, carving, or mixed.
4. Operator prepares default script templates and risk terms.
5. Operator starts live capture.

### 6.2 During Live

1. System captures live audio and screen.
2. STT service generates transcript segments.
3. Vision service summarizes key screen frames.
4. Context engine merges transcript, frame summary, product data, and live metrics.
5. AI agents generate suggestions.
6. Compliance agent filters or rewrites risky output.
7. Suggestions appear on the control dashboard.
8. Human operator accepts, edits, copies, rejects, or marks suggestions as used.
9. System records each suggestion and its result.

### 6.3 After Live

1. System generates a replay report.
2. Report summarizes timeline, product explanation quality, high-interaction moments, cold moments, risky phrases, and recommended improvements.
3. Useful scripts are saved into the script library.
4. Product notes and frequently asked questions are updated.

## 7. MVP Feature Scope

### 7.1 Live Session Management

- Create live session
- Start / stop capture
- View current session status
- Save transcript, screenshots, suggestions, and operator actions

### 7.2 Real-Time Transcript

- Live audio input
- Speech-to-text segmentation
- Speaker text stream
- Keyword extraction
- Summary of the latest 30-120 seconds

### 7.3 Screen Understanding

- Capture frame every 2-5 seconds
- Summarize visible product state
- Detect whether product is being shown, hand is showing scale, certificate is shown, price board is shown, or screen is idle
- Save sampled frames for replay

### 7.4 Jadeite Product Knowledge

Product fields:

- Category
- Name
- Material
- Color
- Water / transparency
- Size
- Weight
- Shape
- Certificate status
- Origin if available
- Flaws and cautions
- Price
- Selling points
- Recommended audience
- Prohibited claims

Initial categories:

- Hand bangle
- Pendant
- Bead string
- Ring face
- Carving
- Ornament

### 7.5 Real-Time Suggestions

Suggestion types:

- Anchor script
- Operator comment
- Customer answer
- Missed explanation reminder
- Risk warning
- Product transition suggestion
- Replay tag

Every suggestion must include:

- Content
- Reason
- Priority
- Risk level
- Target user
- Suggested timing
- Related product
- Source context

### 7.6 Human Review

Operator can:

- Accept
- Edit
- Copy
- Reject
- Mark as used
- Mark as useful
- Mark as inaccurate

No suggestion is executed automatically on third-party live platforms in MVP.

### 7.7 Live Metrics Integration

MVP supports two data input modes:

- Manual metric input for testing
- Screenshot OCR from the merchant's own live data dashboard

Future preferred mode:

- Official platform API or authorized data export

Metrics:

- Online users
- Enter room count
- Comment count
- Like count
- Follow count
- Product exposure
- Product click
- Add to cart
- Order count
- GMV
- Current product

### 7.8 Replay Report

Report sections:

- Live summary
- Product timeline
- Anchor performance
- Missed explanation points
- Effective scripts
- Risky expressions
- Audience questions
- Interaction quality
- Next live recommendations

## 8. Jadeite-Specific AI Agents

### 8.1 Product Explainer Agent

Goal:

- Generate professional but understandable product explanation scripts.

Focus:

- Color
- Water
- Texture
- Shape
- Size
- Craftsmanship
- Wearing scenario
- Price logic

Example output:

```text
This piece can be introduced from color and wearing effect first. Mention that the green is concentrated near the front, and remind viewers that the camera light may make it brighter than indoor natural light.
```

### 8.2 Professional Reminder Agent

Goal:

- Detect missing jadeite-specific explanation points.

Reminder checklist:

- A-grade jadeite statement if verified
- Certificate
- Size / ring size / bangle circle size
- Thickness
- Cracks
- Cotton
- Stone lines
- Color difference under lighting
- Return and after-sales constraints

### 8.3 Audience QA Agent

Goal:

- Help operators answer common audience questions quickly.

Question types:

- Is it natural?
- Does it have certificate?
- Is there crack?
- Is it suitable for daily wear?
- Is this color dark in natural light?
- What wrist size does it fit?
- Can it be cheaper?

### 8.4 Atmosphere Agent

Goal:

- Recommend natural interaction prompts for the operator.

Allowed examples:

- "Want to see natural light, type 1."
- "Want to see hand wearing effect, type 2."
- "Need the certificate close-up, type 3."
- "If you prefer lighter color, tell us in the comments."

This agent must avoid repetitive spam and aggressive pressure.

### 8.5 Transaction Rhythm Agent

Goal:

- Help the anchor decide whether to explain, answer, compare, show detail, or transition.

Signals:

- Long silence
- Repeated explanation
- Online user change
- Product click without order
- High comment density
- Low comment density
- New traffic entering

### 8.6 Compliance Agent

Goal:

- Filter risky claims and rewrite aggressive wording.

Risk phrases:

- Guaranteed appreciation
- Investment guaranteed
- Absolute flawless
- Best in the market
- Cure disease
- Change luck guaranteed
- Fake scarcity
- False discount

Output:

- pass
- rewrite
- block
- explain risk

### 8.7 Replay Agent

Goal:

- Generate post-live analysis and improve future scripts.

Outputs:

- Timeline summary
- Top useful scripts
- Questions not answered well
- Products with weak explanation
- Product categories with high engagement
- Next session script suggestions

## 9. Dashboard Information Architecture

### 9.1 Main Live Dashboard

Recommended layout:

```text
+---------------------------------------------------------------+
| Top bar: Session status / Capture status / AI status / Metrics |
+----------------------+----------------------+-----------------+
| Live Transcript      | Real-Time Suggestions| Product Card    |
|                      |                      |                 |
| Latest speech        | Anchor scripts       | Category        |
| Keywords             | Operator comments    | Size            |
| Summary              | Risk warnings        | Certificate     |
|                      | Missed points        | Flaws           |
+----------------------+----------------------+-----------------+
| Live Metrics Timeline / Comment Trend / Suggestion Log         |
+---------------------------------------------------------------+
```

### 9.2 Suggestion Card

Fields:

- Type
- Priority
- Content
- Reason
- Related context
- Risk level
- Copy button
- Edit button
- Reject button
- Mark as used button

### 9.3 Product Library

Fields:

- Product images
- Category
- Jadeite attributes
- Certificate images
- Price
- Selling points
- Cautions
- Frequently asked questions
- Default scripts

### 9.4 Replay Page

Sections:

- Timeline
- Product performance
- Script performance
- Anchor issues
- Operator issues
- Compliance issues
- Next live checklist

## 10. Technical Stack

### 10.1 Frontend

Recommended:

- Vue 3
- Vite
- TypeScript
- Pinia
- Vue Router
- ECharts
- Naive UI or Element Plus
- WebSocket client

Reason:

- The product is a real-time control dashboard, not an SEO site.
- Vue 3 + Vite is light, fast, and suitable for solo MVP development.
- AI and media processing are better kept in the Python backend.

### 10.2 Backend

Recommended:

- Python
- FastAPI
- WebSocket
- SQLAlchemy or SQLModel
- Pydantic
- Redis
- PostgreSQL
- pgvector

### 10.3 AI and Media Services

Recommended:

- FFmpeg for audio/video capture and frame extraction
- OpenCV for basic frame processing
- STT service for speech-to-text
- Multimodal LLM for frame understanding
- LLM for script generation and agent reasoning
- Lightweight custom orchestrator for MVP
- LangGraph later if workflow state becomes complex

### 10.4 Storage

- PostgreSQL for structured data
- Redis for real-time state and queue
- Local object storage or S3-compatible storage for screenshots and reports
- pgvector for product knowledge and script retrieval

### 10.5 Deployment

MVP local deployment:

- Windows development machine
- FastAPI backend
- Vue frontend
- Local PostgreSQL
- Local Redis
- External AI model API

Future deployment:

- Docker Compose
- Cloud server
- Object storage
- Managed PostgreSQL
- Managed Redis
- Optional GPU worker

## 11. System Architecture

```text
Live Stream / Screen / Mic
        |
        v
Capture Service
        |
        +--> Audio STT Service
        |
        +--> Frame Extraction Service
        |
        +--> Data Dashboard OCR Adapter
        |
        v
Live Context Engine
        |
        v
Agent Orchestrator
        |
        +--> Product Explainer Agent
        +--> Professional Reminder Agent
        +--> Audience QA Agent
        +--> Atmosphere Agent
        +--> Transaction Rhythm Agent
        +--> Compliance Agent
        +--> Replay Agent
        |
        v
Suggestion Center
        |
        v
Web Dashboard
        |
        v
Human Review / Copy / Execute / Feedback
```

## 12. Core Backend Modules

### 12.1 Capture Service

Responsibilities:

- Start and stop capture
- Capture audio stream
- Capture screen region or window
- Extract frame every 2-5 seconds
- Emit capture events

### 12.2 STT Service

Responsibilities:

- Receive audio chunks
- Generate transcript segments
- Detect pauses and repeated speech
- Emit transcript events

### 12.3 Vision Service

Responsibilities:

- Receive frame images
- Generate frame summaries
- Detect certificate, bangle, pendant, bead string, hand wearing effect, price board, and idle screen
- Emit frame summary events

### 12.4 Metrics Adapter

Responsibilities:

- Read live data from manual input, OCR, CSV, or official API
- Normalize live metrics
- Emit metrics events

### 12.5 Context Engine

Responsibilities:

- Merge transcript, frame summary, product data, and live metrics
- Keep latest short context
- Keep session timeline
- Create prompt-ready context blocks

### 12.6 Agent Orchestrator

Responsibilities:

- Decide which agents to run
- Control generation frequency
- Avoid duplicate suggestions
- Send output to compliance check
- Save suggestions

### 12.7 Suggestion Service

Responsibilities:

- Store suggestions
- Update suggestion status
- Push suggestions to frontend by WebSocket
- Record human actions

### 12.8 Replay Service

Responsibilities:

- Generate post-live report
- Extract useful scripts
- Summarize product performance
- Save next-session recommendations

## 13. Data Model Draft

### 13.1 LiveSession

```text
id
title
platform
start_time
end_time
status
operator_name
anchor_name
notes
created_at
updated_at
```

### 13.2 Product

```text
id
name
category
material
color
water
size
weight
shape
certificate
flaws
cautions
price
selling_points
faq
images
created_at
updated_at
```

### 13.3 TranscriptSegment

```text
id
session_id
start_time
end_time
text
confidence
keywords
created_at
```

### 13.4 FrameSnapshot

```text
id
session_id
timestamp
image_url
summary
detected_objects
created_at
```

### 13.5 LiveMetric

```text
id
session_id
timestamp
online_users
enter_count
comment_count
like_count
follow_count
product_views
product_clicks
add_to_cart
orders
gmv
current_product_id
created_at
```

### 13.6 Suggestion

```text
id
session_id
product_id
type
target_role
priority
risk_level
content
reason
source_context
status
operator_feedback
created_at
updated_at
```

### 13.7 ScriptAsset

```text
id
category
scenario
content
tags
effect_score
source_session_id
created_at
updated_at
```

## 14. API Draft

### 14.1 Session APIs

```text
POST /api/sessions
GET /api/sessions
GET /api/sessions/{id}
POST /api/sessions/{id}/start
POST /api/sessions/{id}/stop
```

### 14.2 Product APIs

```text
POST /api/products
GET /api/products
GET /api/products/{id}
PUT /api/products/{id}
DELETE /api/products/{id}
```

### 14.3 Suggestion APIs

```text
GET /api/sessions/{id}/suggestions
POST /api/suggestions/{id}/accept
POST /api/suggestions/{id}/reject
POST /api/suggestions/{id}/used
POST /api/suggestions/{id}/feedback
```

### 14.4 Replay APIs

```text
POST /api/sessions/{id}/replay
GET /api/sessions/{id}/report
```

### 14.5 WebSocket Events

```text
ws://server/ws/sessions/{id}

event: transcript_segment
event: frame_summary
event: live_metric
event: suggestion_created
event: suggestion_updated
event: risk_warning
event: system_status
```

## 15. MVP Development Plan

Hard deadline:

- One-month MVP demo is the bottom-line requirement.
- The first demo must be usable within 4 weeks.
- Any feature that does not directly prove the core loop must be delayed.

Core MVP loop:

```text
Live transcript or simulated transcript
-> current jadeite product card
-> AI suggestions
-> human review feedback
-> simple replay report
```

### Week 1: Foundation, Product Card, and Mock Live Stream

Goals:

- Create project skeleton
- Build Vue dashboard shell
- Build FastAPI backend shell
- Build session management
- Build WebSocket push
- Implement mock transcript stream
- Create jadeite product library schema
- Prepare sample jadeite products and sample transcripts

Deliverable:

- Dashboard can display live session status, current product card, and a mock live transcript stream.

### Week 2: First AI Agents and Suggestion Workflow

Goals:

- Build product CRUD
- Add product card to live dashboard
- Implement first Product Explainer Agent
- Implement first Professional Reminder Agent
- Generate suggestions from transcript and product data
- Add Compliance Agent v0
- Add accept / edit / reject / used workflow

Deliverable:

- Dashboard can recommend anchor scripts and missed-point reminders based on product data and transcript.

### Week 3: STT Prototype, Operator Suggestions, and Replay v0

Goals:

- Implement real or semi-real STT prototype
- Add Atmosphere Agent
- Add Audience QA Agent
- Add simple metrics input
- Add context timeline
- Implement replay report v0

Deliverable:

- System can process a real or recorded live audio source, generate suggestions, and create a simple replay summary.

### Week 4: Demo Hardening and Real Live Trial

Goals:

- Test with recorded jadeite live sessions
- Test with one real or simulated live room
- Tune prompts
- Tune suggestion frequency
- Polish dashboard layout
- Add demo seed data
- Fix blocking bugs
- Prepare demo script

Deliverable:

- JLAO MVP demo can support a complete simulated or real jadeite live session workflow.

### Deferred After One-Month Demo

The following features are valuable but should not block the one-month MVP demo:

- Full screen capture stability
- Frame understanding every 2-5 seconds
- Live data dashboard OCR
- Official live platform API integration
- Multi-phone lightweight agent
- Multi-room management
- Complex LangGraph workflow
- Fine-tuning
- Advanced vector retrieval
- Advanced permission system

## 16. MVP Acceptance Criteria

The one-month MVP demo is considered successful if:

- A simulated or recorded live transcript can drive the dashboard in real time
- At least one real or semi-real STT path is demonstrated
- Product card and transcript can jointly produce jadeite-specific suggestions
- Suggestions are generated within 5-15 seconds of relevant context
- Operator can accept, edit, reject, copy, and mark suggestions as used
- System catches at least 5 common missed jadeite explanation points
- System blocks or rewrites at least 10 obvious risky sales claims
- A basic replay report is generated after the session
- The demo can be shown end-to-end in under 10 minutes

## 17. Key Risks and Mitigations

### 17.1 STT Accuracy

Risk:

- Jadeite terms, accents, and live noise may reduce transcription quality.

Mitigation:

- Build a jadeite term dictionary
- Add custom correction rules
- Use product names and category terms as context

### 17.2 Suggestion Repetition

Risk:

- AI may generate repetitive interaction prompts.

Mitigation:

- Add recent suggestion memory
- Add minimum interval per suggestion type
- Add similarity check before display

### 17.3 Wrong Product Context

Risk:

- AI may recommend scripts for the wrong product.

Mitigation:

- Operator selects current product manually in MVP
- Later use screen recognition and product board OCR

### 17.4 Over-Aggressive Sales Language

Risk:

- Generated scripts may contain risky claims.

Mitigation:

- Compliance Agent must run after all generation
- Risk terms are configurable
- Human review is required

### 17.5 Dashboard Overload

Risk:

- Too many suggestions may distract operators.

Mitigation:

- Priority filtering
- Separate anchor suggestions, operator comments, and risk warnings
- Show only the top 3-5 live suggestions

## 18. Product Metrics

### 18.1 Usage Metrics

- Number of live sessions
- Number of generated suggestions
- Accept rate
- Edit rate
- Reject rate
- Used rate
- Useful feedback rate

### 18.2 Live Optimization Metrics

- Comment density before and after suggestions
- Product click change after explanation reminders
- Add-to-cart change after product scripts
- Repeated question reduction
- Missed explanation count
- Risk warning count

### 18.3 Quality Metrics

- Suggestion relevance score
- Script naturalness score
- Compliance pass rate
- Replay report usefulness score

## 19. Today Start Checklist

Today should not start with complex AI training. Start with product and engineering foundation.

Recommended tasks:

1. Confirm MVP name: Jade Live AI Optimizer, JLAO.
2. Create repository and base folders.
3. Create frontend project with Vue 3 + Vite + TypeScript.
4. Create backend project with FastAPI.
5. Create first database schema draft.
6. Build mock WebSocket transcript stream.
7. Build first live dashboard layout.
8. Prepare 10 sample jadeite products.
9. Prepare 30 sample jadeite live questions.
10. Prepare first role prompts for Product Explainer, Reminder, Atmosphere, QA, and Compliance agents.

## 20. Recommended First Demo

Demo goal:

```text
Select one jadeite product
-> Play or paste a simulated live transcript
-> AI generates anchor suggestions and operator comments
-> Operator accepts or rejects suggestions
-> System creates a simple replay summary
```

This demo proves the core product value before investing in deeper media capture and live platform integration.

## 21. Long-Term Roadmap

### Phase 1: Real-Time AI Co-Pilot

- Real-time transcript
- Product data
- Suggestions
- Human review
- Replay report

### Phase 2: Live Data Intelligence

- Live data dashboard OCR
- Official API integration where available
- Metrics-driven recommendations
- Product performance analysis

### Phase 3: Multi-Room and Team Workflow

- Multi-live-room dashboard
- Team roles
- Permission management
- Multi-operator task assignment
- Script asset library

### Phase 4: Vertical Category Expansion

- Jadeite
- Jewelry
- Tea
- Home customization
- Beauty
- Education consulting

### Phase 5: Intelligent Optimization Engine

- Personalized anchor coaching
- Category-specific script engine
- Conversion stage detection
- Auto-generated training material
- Benchmarking across live sessions
