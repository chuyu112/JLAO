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
    def test_projection_scrcpy_disables_audio_forwarding(self) -> None:
        from unittest.mock import patch

        from app.services.scrcpy_service import _build_scrcpy_command

        with (
            patch("app.services.scrcpy_service._get_qtscrcpy_exe", return_value=None),
            patch("app.services.scrcpy_service._get_scrcpy_exe", return_value=r"D:\scrcpy-win64-v3.3.4\scrcpy.exe"),
        ):
            launch = _build_scrcpy_command(serial="", max_size=1024, bit_rate=4_000_000)

        self.assertIn("--no-audio", launch.command)


class NativeSttServiceTests(unittest.TestCase):
    def test_audio_record_command_keeps_device_playback_alive(self) -> None:
        from pathlib import Path

        from app.services.native_stt_service import _build_audio_record_command

        command = _build_audio_record_command(
            scrcpy_exe=r"D:\scrcpy-win64-v3.3.4\scrcpy.exe",
            serial="",
            output_path=Path("chunk.wav"),
            chunk_seconds=3,
        )

        self.assertIn("--audio-source=voice-performance", command)
        self.assertIn("--no-audio-playback", command)
        self.assertNotIn("--time-limit", command)
        self.assertNotIn("--audio-dup", command)
        self.assertNotIn("--audio-source=playback", command)
        self.assertNotIn("--audio-source=output", command)

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

        self.assertEqual([event.customer_nickname for event in events], ["莲**", "K**"])
        self.assertEqual(events[0].customer_level, "真实弹幕")
        self.assertEqual(events[0].event_type, "弹幕")
        self.assertEqual(events[0].content, "林老师的作品不是都被博物馆收起来了吗？")
        self.assertEqual(events[1].event_type, "关注")
        self.assertNotIn("江苏健康广播", [event.content for event in events])

    def test_windows_ocr_spaced_lines_are_joined_into_comments(self) -> None:
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
        self.assertEqual(len(events), 3)

    def test_content_only_ocr_lines_are_buffered_when_nickname_is_missed(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        events = events_from_ocr_lines(
            session_id="live-001",
            lines=[
                "精品",
                "很难播 0@都是眼高手低管管",
                "我这个月刚去 还在学习 都是接播",
                "翡翠特色雕刻件专场",
            ],
            now=datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual([event.customer_nickname for event in events], ["", ""])
        self.assertEqual(dedupe_live_comment_events("live-content-only", events), [])

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
            self.assertEqual(published, [])

            clearer = events_from_ocr_lines(session_id, ["亮***：老板挺好的已经干了五六年了"], now=now)
            updated = dedupe_live_comment_events(session_id, clearer)

            self.assertEqual(len(updated), 1)
            self.assertEqual(updated[0].customer_nickname, "亮***")
            self.assertEqual(updated[0].content, "老板挺好的已经干了五六年了")
        finally:
            app_state.live_comments.pop(session_id, None)

    def test_numeric_only_ocr_nickname_is_buffered_until_clearer(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import dedupe_live_comment_events, events_from_ocr_lines

        now = datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc)
        noisy = events_from_ocr_lines("live-noisy-nickname", ["4：封底就垫色了"], now=now)
        clearer = events_from_ocr_lines("live-noisy-nickname", ["用***：封底就垫色了"], now=now)

        self.assertEqual(dedupe_live_comment_events("live-noisy-nickname", noisy), [])
        published = dedupe_live_comment_events("live-noisy-nickname", clearer)

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0].customer_nickname, "用***")

    def test_ocr_noise_is_removed_from_masked_nickname_prefixes(self) -> None:
        from datetime import datetime, timezone

        from app.services.live_comment_service import events_from_ocr_lines

        events = events_from_ocr_lines(
            "live-nickname-clean",
            ["00 可** *：几百啊"],
            now=datetime(2026, 5, 30, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].customer_nickname, "可***")

    def test_ocr_errors_are_sanitized_before_logging(self) -> None:
        from app.services.live_comment_service import sanitize_ocr_error

        message = "https://ocr-api.cn-hangzhou.aliyuncs.com/?AccessKeyId=abc&Signature=secret&SignatureNonce=nonce"

        sanitized = sanitize_ocr_error(message)

        self.assertNotIn("abc", sanitized)
        self.assertNotIn("secret", sanitized)
        self.assertNotIn("nonce", sanitized)
        self.assertIn("AccessKeyId=<redacted>", sanitized)


if __name__ == "__main__":
    unittest.main()
