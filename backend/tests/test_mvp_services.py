import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class WikiServiceTests(unittest.TestCase):
    def test_parse_markdown_chunks_splits_headings_and_searches_text(self) -> None:
        from app.services.wiki_service import parse_markdown_chunks, search_wiki_chunks

        chunks = parse_markdown_chunks(
            "# 平台禁忌与风控词\n"
            "不要承诺保证升值。\n\n"
            "## 售后 FAQ\n"
            "支持复检，退换需要按直播间规则处理。\n"
        )

        self.assertEqual([chunk.heading for chunk in chunks], ["平台禁忌与风控词", "售后 FAQ"])
        hits = search_wiki_chunks(chunks, "复检 售后")
        self.assertEqual(hits[0].heading, "售后 FAQ")


class DatabaseRepositoryTests(unittest.TestCase):
    def test_seed_products_persists_products_to_configured_database(self) -> None:
        from app.db import configure_database, init_db
        from app.repositories import list_products, seed_products
        from app.schemas import Product

        configure_database("sqlite:///:memory:")
        init_db()

        seed_products(
            [
                Product(
                    id="p-test-001",
                    name="测试手镯",
                    category="手镯",
                    material="天然翡翠",
                    color="晴水",
                    water="糯冰",
                )
            ]
        )

        products = list_products()
        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].name, "测试手镯")


class VirtualCustomerTests(unittest.TestCase):
    def test_generate_customer_events_alerts_for_high_value_matching_customer(self) -> None:
        from app.schemas import Product, VirtualCustomer
        from app.services.virtual_customer_service import generate_customer_events

        product = Product(
            id="p-bangle",
            name="晴水手镯",
            category="手镯",
            material="天然翡翠",
            color="晴水",
            water="糯冰",
        )
        customers = [
            VirtualCustomer(
                id="vc-001",
                nickname="老客阿青",
                level="高价值",
                personality="稳重",
                preferred_colors=["晴水"],
                preferred_categories=["手镯"],
                budget_range="8000-15000",
                common_questions=["能看自然光吗？"],
                purchased_items=["冰飘花手镯"],
                purchased_amount=26800,
                relationship_strategy="老客进房先欢迎，再提醒主播展示自然光。",
                activity_level=0.9,
            )
        ]

        events = generate_customer_events(
            session_id="live-001",
            customers=customers,
            product=product,
            transcript_text="主播正在讲这只晴水手镯，可以看自然光",
        )

        self.assertTrue(any(event.event_type == "高价值进房" for event in events))
        self.assertTrue(any(event.customer_id == "vc-001" for event in events))


class MultiAgentTests(unittest.TestCase):
    def test_generate_agent_utterances_returns_five_roles_and_blocks_high_risk(self) -> None:
        from app.schemas import Product, WikiChunk
        from app.services.multi_agent_service import generate_agent_utterances

        product = Product(
            id="p-egg",
            name="阳绿蛋面",
            category="蛋面",
            material="天然翡翠",
            color="阳绿",
            water="冰糯",
            selling_points=["颜色亮"],
        )
        wiki_hits = [
            WikiChunk(
                id="wiki-001",
                source_path="wiki.md",
                heading="平台禁忌与风控词",
                content="不要说保证升值、稳赚不赔、绝对最低。",
                tags=["风控"],
            )
        ]

        utterances = generate_agent_utterances(
            session_id="live-001",
            product=product,
            transcript_text="这件阳绿蛋面不要说保证升值",
            wiki_hits=wiki_hits,
            customer_events=[],
        )

        roles = {utterance.agent_role for utterance in utterances}
        self.assertEqual(roles, {"气氛组", "商品专家", "客户关系", "风控", "成交转化"})
        risk_utterance = next(item for item in utterances if item.agent_role == "风控")
        self.assertEqual(risk_utterance.send_mode, "blocked")

    def test_generate_agent_utterances_are_marked_as_virtual_sandbox_only(self) -> None:
        from app.services.multi_agent_service import generate_agent_utterances

        utterances = generate_agent_utterances(
            session_id="live-001",
            product=None,
            transcript_text="这件翡翠想看自然光",
            wiki_hits=[],
            customer_events=[],
        )

        self.assertTrue(utterances)
        self.assertTrue(all("仅模拟，不发送" in item.target for item in utterances))


class VirtualReplyTests(unittest.TestCase):
    def test_price_question_generates_virtual_reply_that_is_not_sent(self) -> None:
        from datetime import datetime

        from app.schemas import Product, TranscriptSegment
        from app.services.agent_service import generate_suggestions

        product = Product(
            id="p-egg",
            name="阳绿蛋面",
            category="蛋面",
            material="天然翡翠",
            color="阳绿",
            water="冰糯",
        )
        transcripts = [
            TranscriptSegment(
                id="seg-001",
                session_id="live-001",
                index=1,
                text="这个价格多少",
                created_at=datetime.utcnow(),
            )
        ]

        suggestions = generate_suggestions("live-001", product, transcripts)
        reply = next(item for item in suggestions if item.type == "用户问题模拟回复")

        self.assertEqual(reply.target_role, "虚拟场控")
        self.assertIn("仅模拟，不发送", reply.content)

    def test_price_question_is_kept_when_risk_and_detail_signals_compete(self) -> None:
        from datetime import datetime

        from app.schemas import Product, TranscriptSegment
        from app.services.agent_service import generate_suggestions

        product = Product(
            id="p-egg",
            name="阳绿蛋面",
            category="蛋面",
            material="天然翡翠",
            color="阳绿",
            water="冰糯",
            certificate="GIA-TEST",
        )
        transcripts = [
            TranscriptSegment(
                id="seg-001",
                session_id="live-001",
                index=1,
                text="这个价格多少，有证书吗，主播说肯定升值",
                created_at=datetime.utcnow(),
            )
        ]

        suggestions = generate_suggestions("live-001", product, transcripts)

        self.assertIn("用户问题模拟回复", {item.type for item in suggestions})

    def test_price_question_is_kept_when_product_context_adds_two_speaker_suggestions(self) -> None:
        from datetime import datetime

        from app.schemas import Product, TranscriptSegment
        from app.services.agent_service import generate_suggestions

        product = Product(
            id="p-bangle",
            name="冰种翡翠手镯",
            category="手镯",
            material="天然翡翠",
            color="晴水",
            water="冰种",
            certificate="NGTC-TEST",
            flaws="轻微棉线",
            selling_points=["冰透水润"],
        )
        transcripts = [
            TranscriptSegment(
                id="seg-001",
                session_id="live-001",
                index=1,
                text="这个冰种翡翠价格多少？有没有证书？自然光看看，上手效果，稳赚不赔",
                created_at=datetime.utcnow(),
            )
        ]

        suggestions = generate_suggestions("live-001", product, transcripts)

        self.assertIn("用户问题模拟回复", {item.type for item in suggestions})


class ObservationReportTests(unittest.TestCase):
    def test_build_report_uses_public_live_observation_language(self) -> None:
        from datetime import datetime

        from app.schemas import Suggestion, TranscriptSegment
        from app.services.replay_service import build_replay_report

        transcripts = [
            TranscriptSegment(
                id="seg-001",
                session_id="live-001",
                index=1,
                text="这件有证书吗，价格多少",
                created_at=datetime.utcnow(),
            )
        ]
        suggestions = [
            Suggestion(
                id="sug-001",
                session_id="live-001",
                type="用户问题模拟回复",
                target_role="虚拟场控",
                priority=2,
                risk_level="低",
                content="【仅模拟，不发送】可以先讲品质依据，再说价格。",
                reason="公开视频号直播观察。",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        ]

        report = build_replay_report("live-001", transcripts, suggestions)

        self.assertIn("公开视频号翡翠直播观察报告", report.summary)
        self.assertTrue(any("训练样本" in item for item in report.next_suggestions))


if __name__ == "__main__":
    unittest.main()
