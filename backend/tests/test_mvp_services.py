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


class LocalSttServiceTests(unittest.TestCase):
    def test_funasr_alias_prefers_local_modelscope_cache(self) -> None:
        import os
        import tempfile

        from app.services.local_stt_service import _resolve_funasr_model

        old_cache = os.environ.get("MODELSCOPE_CACHE")
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                model_dir = (
                    Path(temp_dir)
                    / "models"
                    / "iic"
                    / "speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-online"
                )
                model_dir.mkdir(parents=True)
                os.environ["MODELSCOPE_CACHE"] = temp_dir

                self.assertEqual(Path(_resolve_funasr_model("paraformer-zh-streaming")), model_dir)
        finally:
            if old_cache is None:
                os.environ.pop("MODELSCOPE_CACHE", None)
            else:
                os.environ["MODELSCOPE_CACHE"] = old_cache

    def test_funasr_streaming_text_merges_incremental_chunks(self) -> None:
        from app.services.local_stt_service import _merge_funasr_text

        self.assertEqual(_merge_funasr_text("", "欢迎大家"), "欢迎大家")
        self.assertEqual(_merge_funasr_text("欢迎大家", "来体验"), "欢迎大家来体验")
        self.assertEqual(_merge_funasr_text("欢迎大家来体验", "大家来体验"), "欢迎大家来体验")
        self.assertEqual(_merge_funasr_text("欢迎大家", "欢迎大家来体验"), "欢迎大家来体验")


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

    def test_init_db_adds_product_status_to_existing_database(self) -> None:
        from sqlalchemy import text

        from app.db import configure_database, get_engine, init_db
        from app.repositories import list_products

        configure_database("sqlite:///:memory:")
        with get_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE products (
                        id VARCHAR(64) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        category VARCHAR(100) NOT NULL,
                        material VARCHAR(100),
                        color VARCHAR(100),
                        water VARCHAR(100),
                        size VARCHAR(255),
                        weight VARCHAR(100),
                        certificate VARCHAR(255),
                        flaws TEXT,
                        cautions TEXT,
                        price FLOAT,
                        selling_points JSON,
                        faq JSON,
                        recommended_scripts JSON
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO products (
                        id, name, category, material, color, water, selling_points, faq, recommended_scripts
                    )
                    VALUES (
                        'legacy-001', '旧库商品', '手镯', '天然翡翠', '晴水', '糯冰', '[]', '[]', '[]'
                    )
                    """
                )
            )

        init_db()

        products = list_products()
        self.assertEqual(products[0].status, "在售")


class JadeMultimodalServiceTests(unittest.TestCase):
    def test_text_analysis_extracts_jade_color_water_style_size_and_price(self) -> None:
        from app.services.jade_multimodal_service import analyze_jade_text

        result = analyze_jade_text("这条蓝水珠串是糯冰种，单珠约 8mm，18 颗，报价 5600")

        self.assertEqual(result.color, "蓝水")
        self.assertEqual(result.water, "糯冰")
        self.assertEqual(result.style, "珠串")
        self.assertIn("8mm", result.size)
        self.assertIn("18 颗", result.size)
        self.assertEqual(result.price, 5600)
        self.assertGreaterEqual(result.confidence, 0.7)

    def test_text_analysis_extracts_theme_when_product_is_carving(self) -> None:
        from app.services.jade_multimodal_service import analyze_jade_text

        result = analyze_jade_text("这件白冰冰种观音，高 45mm，宽 28mm，题材吉祥")

        self.assertEqual(result.color, "白冰")
        self.assertEqual(result.water, "冰种")
        self.assertEqual(result.theme, "观音")
        self.assertIn("高 45mm", result.size)

    def test_merge_analysis_combines_image_color_and_speech_attributes(self) -> None:
        from app.services.jade_multimodal_service import JadeAnalysis, analyze_jade_text, merge_jade_analysis

        image = JadeAnalysis(color="阳绿", style="手镯", evidence_image_paths=["frame.jpg"], detections=[{"label": "jade_bangle", "confidence": 0.82}])
        text = analyze_jade_text("冰糯蛋面，8.5mm x 6.2mm，适合做戒指")
        merged = merge_jade_analysis(image, text)

        self.assertEqual(merged.color, "阳绿")
        self.assertEqual(merged.water, "冰糯")
        self.assertEqual(merged.style, "手镯")
        self.assertIn("frame.jpg", merged.evidence_image_paths)
        self.assertEqual(merged.detections[0]["label"], "jade_bangle")
        self.assertTrue(merged.evidence_texts)

    def test_live_context_merges_current_frame_with_recent_anchor_transcripts(self) -> None:
        from datetime import datetime, timezone

        from app.schemas import TranscriptSegment
        from app.services.jade_multimodal_service import JadeAnalysis, analyze_live_jade_context
        from app.state import app_state

        session_id = "live-context-jade"
        app_state.transcripts[session_id] = [
            TranscriptSegment(
                id="seg-context-001",
                session_id=session_id,
                index=1,
                text="这件是冰种观音，高 45mm，宽 28mm",
                keywords=[],
                created_at=datetime.now(timezone.utc),
            )
        ]

        try:
            result = analyze_live_jade_context(
                session_id,
                image_analysis=JadeAnalysis(color="白冰", evidence_image_paths=["frame-context.jpg"]),
            )
        finally:
            app_state.transcripts.pop(session_id, None)

        self.assertEqual(result.color, "白冰")
        self.assertEqual(result.water, "冰种")
        self.assertEqual(result.theme, "观音")
        self.assertIn("45mm", result.size)
        self.assertIn("frame-context.jpg", result.evidence_image_paths)
        self.assertIn("这件是冰种观音", result.evidence_texts[0])
        self.assertEqual(result.signals["source"], "live-context")
        self.assertEqual(result.signals["recent_transcript_ids"], ["seg-context-001"])

    def test_yolo_label_mapping_extracts_jade_style_and_theme(self) -> None:
        from app.services.jade_yolo_service import jade_attributes_from_yolo_label

        self.assertEqual(jade_attributes_from_yolo_label("jade_bangle"), ("手镯", ""))
        self.assertEqual(jade_attributes_from_yolo_label("guanyin_pendant"), ("吊坠", "观音"))
        self.assertEqual(jade_attributes_from_yolo_label("guanyin"), ("", "观音"))

    def test_image_analysis_runs_without_configured_yolo_model(self) -> None:
        import os
        import tempfile

        import cv2
        import numpy as np

        from app.services.jade_multimodal_service import analyze_jade_image

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        old_yolo_model = os.environ.get("JLAO_YOLO_MODEL")
        try:
            os.environ["JLAO_YOLO_MODEL"] = str(temp_path.with_suffix(".missing.pt"))
            image = np.full((80, 80, 3), (180, 160, 60), dtype=np.uint8)
            cv2.imwrite(str(temp_path), image)

            result = analyze_jade_image(temp_path)

            self.assertIn("yolo", result.signals)
            self.assertFalse(result.signals["yolo"]["enabled"])
            self.assertEqual(result.signals["yolo"]["reason"], "model-not-configured")
        finally:
            if old_yolo_model is None:
                os.environ.pop("JLAO_YOLO_MODEL", None)
            else:
                os.environ["JLAO_YOLO_MODEL"] = old_yolo_model
            temp_path.unlink(missing_ok=True)

    def test_image_analysis_estimates_water_from_clear_jade_like_frame(self) -> None:
        import tempfile

        import cv2
        import numpy as np

        from app.services.jade_multimodal_service import analyze_jade_image

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            image = np.full((120, 120, 3), (180, 215, 175), dtype=np.uint8)
            cv2.circle(image, (60, 60), 38, (150, 230, 145), -1)
            cv2.GaussianBlur(image, (17, 17), 0, dst=image)
            cv2.imwrite(str(temp_path), image)

            result = analyze_jade_image(temp_path)

            self.assertIn(result.water, {"高冰", "冰种", "糯冰"})
            self.assertIn("water_features", result.signals)
            self.assertGreater(result.signals["water_features"]["clarity_score"], 0.45)
            self.assertTrue(result.color)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_image_analysis_estimates_lower_water_from_noisy_jade_like_frame(self) -> None:
        import tempfile

        import cv2
        import numpy as np

        from app.services.jade_multimodal_service import analyze_jade_image

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            rng = np.random.default_rng(7)
            image = np.full((120, 120, 3), (70, 130, 80), dtype=np.uint8)
            noise = rng.integers(0, 95, size=image.shape, dtype=np.uint8)
            image = cv2.add(image, noise)
            cv2.imwrite(str(temp_path), image)

            result = analyze_jade_image(temp_path)

            self.assertIn(result.water, {"糯冰", "糯种", "豆种"})
            self.assertIn("water_features", result.signals)
            self.assertGreater(result.signals["water_features"]["texture"], 100)
            self.assertTrue(result.color)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_yolo_runtime_status_reports_model_and_package_readiness(self) -> None:
        import tempfile

        from app.services.jade_yolo_service import get_yolo_runtime_status

        with tempfile.TemporaryDirectory() as temp_dir:
            missing_model = Path(temp_dir) / "missing-jade-yolo.pt"

            status = get_yolo_runtime_status(missing_model)

        self.assertFalse(status["enabled"])
        self.assertEqual(status["reason"], "model-not-configured")
        self.assertEqual(status["resolved_model_path"], "")
        self.assertIn("package_available", status)

    def test_analysis_upserts_live_product_record_with_evidence(self) -> None:
        import asyncio

        from app.db import configure_database, init_db
        from app.repositories import list_products
        from app.services.jade_multimodal_service import analyze_jade_text, upsert_live_jade_product
        from app.state import app_state

        configure_database("sqlite:///:memory:")
        init_db()
        app_state.products.clear()

        first = analyze_jade_text("这条蓝水珠串是糯冰种，单珠约 8mm，18 颗，报价 5600")
        product = asyncio.run(upsert_live_jade_product("live-jade-upsert", first))

        self.assertIsNotNone(product)
        self.assertEqual(product.color, "蓝水")
        self.assertEqual(product.water, "糯冰")
        self.assertEqual(product.style, "珠串")
        self.assertIn("8mm", product.size)
        self.assertEqual(product.price, 5600)

        second = analyze_jade_text("蓝水珠串颜色统一，珠形规整")
        updated = asyncio.run(upsert_live_jade_product("live-jade-upsert", second))
        products = list_products()

        self.assertEqual(updated.id, product.id)
        self.assertEqual(len(products), 1)
        self.assertGreaterEqual(len(products[0].evidence_texts), 2)


class CaptureArchiveRepositoryTests(unittest.TestCase):
    def test_capture_archive_records_video_image_and_text_metadata(self) -> None:
        from app.db import configure_database, init_db
        from app.repositories import list_capture_archives, save_capture_archive
        from app.schemas import CaptureArchiveItem

        configure_database("sqlite:///:memory:")
        init_db()

        save_capture_archive(
            CaptureArchiveItem(
                id="arch-video-001",
                session_id="live-archive",
                artifact_type="video",
                source="scrcpy-record",
                path="/uploads/recordings/live-archive/screen.mp4",
                content="",
                metadata={"format": "mp4"},
            )
        )
        save_capture_archive(
            CaptureArchiveItem(
                id="arch-image-001",
                session_id="live-archive",
                artifact_type="image",
                source="phone-capture",
                path="/uploads/frames/live-archive/frame.jpg",
                content="",
                metadata={"sharpness_score": 100},
            )
        )
        save_capture_archive(
            CaptureArchiveItem(
                id="arch-text-001",
                session_id="live-archive",
                artifact_type="text",
                source="live-comment",
                path="",
                content="扣头多大？",
                metadata={"event_type": "弹幕"},
            )
        )

        archives = list_capture_archives("live-archive")

        self.assertEqual([item.artifact_type for item in archives], ["text", "image", "video"])
        self.assertEqual(archives[0].content, "扣头多大？")

    def test_live_session_persists_detected_live_room_name(self) -> None:
        from datetime import datetime, timezone

        from app.db import configure_database, init_db
        from app.repositories import list_live_sessions, save_live_session
        from app.schemas import LiveSession

        configure_database("sqlite:///:memory:")
        init_db()

        now = datetime.now(timezone.utc)
        save_live_session(
            LiveSession(
                id="live-room-name",
                title="JLAO",
                platform="video-account",
                live_room_name="Room A",
                created_at=now,
                updated_at=now,
            )
        )

        sessions = list_live_sessions()

        self.assertEqual(sessions[0].live_room_name, "Room A")


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
        from datetime import datetime, timezone

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
                created_at=datetime.now(timezone.utc),
            )
        ]

        suggestions = generate_suggestions("live-001", product, transcripts)
        reply = next(item for item in suggestions if item.type == "用户问题模拟回复")

        self.assertEqual(reply.target_role, "虚拟场控")
        self.assertIn("仅模拟，不发送", reply.content)

    def test_price_question_is_kept_when_risk_and_detail_signals_compete(self) -> None:
        from datetime import datetime, timezone

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
                created_at=datetime.now(timezone.utc),
            )
        ]

        suggestions = generate_suggestions("live-001", product, transcripts)

        self.assertIn("用户问题模拟回复", {item.type for item in suggestions})

    def test_price_question_is_kept_when_product_context_adds_two_speaker_suggestions(self) -> None:
        from datetime import datetime, timezone

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
                created_at=datetime.now(timezone.utc),
            )
        ]

        suggestions = generate_suggestions("live-001", product, transcripts)

        self.assertIn("用户问题模拟回复", {item.type for item in suggestions})


class ObservationReportTests(unittest.TestCase):
    def test_build_report_uses_public_live_observation_language(self) -> None:
        from datetime import datetime, timezone

        from app.schemas import Suggestion, TranscriptSegment
        from app.services.replay_service import build_replay_report

        transcripts = [
            TranscriptSegment(
                id="seg-001",
                session_id="live-001",
                index=1,
                text="这件有证书吗，价格多少",
                created_at=datetime.now(timezone.utc),
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
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        ]

        report = build_replay_report("live-001", transcripts, suggestions)

        self.assertIn("公开视频号翡翠直播观察报告", report.summary)
        self.assertTrue(any("训练样本" in item for item in report.next_suggestions))


class SttWebsocketTests(unittest.TestCase):
    def test_disconnect_runtime_error_is_treated_as_normal_close(self) -> None:
        from app.ws.stt_ws import _is_expected_disconnect_error

        error = RuntimeError('Cannot call "receive" once a disconnect message has been received.')

        self.assertTrue(_is_expected_disconnect_error(error))


class ScrcpyCommandTests(unittest.TestCase):
    def test_projection_scrcpy_is_video_only(self) -> None:
        from unittest.mock import patch

        from app.services.scrcpy_service import _build_scrcpy_command

        with (
            patch("app.services.scrcpy_service._get_qtscrcpy_exe", return_value=None),
            patch("app.services.scrcpy_service._get_scrcpy_exe", return_value=r"D:\scrcpy-win64-v3.3.4\scrcpy.exe"),
        ):
            launch = _build_scrcpy_command(serial="", max_size=1024, bit_rate=4_000_000)

        self.assertIn("--no-audio", launch.command)
        self.assertNotIn("--audio-source=playback", launch.command)
        self.assertNotIn("--audio-source=mic", launch.command)
        self.assertNotIn("--audio-source=voice-performance", launch.command)

    def test_projection_scrcpy_does_not_force_window_position_by_default(self) -> None:
        import os
        from unittest.mock import patch

        from app.services.scrcpy_service import _build_scrcpy_command

        old_values = {name: os.environ.get(name) for name in (
            "JLAO_SCRCPY_WINDOW_X",
            "JLAO_SCRCPY_WINDOW_Y",
            "JLAO_SCRCPY_WINDOW_WIDTH",
            "JLAO_SCRCPY_WINDOW_HEIGHT",
        )}
        try:
            for name in old_values:
                os.environ.pop(name, None)
            with (
                patch("app.services.scrcpy_service._get_qtscrcpy_exe", return_value=None),
                patch("app.services.scrcpy_service._get_scrcpy_exe", return_value=r"D:\scrcpy-win64-v4.0\scrcpy.exe"),
            ):
                launch = _build_scrcpy_command(serial="", max_size=1024, bit_rate=4_000_000)
        finally:
            for name, value in old_values.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

        self.assertNotIn("--window-x", launch.command)
        self.assertNotIn("--window-y", launch.command)

    def test_projection_scrcpy_window_position_is_configurable(self) -> None:
        import os
        from unittest.mock import patch

        from app.services.scrcpy_service import _build_scrcpy_command

        old_values = {name: os.environ.get(name) for name in (
            "JLAO_SCRCPY_WINDOW_X",
            "JLAO_SCRCPY_WINDOW_Y",
            "JLAO_SCRCPY_WINDOW_WIDTH",
            "JLAO_SCRCPY_WINDOW_HEIGHT",
        )}
        try:
            os.environ["JLAO_SCRCPY_WINDOW_X"] = "120"
            os.environ["JLAO_SCRCPY_WINDOW_Y"] = "80"
            os.environ["JLAO_SCRCPY_WINDOW_WIDTH"] = "720"
            os.environ["JLAO_SCRCPY_WINDOW_HEIGHT"] = "1280"
            with (
                patch("app.services.scrcpy_service._get_qtscrcpy_exe", return_value=None),
                patch("app.services.scrcpy_service._get_scrcpy_exe", return_value=r"D:\scrcpy-win64-v4.0\scrcpy.exe"),
            ):
                launch = _build_scrcpy_command(serial="", max_size=1024, bit_rate=4_000_000)
        finally:
            for name, value in old_values.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

        self.assertIn("--window-x", launch.command)
        self.assertIn("120", launch.command)
        self.assertIn("--window-y", launch.command)
        self.assertIn("80", launch.command)
        self.assertIn("--window-width", launch.command)
        self.assertIn("720", launch.command)
        self.assertIn("--window-height", launch.command)
        self.assertIn("1280", launch.command)

    def test_command_line_scrcpy_is_preferred_when_both_drivers_exist(self) -> None:
        from unittest.mock import patch

        from app.services.scrcpy_service import _build_scrcpy_command

        scrcpy_exe = r"D:\scrcpy-win64-v4.0\scrcpy.exe"
        qtscrcpy_exe = r"D:\QtScrcpy-win-x64-v3.3.3\QtScrcpy.exe"

        with (
            patch("app.services.scrcpy_service._get_scrcpy_exe", return_value=scrcpy_exe),
            patch("app.services.scrcpy_service._get_qtscrcpy_exe", return_value=qtscrcpy_exe),
        ):
            launch = _build_scrcpy_command(serial="", max_size=1024, bit_rate=4_000_000)

        self.assertEqual("scrcpy", launch.mode)
        self.assertEqual(scrcpy_exe, launch.command[0])

    def test_command_line_scrcpy_does_not_record_projection(self) -> None:
        from unittest.mock import patch

        from app.services.scrcpy_service import _build_scrcpy_command

        with (
            patch("app.services.scrcpy_service._get_scrcpy_exe", return_value=r"D:\scrcpy-win64-v4.0\scrcpy.exe"),
            patch("app.services.scrcpy_service._get_qtscrcpy_exe", return_value=None),
        ):
            launch = _build_scrcpy_command(serial="", max_size=1024, bit_rate=4_000_000)

        self.assertNotIn("--record", launch.command)
        self.assertNotIn("--record-format", launch.command)

    def test_user_selected_qtscrcpy_directory_resolves_to_executable(self) -> None:
        import tempfile
        from pathlib import Path

        from app.services.scrcpy_service import _build_scrcpy_command, set_scrcpy_path

        with tempfile.TemporaryDirectory() as temp_dir:
            driver_dir = Path(temp_dir) / "QtScrcpy-win-x64"
            driver_dir.mkdir()
            qtscrcpy_exe = driver_dir / "QtScrcpy.exe"
            qtscrcpy_exe.write_bytes(b"")

            try:
                set_scrcpy_path(str(driver_dir))
                launch = _build_scrcpy_command(serial="", max_size=1024, bit_rate=4_000_000)
            finally:
                set_scrcpy_path(None)

        self.assertEqual(launch.command[0], str(qtscrcpy_exe))
        self.assertEqual(launch.cwd, str(driver_dir))

    def test_invalid_user_scrcpy_path_is_rejected(self) -> None:
        import tempfile
        from pathlib import Path

        from app.services.scrcpy_service import set_scrcpy_path

        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing-scrcpy.exe"
            with self.assertRaises(FileNotFoundError):
                set_scrcpy_path(str(missing))

    def test_drive_root_scan_finds_scrcpy_bundles_one_level_down(self) -> None:
        import tempfile
        from pathlib import Path

        from app.services.scrcpy_service import _scan_drive_root_scrcpy_candidates

        with tempfile.TemporaryDirectory() as temp_dir:
            scrcpy_dir = Path(temp_dir) / "scrcpy-win64-v4.0"
            qtscrcpy_dir = Path(temp_dir) / "QtScrcpy-win-x64"
            scrcpy_dir.mkdir()
            qtscrcpy_dir.mkdir()
            scrcpy_exe = scrcpy_dir / "scrcpy.exe"
            qtscrcpy_exe = qtscrcpy_dir / "QtScrcpy.exe"
            scrcpy_exe.write_bytes(b"")
            qtscrcpy_exe.write_bytes(b"")

            candidates = _scan_drive_root_scrcpy_candidates(temp_dir)

        self.assertIn(str(scrcpy_exe), candidates["scrcpy"])
        self.assertIn(str(qtscrcpy_exe), candidates["qtscrcpy"])

    def test_projection_adb_devices_output_is_parsed(self) -> None:
        from app.services.scrcpy_service import _parse_adb_devices_output

        devices = _parse_adb_devices_output(
            "List of devices attached\n"
            "abc123\tdevice\n"
            "xyz987\toffline\n"
        )

        self.assertEqual(devices[0]["serial"], "abc123")
        self.assertEqual(devices[0]["state"], "device")
        self.assertEqual(devices[1]["state"], "offline")

    def test_projection_start_requires_online_adb_device(self) -> None:
        import asyncio
        from unittest.mock import AsyncMock, patch

        from app.services.scrcpy_service import _ensure_adb_device_online

        with (
            patch("app.services.scrcpy_service._adb_exe_for_projection", return_value="adb"),
            patch("app.services.scrcpy_service._adb_devices", new=AsyncMock(return_value=[])),
        ):
            with self.assertRaisesRegex(RuntimeError, "ADB 设备未在线"):
                asyncio.run(_ensure_adb_device_online(""))

    def test_scrcpy_status_includes_resource_state(self) -> None:
        from app.services.scrcpy_service import status

        self.assertEqual(status("missing-session")["state"], "stopped")

    def test_project_scrcpy_process_markers_are_distinguished_from_external_windows(self) -> None:
        from app.services.scrcpy_service import _is_project_scrcpy_command_line

        self.assertTrue(_is_project_scrcpy_command_line('scrcpy.exe --window-title "JLAO Projection - default-device"'))
        self.assertTrue(_is_project_scrcpy_command_line('scrcpy.exe --no-video --record-format wav --record stream.wav'))
        self.assertFalse(_is_project_scrcpy_command_line('scrcpy.exe --max-fps 30'))


class NativeSttServiceTests(unittest.TestCase):
    def test_audio_record_command_uses_playback_source(self) -> None:
        from pathlib import Path

        from app.services.native_stt_service import _build_audio_record_command

        command = _build_audio_record_command(
            scrcpy_exe=r"D:\scrcpy-win64-v3.3.4\scrcpy.exe",
            serial="",
            output_path=Path("chunk.wav"),
            chunk_seconds=3,
        )

        self.assertIn("--audio-source=playback", command)
        self.assertIn("--no-audio-playback", command)
        self.assertNotIn("--time-limit", command)
        self.assertNotIn("--audio-dup", command)
        self.assertNotIn("--audio-source=mic", command)
        self.assertNotIn("--audio-source=output", command)
        self.assertNotIn("--audio-source=voice-performance", command)

    def test_native_stt_status_includes_resource_state(self) -> None:
        from app.services.native_stt_service import status

        self.assertEqual(status("missing-session")["state"], "stopped")

    def test_adb_devices_output_is_parsed(self) -> None:
        from app.services.native_audio_service import _parse_adb_devices_output

        devices = _parse_adb_devices_output(
            "List of devices attached\n"
            "abc123\tdevice\n"
            "xyz987\toffline\n"
        )

        self.assertEqual(devices[0]["serial"], "abc123")
        self.assertEqual(devices[0]["state"], "device")
        self.assertEqual(devices[1]["state"], "offline")

    def test_scrcpy_device_disconnected_error_is_recoverable(self) -> None:
        from app.services.native_stt_service import _is_device_disconnected_error, _is_scrcpy_recoverable_error

        self.assertTrue(_is_device_disconnected_error("WARN: Device disconnected"))
        self.assertTrue(_is_device_disconnected_error("3AF9K24227080668\toffline"))
        self.assertTrue(_is_device_disconnected_error("adb: device offline"))
        self.assertFalse(_is_device_disconnected_error("No streams to mux were specified"))
        self.assertTrue(_is_scrcpy_recoverable_error("Aborted\nERROR: Server connection failed"))

    def test_adb_exe_is_resolved_next_to_scrcpy(self) -> None:
        from app.services.native_stt_service import _adb_exe_for_scrcpy

        self.assertEqual(
            _adb_exe_for_scrcpy(r"D:\scrcpy-win64-v4.0\scrcpy.exe"),
            r"D:\scrcpy-win64-v4.0\adb.exe",
        )

    def test_startup_adb_recover_can_skip_waiting_for_device(self) -> None:
        import inspect

        from app.services.native_stt_service import _recover_adb_device

        signature = inspect.signature(_recover_adb_device)

        self.assertIn("wait_for_device", signature.parameters)
        self.assertTrue(signature.parameters["wait_for_device"].default)

    def test_streaming_wav_data_offset_is_detected_from_scrcpy_header(self) -> None:
        from app.services.native_stt_service import _find_wav_data_offset

        header = (
            b"RIFF\xff\xff\xff\xffWAVEfmt \x10\x00\x00\x00\x01\x00\x02\x00"
            b"\x80\xbb\x00\x00\x00\xee\x02\x00\x04\x00\x10\x00"
            b"LIST\x04\x00\x00\x00testdata\xff\xff\xff\xff"
        )

        self.assertEqual(_find_wav_data_offset(header), len(header))

    def test_default_serial_native_stt_tasks_share_one_device_slot(self) -> None:
        from types import SimpleNamespace

        from app.services.native_stt_service import _sessions_for_native_stt_device, native_stt_tasks

        existing = dict(native_stt_tasks)
        try:
            native_stt_tasks.clear()
            native_stt_tasks["old-default"] = SimpleNamespace(serial="")
            native_stt_tasks["explicit"] = SimpleNamespace(serial="ABC123")

            self.assertEqual(_sessions_for_native_stt_device(""), ["old-default"])
            self.assertEqual(_sessions_for_native_stt_device("ABC123"), ["explicit"])
        finally:
            native_stt_tasks.clear()
            native_stt_tasks.update(existing)

    def test_wav_to_pcm16_mono_16k_downmixes_and_resamples(self) -> None:
        import struct
        import tempfile
        import wave

        from app.services.native_stt_service import _wav_to_pcm16_mono_16k

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(2)
                wav_file.setsampwidth(2)
                wav_file.setframerate(48000)
                frame = struct.pack("<hh", 1200, -1200)
                wav_file.writeframes(frame * 48000)

            pcm = _wav_to_pcm16_mono_16k(temp_path)

            self.assertEqual(len(pcm), 16000 * 2)
        finally:
            Path(temp_path).unlink(missing_ok=True)


class RuntimeSettingsTests(unittest.TestCase):
    def test_stt_runtime_device_accepts_gpu_alias_and_clears_model_cache(self) -> None:
        import tempfile
        from unittest.mock import patch

        from app.services import runtime_settings_service

        old_path = runtime_settings_service.RUNTIME_SETTINGS_PATH
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                runtime_settings_service.RUNTIME_SETTINGS_PATH = Path(temp_dir) / "runtime-settings.json"

                with (
                    patch.object(runtime_settings_service, "_cuda_available", return_value=True),
                    patch.object(runtime_settings_service, "_clear_local_stt_model_cache") as clear_model_cache,
                ):
                    info = runtime_settings_service.update_stt_runtime_settings(local_stt_device="gpu")

                self.assertEqual(info["local_stt_device"], "cuda")
                self.assertEqual(runtime_settings_service.get_local_stt_device(), "cuda")
                clear_model_cache.assert_called_once()
        finally:
            runtime_settings_service.RUNTIME_SETTINGS_PATH = old_path


class CaptureResourceServiceTests(unittest.TestCase):
    def test_browser_video_requires_projection(self) -> None:
        from unittest.mock import patch

        from app.services import capture_resource_service

        session_id = "capture-video-requires-projection"
        capture_resource_service.browser_video_states.pop(session_id, None)
        try:
            with patch("app.services.scrcpy_service.status", return_value={"running": False}):
                with self.assertRaisesRegex(RuntimeError, "请先启动采集投屏"):
                    capture_resource_service.mark_browser_video(session_id, True)
        finally:
            capture_resource_service.browser_video_states.pop(session_id, None)

    def test_ocr_requires_browser_video(self) -> None:
        from app.services import capture_resource_service

        session_id = "capture-ocr-requires-video"
        capture_resource_service.browser_video_states.pop(session_id, None)
        capture_resource_service.ocr_capture_states.pop(session_id, None)
        try:
            with self.assertRaisesRegex(RuntimeError, "请先接入视频流"):
                capture_resource_service.mark_ocr_capture(session_id, True)
        finally:
            capture_resource_service.browser_video_states.pop(session_id, None)
            capture_resource_service.ocr_capture_states.pop(session_id, None)

    def test_recording_requires_browser_video(self) -> None:
        import asyncio
        from datetime import datetime, timezone
        from types import SimpleNamespace
        import sys
        from unittest.mock import patch

        from app.schemas import LiveSession
        from app.services import capture_resource_service
        from app.state import app_state

        session_id = "recording-requires-video"
        previous = app_state.sessions.get(session_id)
        now = datetime.now(timezone.utc)
        app_state.sessions[session_id] = LiveSession(id=session_id, title="recording test", created_at=now, updated_at=now)
        capture_resource_service.browser_video_states.pop(session_id, None)
        try:
            with (
                patch.dict(sys.modules, {"imageio_ffmpeg": SimpleNamespace(get_ffmpeg_exe=lambda: "ffmpeg")}),
                patch("app.services.native_audio_service.is_running", return_value=True),
            ):
                from app.services import recording_service

                with self.assertRaisesRegex(RuntimeError, "请先接入视频流"):
                    asyncio.run(recording_service.start_recording(session_id))
        finally:
            capture_resource_service.browser_video_states.pop(session_id, None)
            recording_service.recording_tasks.pop(session_id, None)
            if previous is None:
                app_state.sessions.pop(session_id, None)
            else:
                app_state.sessions[session_id] = previous

    def test_reset_marks_live_session_stopped(self) -> None:
        import asyncio
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock, patch

        from app.schemas import LiveSession, SessionStatus
        from app.services import capture_resource_service
        from app.state import app_state

        session_id = "capture-reset-session"
        now = datetime.now(timezone.utc)
        previous = app_state.sessions.get(session_id)
        app_state.sessions[session_id] = LiveSession(
            id=session_id,
            title="reset test",
            status=SessionStatus.running,
            created_at=now,
            updated_at=now,
        )
        try:
            with (
                patch("app.services.capture_resource_service.save_live_session"),
                patch.object(capture_resource_service.manager, "broadcast", new=AsyncMock()),
            ):
                asyncio.run(capture_resource_service._stop_live_session(session_id))

            self.assertEqual(app_state.sessions[session_id].status, SessionStatus.stopped)
            self.assertIsNotNone(app_state.sessions[session_id].end_time)
        finally:
            if previous is None:
                app_state.sessions.pop(session_id, None)
            else:
                app_state.sessions[session_id] = previous

    def test_hard_reset_returns_adb_status(self) -> None:
        import asyncio
        from datetime import datetime, timezone
        from unittest.mock import AsyncMock, patch

        from app.schemas import LiveSession
        from app.services import capture_resource_service
        from app.state import app_state

        session_id = "hard-reset-adb-status"
        previous = app_state.sessions.get(session_id)
        now = datetime.now(timezone.utc)
        app_state.sessions[session_id] = LiveSession(id=session_id, title="hard reset", created_at=now, updated_at=now)
        try:
            with (
                patch("app.services.capture_resource_service.save_live_session"),
                patch.object(capture_resource_service.manager, "broadcast", new=AsyncMock()),
                patch("app.services.scrcpy_service.stop_scrcpy", new=AsyncMock(return_value={})),
                patch("app.services.scrcpy_service.cleanup_stale_scrcpy_processes", new=AsyncMock()),
                patch("app.services.native_stt_service.stop_native_stt", new=AsyncMock(return_value={})),
                patch("app.services.phone_capture_service.stop_capture", new=AsyncMock(return_value={})),
                patch("app.services.native_audio_service.stop_native_audio", new=AsyncMock(return_value={})),
                patch("app.services.native_audio_service.cleanup_stale_native_audio_processes", new=AsyncMock()),
                patch("app.services.native_audio_service.recover_adb_once", new=AsyncMock()),
                patch(
                    "app.services.native_audio_service.get_adb_devices_status",
                    new=AsyncMock(return_value={"status": "online", "online_count": 1, "offline_count": 0}),
                ),
            ):
                result = asyncio.run(capture_resource_service.hard_reset(session_id))

            self.assertEqual(result["reset"], "hard")
            self.assertEqual(result["adb_status"]["status"], "online")
            self.assertEqual(result["adb_status"]["online_count"], 1)
        finally:
            if previous is None:
                app_state.sessions.pop(session_id, None)
            else:
                app_state.sessions[session_id] = previous


class PhoneCaptureServiceTests(unittest.TestCase):
    def test_capture_card_device_result_prioritizes_ugreen_video_and_audio(self) -> None:
        from app.services.capture_card_service import build_device_result

        result = build_device_result(
            [
                {
                    "pnp_class": "AudioEndpoint",
                    "name": "MX3228 (NVIDIA High Definition Audio)",
                    "status": "OK",
                    "device_id": "SWD\\MMDEVAPI\\NVIDIA",
                    "manufacturer": "Microsoft",
                    "service": "",
                },
                {
                    "pnp_class": "Camera",
                    "name": "UGREEN 95348",
                    "status": "OK",
                    "device_id": "USB\\VID_2B89&PID_5348&MI_00",
                    "manufacturer": "UGREEN",
                    "service": "usbvideo",
                },
                {
                    "pnp_class": "AudioEndpoint",
                    "name": "数字音频接口 (UGREEN 95348)",
                    "status": "OK",
                    "device_id": "SWD\\MMDEVAPI\\UGREEN",
                    "manufacturer": "Microsoft",
                    "service": "",
                },
            ],
            platform_name="win32",
            errors=[],
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["video_devices"][0]["name"], "UGREEN 95348")
        self.assertTrue(result["video_devices"][0]["is_capture_candidate"])
        self.assertEqual(result["audio_devices"][0]["name"], "数字音频接口 (UGREEN 95348)")
        self.assertTrue(result["audio_devices"][0]["is_capture_candidate"])

    def test_capture_card_parse_pnputil_devices(self) -> None:
        from app.services.capture_card_service import parse_pnputil_devices

        devices = parse_pnputil_devices(
            "Microsoft PnP Utility\n\n"
            "Instance ID:                USB\\VID_2B89&PID_5348&MI_00\\7&2dbee40a&0&0000\n"
            "Device Description:         UGREEN 95348\n"
            "Class Name:                 Camera\n"
            "Manufacturer Name:          Microsoft\n"
            "Status:                     Started\n"
            "Driver Name:                usbvideo.inf\n\n"
            "Instance ID:                SWD\\MMDEVAPI\\UGREEN\n"
            "Device Description:         数字音频接口 (UGREEN 95348)\n"
            "Class Name:                 AudioEndpoint\n"
            "Manufacturer Name:          Microsoft\n"
            "Status:                     Started\n"
            "Driver Name:                audioendpoint.inf\n"
        )

        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0]["name"], "UGREEN 95348")
        self.assertEqual(devices[0]["pnp_class"], "Camera")
        self.assertEqual(devices[1]["name"], "数字音频接口 (UGREEN 95348)")
        self.assertEqual(devices[1]["pnp_class"], "AudioEndpoint")

    def test_capture_card_video_index_uses_selected_device_order(self) -> None:
        from app.services.capture_card_service import _resolve_video_index

        devices = [
            {"id": "camera-built-in", "device_id": "camera-built-in", "is_capture_candidate": False},
            {"id": "ugreen-capture", "device_id": "ugreen-capture", "is_capture_candidate": True},
        ]

        self.assertEqual(_resolve_video_index(devices, device_id="ugreen-capture"), 1)
        self.assertEqual(_resolve_video_index(devices, device_id="missing"), 1)
        self.assertEqual(_resolve_video_index(devices, video_index=3), 3)

    def test_capture_card_stopped_status_shape(self) -> None:
        from app.services.capture_card_service import status

        info = status("missing-capture-card-session")

        self.assertFalse(info["running"])
        self.assertEqual(info["state"], "stopped")
        self.assertEqual(info["frame_count"], 0)

    def test_windows_adb_lookup_includes_scrcpy_v4_bundle(self) -> None:
        from unittest.mock import patch

        from app.services.phone_capture_service import _get_adb_exe

        expected = r"D:\scrcpy-win64-v4.0\adb.exe"

        with (
            patch("app.services.phone_capture_service.sys.platform", "win32"),
            patch("app.services.phone_capture_service.os.path.exists", side_effect=lambda path: path == expected),
            patch("app.services.phone_capture_service.shutil.which", return_value=None),
        ):
            self.assertEqual(_get_adb_exe(), expected)

    def test_drive_root_scan_finds_adb_next_to_scrcpy_bundle(self) -> None:
        import tempfile
        from pathlib import Path

        from app.services.phone_capture_service import _scan_drive_root_adb_candidates

        with tempfile.TemporaryDirectory() as temp_dir:
            scrcpy_dir = Path(temp_dir) / "scrcpy-win64-v4.0"
            scrcpy_dir.mkdir()
            adb_exe = scrcpy_dir / "adb.exe"
            adb_exe.write_bytes(b"")

            candidates = _scan_drive_root_adb_candidates(temp_dir)

        self.assertIn(str(adb_exe), candidates)


class LiveRoomNameDetectionTests(unittest.TestCase):
    def test_extract_live_room_name_uses_top_left_room_label_not_static_store_name(self) -> None:
        from app.services.live_room_name_service import extract_live_room_name

        room_name = extract_live_room_name(
            [
                "LIVE",
                "Current Room 88",
                "Follow",
                "10.2w",
            ]
        )

        self.assertEqual(room_name, "Current Room 88")

    def test_extract_live_room_name_skips_video_account_ui_noise(self) -> None:
        from app.services.live_room_name_service import extract_live_room_name

        room_name = extract_live_room_name(["视频号", "直播中", "New Shop 2", "关注"])

        self.assertEqual(room_name, "New Shop 2")

    def test_extract_live_room_name_matches_known_observation_shops(self) -> None:
        from app.services.live_room_name_service import extract_live_room_name

        expected_names = [
            "浅玩翡翠2号店",
            "菲菲珠宝闲置店",
            "佳心珠宝回流寄售",
            "且慢翡翠珠宝定制",
            "闲值珠宝",
            "春风翡翠寄售回流",
        ]

        for name in expected_names:
            with self.subTest(name=name):
                self.assertEqual(extract_live_room_name(["视频号", f"LIVE {name} 的直播间", "关注"]), name)

    def test_extract_live_room_name_prefers_clean_repeated_store_name(self) -> None:
        from app.services.live_room_name_service import extract_live_room_name

        room_name = extract_live_room_name(
            [
                "5G",
                "平洲万万翡翠手虱",
                "看过",
                "礼物墙 0 /",
                "平洲万万翡翠手镯 -",
                "平洲万万翡翠手躅",
            ]
        )

        self.assertEqual(room_name, "平洲万万翡翠手镯")

    def test_extract_live_room_name_ignores_status_bar_time(self) -> None:
        from app.services.live_room_name_service import extract_live_room_name

        room_name = extract_live_room_name(
            [
                "22:14",
                "2 ： 14 0 ·",
                "5G",
                "100",
                "平洲万万翡翠手镯",
            ]
        )

        self.assertEqual(room_name, "平洲万万翡翠手镯")

        self.assertEqual(extract_live_room_name(["22:14", "2 ： 14 0 ·", "100"]), "")


class LiveCommentOcrTests(unittest.TestCase):
    def test_ocr_lines_are_parsed_into_real_live_comment_events(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import events_from_ocr_lines

        events = events_from_ocr_lines(
            session_id="live-001",
            lines=[
                "粉丝 莲**：林老师的作品不是都被博物馆收起来了吗？",
                "江苏健康广播 FM100.5",
                "K** 关注了主播",
                "聊一聊",
            ],
            now=datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual([event.customer_nickname for event in events], ["莲**", "", "K**", ""])
        self.assertEqual(events[0].customer_level, "[粉丝]")
        self.assertEqual(events[0].event_type, "弹幕")
        self.assertEqual(events[0].content, "林老师的作品不是都被博物馆收起来了吗？")
        self.assertEqual(events[1].event_type, "弹幕")
        self.assertEqual(events[1].content, "江苏健康广播 FM100.5")
        self.assertEqual(events[2].event_type, "关注")
        self.assertEqual(events[3].content, "聊一聊")

    def test_spaced_ocr_lines_are_joined_into_comments(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import events_from_ocr_lines

        events = events_from_ocr_lines(
            session_id="live-001",
            lines=[
                "萍 * * 林 老 师 的 作 品 不 是 都 博 物 馆 收",
                "藏 起 来 了 吗 ， 小 胖 总 今 天 还 带 来 ？",
                "K** 关 注 了 主 播",
                "畝 * * 太 想 看 看 了",
                "中 国 工 艺 美 术 大 师 ， 国 家 高 级 工",
            ],
            now=datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(events[0].customer_nickname, "萍**")
        self.assertEqual(events[0].content, "林老师的作品不是都博物馆收藏起来了吗，小胖总今天还带来？")
        self.assertEqual(events[1].customer_nickname, "K**")
        self.assertEqual(events[1].event_type, "关注")
        self.assertEqual(events[2].event_type, "弹幕")
        self.assertEqual(events[2].content, "太想看看了")
        self.assertEqual(events[3].event_type, "弹幕")
        self.assertEqual(events[3].content, "中国工艺美术大师，国家高级工")
        self.assertEqual(len(events), 4)

    def test_content_only_ocr_lines_are_published_when_nickname_is_missed(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        lines = [
            "精品",
            "很难播 0@都是眼高手低管管",
            "我这个月刚去 还在学习 都是接播",
            "翡翠特色雕刻件专场",
        ]
        events = events_from_ocr_lines(
            session_id="live-001",
            lines=lines,
            now=datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual([event.customer_nickname for event in events], ["", "", "", ""])
        self.assertEqual(
            [event.content for event in dedupe_live_comment_events("live-content-only", events)],
            ["精品", "很难播 @都是眼高手低管管", "我这个月刚去还在学习都是接播", "翡翠特色雕刻件专场"],
        )

    def test_interaction_events_are_published_even_when_short(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        session_id = "live-short-interactions"
        events = events_from_ocr_lines(
            session_id=session_id,
            lines=[
                "张三下单",
                "李**点赞",
                "王**关注了",
                "宋**赞了直播",
                "花下单了闪购商品",
                "关注了主播",
                "用户：帮我点赞",
            ],
            now=datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
        )
        published = dedupe_live_comment_events(session_id, events)

        self.assertEqual(
            [(event.customer_nickname, event.event_type, event.content) for event in published],
            [
                ("张三", "下单", "下单"),
                ("李**", "点赞", "点赞"),
                ("王**", "关注", "关注了"),
                ("宋**", "点赞", "赞了直播"),
                ("花", "下单", "下单了闪购商品"),
                ("", "关注", "关注了主播"),
                ("用户", "弹幕", "帮我点赞"),
            ],
        )

    def test_content_only_question_comments_are_published_without_fake_viewer_name(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        session_id = "live-content-question"
        events = events_from_ocr_lines(
            session_id=session_id,
            lines=[
                "扣头多大？",
                "有没有0.5？",
                "特色翡翠直播",
            ],
            now=datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
        )

        published = dedupe_live_comment_events(session_id, events)

        self.assertEqual([event.content for event in published], ["扣头多大？", "有没有0.5？", "特色翡翠直播"])
        self.assertEqual([event.customer_nickname for event in published], ["", "", ""])

    def test_later_badged_masked_comment_updates_pending_content_only_comment(self) -> None:
        from datetime import datetime, timedelta, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines
        from app.state import app_state

        session_id = "live-update-pending-badged"
        now = datetime(2026, 6, 2, 16, 32, 59, tzinfo=timezone.utc)
        app_state.live_comments[session_id] = []

        try:
            first = dedupe_live_comment_events(
                session_id,
                events_from_ocr_lines(session_id, ["温钟宝跑去吃面了？"], now=now),
            )
            self.assertEqual(len(first), 1)
            self.assertEqual(first[0].customer_nickname, "")
            self.assertEqual(first[0].content, "温钟宝跑去吃面了？")
            self.assertFalse(first[0].is_updated)

            clearer = dedupe_live_comment_events(
                session_id,
                events_from_ocr_lines(session_id, ["+6粉丝温*钟宝跑去吃面了？"], now=now + timedelta(milliseconds=200)),
            )

            self.assertEqual(len(clearer), 1)
            self.assertEqual(f"{clearer[0].customer_level}{clearer[0].customer_nickname}", "[+6][粉丝]温**")
            self.assertEqual(clearer[0].content, "钟宝跑去吃面了？")
            self.assertTrue(clearer[0].is_updated)
        finally:
            app_state.live_comments.pop(session_id, None)

    def test_repeated_live_comment_events_are_deduped_per_session(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        now = datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc)
        first = events_from_ocr_lines("live-ocr-dedupe", ["粉丝 玖**：太想看看了"], now=now)
        repeated = events_from_ocr_lines("live-ocr-dedupe", ["玖**：太想看看了"], now=now)

        self.assertEqual(len(dedupe_live_comment_events("live-ocr-dedupe", first)), 1)
        self.assertEqual(dedupe_live_comment_events("live-ocr-dedupe", repeated), [])

    def test_noisy_repeated_live_comments_are_deduped_by_content(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        now = datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc)
        first = events_from_ocr_lines("live-noisy-dedupe", ["粉丝 亮***：老板挺好的已经干了五六年了"], now=now)
        repeated = events_from_ocr_lines("live-noisy-dedupe", ["亮***：老板挺好的已经干了五六年了"], now=now)

        self.assertEqual(len(dedupe_live_comment_events("live-noisy-dedupe", first)), 1)
        self.assertEqual(dedupe_live_comment_events("live-noisy-dedupe", repeated), [])

    def test_duplicate_live_comments_merge_into_existing_event_count(self) -> None:
        from datetime import datetime, timedelta, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines
        from app.state import app_state

        session_id = "live-merge-duplicates"
        now = datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc)
        app_state.live_comments[session_id] = []

        try:
            first = dedupe_live_comment_events(
                session_id,
                events_from_ocr_lines(session_id, ["粉丝 莲**：扣头多大？"], now=now),
            )
            app_state.live_comments[session_id] = first

            repeated = dedupe_live_comment_events(
                session_id,
                events_from_ocr_lines(session_id, ["莲**：扣头 多大?"], now=now + timedelta(seconds=3)),
            )

            self.assertEqual(len(repeated), 1)
            self.assertEqual(repeated[0].id, first[0].id)
            self.assertEqual(repeated[0].repeat_count, 1)
        finally:
            app_state.live_comments.pop(session_id, None)

    def test_later_clearer_ocr_publishes_pending_comment_with_nickname(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines
        from app.state import app_state

        session_id = "live-ocr-refine"
        now = datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc)
        app_state.live_comments[session_id] = []

        try:
            first = events_from_ocr_lines(session_id, ["老板挺好的已经干了五六年了"], now=now)
            published = dedupe_live_comment_events(session_id, first)
            self.assertEqual(len(published), 1)
            self.assertEqual(published[0].customer_nickname, "")
            app_state.live_comments[session_id] = published

            clearer = events_from_ocr_lines(session_id, ["亮***：老板挺好的已经干了五六年了"], now=now)
            updated = dedupe_live_comment_events(session_id, clearer)

            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0].customer_nickname, "亮**")
            self.assertEqual(updated[0].content, "老板挺好的已经干了五六年了")
        finally:
            app_state.live_comments.pop(session_id, None)

    def test_numeric_only_ocr_nickname_is_published(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        now = datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc)
        noisy = events_from_ocr_lines("live-noisy-nickname", ["4：封底就垫色了"], now=now)
        published = dedupe_live_comment_events("live-noisy-nickname", noisy)

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].customer_nickname, "4")
        self.assertEqual(published[0].content, "封底就垫色了")

    def test_ocr_noise_is_removed_from_masked_nickname_prefixes(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import events_from_ocr_lines

        events = events_from_ocr_lines(
            "live-nickname-clean",
            ["00 可** *：几百啊"],
            now=datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].customer_nickname, "可**")

    def test_masked_video_account_nickname_keeps_two_stars(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        session_id = "live-masked-name"
        events = events_from_ocr_lines(
            session_id,
            ["L* * 来大漏"],
            now=datetime(2026, 6, 2, 15, 25, tzinfo=timezone.utc),
        )
        published = dedupe_live_comment_events(session_id, events)

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].customer_nickname, "L**")
        self.assertEqual(published[0].content, "来大漏")
    def test_fan_badge_before_masked_nickname_becomes_tag(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        session_id = "live-fan-badge"
        events = events_from_ocr_lines(
            session_id,
            ["粉丝 L* * 来大漏"],
            now=datetime(2026, 6, 2, 15, 25, tzinfo=timezone.utc),
        )
        published = dedupe_live_comment_events(session_id, events)

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].customer_nickname, "L**")
        self.assertIn("[粉丝]", published[0].customer_level)
        self.assertEqual(published[0].content, "来大漏")

    def test_compact_badges_and_masked_nickname_use_display_format(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        session_id = "live-compact-tags"
        events = events_from_ocr_lines(
            session_id,
            ["+5粉丝鹅*大高货"],
            now=datetime(2026, 6, 2, 15, 58, 26, tzinfo=timezone.utc),
        )
        published = dedupe_live_comment_events(session_id, events)

        self.assertEqual(len(published), 1)
        self.assertEqual(f"{published[0].customer_level}{published[0].customer_nickname}", "[+5][粉丝]鹅**")
        self.assertEqual(published[0].content, "大高货")

    def test_single_star_masked_nickname_normalizes_to_two_stars(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        session_id = "live-single-star-name"
        events = events_from_ocr_lines(
            session_id,
            ["鹅* 来大漏"],
            now=datetime(2026, 6, 2, 15, 25, tzinfo=timezone.utc),
        )
        published = dedupe_live_comment_events(session_id, events)

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].customer_nickname, "鹅**")
        self.assertEqual(published[0].content, "来大漏")
    def test_ocr_errors_are_sanitized_before_logging(self) -> None:
        from app.services.live_comment_service import sanitize_ocr_error

        message = "local-ocr-error?AccessKeyId=abc&Signature=secret&SignatureNonce=nonce"

        sanitized = sanitize_ocr_error(message)

        self.assertNotIn("abc", sanitized)
        self.assertNotIn("secret", sanitized)
        self.assertNotIn("nonce", sanitized)
        self.assertIn("AccessKeyId=<redacted>", sanitized)


if __name__ == "__main__":
    unittest.main()
