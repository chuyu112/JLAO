import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.schemas import (
    AgentProfile,
    FrameSnapshot,
    LiveSession,
    Product,
    ReplayReport,
    Suggestion,
    TranscriptSegment,
    VirtualCustomer,
    VirtualCustomerEvent,
)


WORKSPACE_DIR = Path(__file__).resolve().parents[2]
SAMPLES_DIR = WORKSPACE_DIR / "data" / "samples"
LEGACY_SAMPLE_PRODUCT_IDS = {
    "p-egg-001",
    "p-pendant-001",
    "p-beads-001",
    "p-idle-001",
    "p-idle-002",
}


class AppState:
    def __init__(self) -> None:
        self.products: dict[str, Product] = {}
        self.sessions: dict[str, LiveSession] = {}
        self.transcripts: dict[str, list[TranscriptSegment]] = {}
        self.suggestions: dict[str, list[Suggestion]] = {}
        self.reports: dict[str, ReplayReport] = {}
        self.frames: dict[str, list[FrameSnapshot]] = {}
        self.live_comments: dict[str, list[VirtualCustomerEvent]] = {}
        self.live_comment_ocr_status: dict[str, dict[str, Any]] = {}

    def load_seed_data(self) -> None:
        from app.db import init_db
        from app.repositories import delete_product, hydrate_state, seed_agent_profiles, seed_products, seed_virtual_customers
        from app.services.wiki_service import reload_wiki_chunks

        init_db()

        for product_id in LEGACY_SAMPLE_PRODUCT_IDS:
            delete_product(product_id)

        product_path = SAMPLES_DIR / "products.json"
        if product_path.exists():
            seed_products([Product(**item) for item in json.loads(product_path.read_text(encoding="utf-8-sig"))])

        customer_path = SAMPLES_DIR / "virtual_customers.json"
        if customer_path.exists():
            seed_virtual_customers(
                [VirtualCustomer(**item) for item in json.loads(customer_path.read_text(encoding="utf-8-sig"))]
            )

        agent_path = SAMPLES_DIR / "agents.json"
        if agent_path.exists():
            seed_agent_profiles([AgentProfile(**item) for item in json.loads(agent_path.read_text(encoding="utf-8-sig"))])

        hydrate_state(self)
        reload_wiki_chunks()

    def new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:12]}"


app_state = AppState()
