import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from server.services.llm import LLMService
from server.services.memory import MemoryService
from server.services.scheduler import ProactiveScheduler

UTC = timezone.utc


class ApiFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        db_path = str(Path(cls.temp_dir.name) / "test_mindshadow.db")
        kb_path = Path(cls.temp_dir.name) / "test_kb.json"
        kb_path.write_text(
            '{"metadata":{"topic":"test","version":"v1","document_count":1},"documents":[{"source":"test.pdf","title":"教育学基础","page":"1","content":"教育目的与课程设计是教编考试常见考点","keywords":["教育目的","课程设计","考点"]}]}',
            encoding="utf-8",
        )
        os.environ["MINDSHADOW_DB_PATH"] = db_path
        os.environ["MINDSHADOW_KB_PATH"] = str(kb_path)
        os.environ["MINDSHADOW_LLM_PROVIDER"] = "mock"
        os.environ["MINDSHADOW_RATE_LIMIT_MAX_REQUESTS_PER_MINUTE"] = "3"
        os.environ["MINDSHADOW_OPS_TOKEN"] = "ops-secret"
        os.environ["MINDSHADOW_MEMORY_DEBUG_ENABLED"] = "1"
        os.environ["MINDSHADOW_HYBRID_RECALL_ENABLED"] = "1"
        os.environ["MINDSHADOW_HYBRID_RECALL_RATIO"] = "1"
        from server.app import create_app

        cls.app = create_app()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()

    def test_health_returns_llm_state(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("llm", payload)
        self.assertIn("provider", payload["llm"])
        self.assertIn("metrics", payload)
        self.assertIn("X-Request-ID", response.headers)

    def test_ready_endpoint_returns_dependency_checks(self) -> None:
        response = self.client.get("/api/ready")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("ok", payload)
        self.assertIn("checks", payload)
        self.assertIn("db", payload["checks"])
        self.assertIn("kb", payload["checks"])
        self.assertIn("uploads", payload["checks"])
        self.assertIn("scheduler", payload["checks"])

    def test_ops_metrics_requires_token(self) -> None:
        forbidden = self.client.get("/api/ops/metrics")
        self.assertEqual(forbidden.status_code, 403)
        allowed = self.client.get("/api/ops/metrics", headers={"X-Ops-Token": "ops-secret"})
        self.assertEqual(allowed.status_code, 200)
        payload = allowed.get_json()
        self.assertIn("metrics", payload)

    def test_ops_persona_config_get_and_update(self) -> None:
        forbidden = self.client.get("/api/ops/persona-config")
        self.assertEqual(forbidden.status_code, 403)
        current = self.client.get("/api/ops/persona-config", headers={"X-Ops-Token": "ops-secret"})
        self.assertEqual(current.status_code, 200)
        current_payload = current.get_json()
        self.assertIn("config", current_payload)
        original_name = current_payload["config"]["assistant_name"]

        update = self.client.post(
            "/api/ops/persona-config",
            headers={"X-Ops-Token": "ops-secret"},
            json={"assistant_name": "教编冲刺教练", "list_limit": 2},
        )
        self.assertEqual(update.status_code, 200)
        updated_payload = update.get_json()
        self.assertEqual(updated_payload["config"]["assistant_name"], "教编冲刺教练")
        self.assertEqual(int(updated_payload["config"]["list_limit"]), 2)

        restored = self.client.post(
            "/api/ops/persona-config",
            headers={"X-Ops-Token": "ops-secret"},
            json={"assistant_name": original_name, "list_limit": 3},
        )
        self.assertEqual(restored.status_code, 200)

    def test_analytics_event_flow(self) -> None:
        response = self.client.post(
            "/api/analytics/events",
            json={
                "user_id": "analytics-user",
                "event_name": "answer_richtext_rendered",
                "event_payload": {
                    "message_id": "m-1",
                    "visual_lines": 12,
                    "collapsed_by_default": True,
                },
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["event_name"], "answer_richtext_rendered")

    def test_chat_history_flow(self) -> None:
        send = self.client.post("/api/chat", json={"text": "我今天学递归", "user_id": "test-user"})
        self.assertEqual(send.status_code, 200)
        send_payload = send.get_json()
        self.assertIn("reply", send_payload)
        self.assertIn("mode", send_payload)
        self.assertIn("kb_used", send_payload)
        self.assertIn("kb_sources", send_payload)
        self.assertIn("citations", send_payload)
        self.assertIn("citation_summary", send_payload)
        self.assertIn("total", send_payload["citation_summary"])
        self.assertIn("has_conflict", send_payload["citation_summary"])

        history = self.client.get("/api/history?user_id=test-user&limit=20")
        self.assertEqual(history.status_code, 200)
        history_payload = history.get_json()
        self.assertGreaterEqual(len(history_payload["messages"]), 2)

    def test_chat_history_isolated_by_conversation_but_shared_profile(self) -> None:
        user_id = "multi-conv-user"
        first = self.client.post(
            "/api/chat",
            json={
                "text": "我目标82分，讲下教育目的",
                "user_id": user_id,
                "conversation_id": "session-a",
            },
        )
        self.assertEqual(first.status_code, 200)

        second = self.client.post(
            "/api/chat",
            json={
                "text": "继续讲重点",
                "user_id": user_id,
                "conversation_id": "session-b",
            },
        )
        self.assertEqual(second.status_code, 200)

        history_a = self.client.get("/api/history?user_id=multi-conv-user&conversation_id=session-a&limit=20")
        self.assertEqual(history_a.status_code, 200)
        messages_a = history_a.get_json()["messages"]
        self.assertTrue(any("我目标82分" in str(item.get("content", "")) for item in messages_a))
        self.assertFalse(any("继续讲重点" in str(item.get("content", "")) for item in messages_a))

        history_b = self.client.get("/api/history?user_id=multi-conv-user&conversation_id=session-b&limit=20")
        self.assertEqual(history_b.status_code, 200)
        messages_b = history_b.get_json()["messages"]
        self.assertTrue(any("继续讲重点" in str(item.get("content", "")) for item in messages_b))
        self.assertFalse(any("我目标82分" in str(item.get("content", "")) for item in messages_b))

        profile = self.client.get(f"/api/profile?user_id={user_id}")
        self.assertEqual(profile.status_code, 200)
        self.assertTrue(str(profile.get_json()["profile"]["exam_goal"]).startswith("82"))

    def test_chat_stream_flow(self) -> None:
        response = self.client.post("/api/chat/stream", json={"text": "讲下教育目的", "user_id": "stream-user"})
        self.assertEqual(response.status_code, 200)
        lines = [line for line in response.data.decode("utf-8").splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 2)
        payloads = [json.loads(line) for line in lines]
        self.assertEqual(payloads[0]["type"], "meta")
        self.assertIn("memory_debug", payloads[0])
        self.assertEqual(payloads[-1]["type"], "done")
        self.assertIn("reply", payloads[-1])
        self.assertIn("memory_debug", payloads[-1])
        self.assertIn("citations", payloads[-1])
        self.assertIn("citation_summary", payloads[-1])
        history = self.client.get("/api/history?user_id=stream-user&limit=20")
        self.assertEqual(history.status_code, 200)
        messages = history.get_json()["messages"]
        self.assertTrue(any(item["role"] == "ai" and item["content"] for item in messages))

    def test_memory_recall_summary_flow(self) -> None:
        user_id = "recall-summary-user"
        chat = self.client.post("/api/chat", json={"text": "我目标80分，讲下教育目的", "user_id": user_id})
        self.assertEqual(chat.status_code, 200)
        chat_payload = chat.get_json()
        self.assertIn("memory_debug", chat_payload)
        summary = self.client.get(f"/api/memory/recall-summary?user_id={user_id}&days=7&limit=20")
        self.assertEqual(summary.status_code, 200)
        summary_payload = summary.get_json()["summary"]
        self.assertGreaterEqual(int(summary_payload["total_events"]), 1)
        self.assertIn("by_channel", summary_payload)
        self.assertIn("source_usage_counts", summary_payload)

    def test_chat_hybrid_semantic_recall_flow(self) -> None:
        user_id = "hybrid-user"
        create = self.client.post(
            "/api/memory-cards",
            json={
                "user_id": user_id,
                "card": {
                    "title": "人物识记卡",
                    "content": "夸美纽斯是近代教育学之父，赫尔巴特是科学教育学奠基人",
                    "tags": ["人物识记", "教育学"],
                },
            },
        )
        self.assertEqual(create.status_code, 200)
        response = self.client.post("/api/chat", json={"text": "人物识记总混怎么办", "user_id": user_id})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(bool(payload["semantic_used"]))
        self.assertGreaterEqual(len(payload["semantic_sources"]), 1)
        self.assertEqual(payload["semantic_sources"][0]["retrieval_mode"], "vector_hybrid")
        self.assertIn("vector_similarity", payload["semantic_sources"][0])
        self.assertIn("memory_debug", payload)
        self.assertIn("semantic", payload["memory_debug"]["memory_sources_used"])
        self.assertIn("hybrid_used", payload["memory_debug"])

    def test_chat_memory_explanation_card_flow(self) -> None:
        user_id = "memory-explain-user"
        create = self.client.post(
            "/api/memory-cards",
            json={
                "user_id": user_id,
                "card": {
                    "title": "教育学记忆点",
                    "content": "教育目的常见考法是定义、功能和价值取向",
                    "tags": ["教育目的", "高频考点"],
                },
            },
        )
        self.assertEqual(create.status_code, 200)
        response = self.client.post(
            "/api/chat",
            json={
                "text": "教育目的怎么答",
                "user_id": user_id,
                "include_memory_explanation": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("memory_explanation", payload)
        explanation = payload["memory_explanation"]
        self.assertIn("memory_sources", explanation)
        self.assertIn("references", explanation)

    def test_hybrid_config_update_and_dashboard_flow(self) -> None:
        for event_name, event_payload in [
            ("answer_richtext_rendered", {"message_id": "m-1", "visual_lines": 12, "rich_block_count": 4, "collapsed_by_default": True}),
            ("answer_expand_clicked", {"message_id": "m-1", "expanded": True}),
            ("answer_citation_toggled", {"message_id": "m-1", "expanded": True}),
            ("answer_citation_copied", {"message_id": "m-1", "source_type": "kb", "quote_length": 32}),
        ]:
            event_resp = self.client.post(
                "/api/analytics/events",
                json={
                    "user_id": "hybrid-user",
                    "event_name": event_name,
                    "event_payload": event_payload,
                },
            )
            self.assertEqual(event_resp.status_code, 200)
        update = self.client.post(
            "/api/memory/hybrid-config",
            headers={"X-Ops-Token": "ops-secret"},
            json={
                "enabled": True,
                "ratio": 1,
                "top_k": 4,
                "time_decay_days": 21,
                "freshness_weight": 0.3,
                "semantic_weight": 0.6,
                "min_similarity": 0.1,
                "source_weights": {"memory_card": 1.2, "review": 1.1, "message": 0.9},
            },
        )
        self.assertEqual(update.status_code, 200)
        config = update.get_json()["hybrid_config"]
        self.assertEqual(int(config["top_k"]), 4)
        self.assertAlmostEqual(float(config["freshness_weight"]), 0.3)
        self.assertAlmostEqual(float(config["semantic_weight"]), 0.6)

        dashboard = self.client.get(
            "/api/ops/recall-dashboard?user_id=hybrid-user&days=7",
            headers={"X-Ops-Token": "ops-secret"},
        )
        self.assertEqual(dashboard.status_code, 200)
        dashboard_payload = dashboard.get_json()
        self.assertIn("recall", dashboard_payload)
        self.assertIn("answer_quality", dashboard_payload)
        self.assertIn("nudge", dashboard_payload)
        self.assertIn("weekly_learning", dashboard_payload)
        answer_quality = dashboard_payload["answer_quality"]
        self.assertGreaterEqual(int(answer_quality["rendered_count"]), 1)
        self.assertGreaterEqual(float(answer_quality["expand_rate"]), 0.0)
        self.assertGreaterEqual(float(answer_quality["citation_open_rate"]), 0.0)
        self.assertGreaterEqual(float(answer_quality["citation_copy_rate"]), 0.0)

    def test_embedding_config_runtime_switch_and_reindex_flow(self) -> None:
        user_id = "embedding-config-user"
        self.client.post(
            "/api/memory-cards",
            json={
                "user_id": user_id,
                "card": {
                    "title": "教育目的记忆卡",
                    "content": "教育目的要答定义、功能、价值取向",
                    "tags": ["教育目的"],
                },
            },
        )
        current = self.client.get("/api/memory/embedding-config")
        self.assertEqual(current.status_code, 200)
        self.assertIn("embedding_config", current.get_json())
        forbidden = self.client.post(
            "/api/memory/embedding-config",
            json={"provider": "hash", "reindex_user_id": user_id},
        )
        self.assertEqual(forbidden.status_code, 403)
        update = self.client.post(
            "/api/memory/embedding-config",
            headers={"X-Ops-Token": "ops-secret"},
            json={
                "provider": "hash",
                "reindex_user_id": user_id,
            },
        )
        self.assertEqual(update.status_code, 200)
        payload = update.get_json()
        self.assertEqual(payload["embedding_config"]["provider"], "hash")
        self.assertEqual(payload["reindex"]["target_user_id"], user_id)
        self.assertGreaterEqual(int(payload["reindex"]["vector_count"]), 1)

    def test_ingest_flow(self) -> None:
        response = self.client.post(
            "/api/ingest",
            json={"content": "递归\n终止条件\n函数调用栈", "user_id": "ingest-user"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("topic", payload)
        self.assertEqual(len(payload["concepts"]), 3)
        self.assertIn("mode", payload)

    def test_rate_limit_for_chat(self) -> None:
        user_id = "rate-limit-user"
        for index in range(3):
            response = self.client.post("/api/chat", json={"text": f"第{index}次", "user_id": user_id})
            self.assertEqual(response.status_code, 200)
        blocked = self.client.post("/api/chat", json={"text": "第4次", "user_id": user_id})
        self.assertEqual(blocked.status_code, 429)
        payload = blocked.get_json()
        self.assertIn("retry_after_seconds", payload)

    def test_upload_and_vision_query_flow(self) -> None:
        upload = self.client.post(
            "/api/upload-image",
            data={
                "user_id": "vision-user",
                "image": (io.BytesIO(b"fakepngdata"), "sample.png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload.status_code, 200)
        upload_payload = upload.get_json()
        self.assertIn("image_url", upload_payload)

        reply = self.client.post(
            "/api/vision-query",
            json={
                "question": "这道题在考什么",
                "image_url": upload_payload["image_url"],
                "user_id": "vision-user",
            },
        )
        self.assertEqual(reply.status_code, 200)
        reply_payload = reply.get_json()
        self.assertIn("reply", reply_payload)
        self.assertIn("mode", reply_payload)
        self.assertIn("citations", reply_payload)
        self.assertIn("citation_summary", reply_payload)

    def test_profile_get_and_update_flow(self) -> None:
        user_id = "profile-user"
        update = self.client.post(
            "/api/profile",
            json={
                "user_id": user_id,
                "profile": {
                    "exam_goal": "75+",
                    "exam_date": "2026-06-20",
                    "response_style": "先结论后口诀",
                    "weak_points": ["教育心理学", "人物识记"],
                    "study_schedule": "工作日晚间1小时",
                    "motivation_note": "目标上岸",
                },
            },
        )
        self.assertEqual(update.status_code, 200)
        update_payload = update.get_json()
        self.assertEqual(update_payload["profile"]["response_style"], "先结论后口诀")
        self.assertEqual(update_payload["profile"]["weak_points"][0], "教育心理学")

        read = self.client.get(f"/api/profile?user_id={user_id}")
        self.assertEqual(read.status_code, 200)
        read_payload = read.get_json()
        self.assertEqual(read_payload["profile"]["exam_goal"], "75+")
        self.assertEqual(read_payload["profile"]["study_schedule"], "工作日晚间1小时")

        chat = self.client.post("/api/chat", json={"text": "教育起源学说怎么记", "user_id": user_id})
        self.assertEqual(chat.status_code, 200)
        chat_payload = chat.get_json()
        self.assertIn("先结论后口诀", chat_payload["reply"])

    def test_llm_prompt_includes_user_profile(self) -> None:
        llm = LLMService()
        llm.provider = "openai"
        llm.api_key = "x"
        captured: dict[str, str] = {}

        def fake(messages, temperature, max_tokens):
            captured["system"] = messages[0]["content"]
            return "ok"

        llm._post_chat_completion = fake
        llm.chat(
            recent_messages=[{"role": "user", "content": "讲下教育起源学说"}],
            focus_topic="教育学",
            kb_context=[{"title": "教招口诀速记92个 (2)", "page": "1", "snippet": "教育起源学说"}],
            user_profile={
                "exam_goal": "75+",
                "response_style": "先结论后口诀",
                "weak_points": ["人物识记"],
            },
        )
        self.assertIn("用户长期画像", captured["system"])
        self.assertIn("讲解偏好:先结论后口诀", captured["system"])
        self.assertIn("薄弱点:人物识记", captured["system"])
        self.assertIn("只能引用当前上下文里可验证的信息", captured["system"])
        self.assertIn("要明确说“不确定”", captured["system"])

    def test_chat_auto_updates_profile_from_user_message(self) -> None:
        user_id = "auto-profile-user"
        response = self.client.post(
            "/api/chat",
            json={
                "user_id": user_id,
                "text": "我目标是78分，先结论后口诀讲，教育心理学我总是错在人物识记，工作日晚间学习",
            },
        )
        self.assertEqual(response.status_code, 200)
        profile = self.client.get(f"/api/profile?user_id={user_id}")
        self.assertEqual(profile.status_code, 200)
        payload = profile.get_json()["profile"]
        self.assertEqual(payload["exam_goal"], "78+")
        self.assertEqual(payload["response_style"], "先结论后口诀")
        self.assertIn("人物识记", payload["weak_points"])
        self.assertIn("工作日", payload["study_schedule"])

    def test_chat_auto_updates_profile_with_relative_date_and_negation(self) -> None:
        user_id = "auto-profile-negation-user"
        response = self.client.post(
            "/api/chat",
            json={
                "user_id": user_id,
                "text": "我不是要简洁讲解，按步骤来。考试在明天，教育心理学我老忘人物识记",
            },
        )
        self.assertEqual(response.status_code, 200)
        profile = self.client.get(f"/api/profile?user_id={user_id}")
        self.assertEqual(profile.status_code, 200)
        payload = profile.get_json()["profile"]
        self.assertEqual(payload["response_style"], "按步骤讲解")
        self.assertIn("人物识记", payload["weak_points"])
        expected_date = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()
        self.assertEqual(payload["exam_date"], expected_date)

    def test_profile_conflict_event_logged_when_field_changes(self) -> None:
        user_id = "profile-conflict-user"
        first = self.client.post(
            "/api/chat",
            json={"user_id": user_id, "text": "我目标75分，先结论后口诀"},
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            "/api/chat",
            json={"user_id": user_id, "text": "目标改成82分，按步骤讲"},
        )
        self.assertEqual(second.status_code, 200)
        memory = MemoryService(db_path=os.environ["MINDSHADOW_DB_PATH"])
        with memory._conn() as conn:
            rows = conn.execute(
                """
                SELECT field_name, old_value, new_value
                FROM profile_conflict_events
                WHERE user_id = ?
                ORDER BY id ASC
                """,
                (user_id,),
            ).fetchall()
        self.assertTrue(any(str(row["field_name"]) == "exam_goal" for row in rows))
        self.assertTrue(any(str(row["field_name"]) == "response_style" for row in rows))

    def test_llm_welcome_reply_uses_profile(self) -> None:
        llm = LLMService()
        reply = llm.chat(
            recent_messages=[],
            focus_topic="未设置学习主题",
            user_profile={"exam_goal": "80+", "response_style": "先结论后口诀"},
        )
        self.assertIn("80+", reply)
        self.assertIn("先结论后口诀", reply)

    def test_generate_hook_uses_profile(self) -> None:
        llm = LLMService()
        hook = llm.generate_hook(
            focus_topic="教育学",
            user_profile={"exam_goal": "78+", "weak_points": ["人物识记"]},
            nudge_level="focus",
        )
        self.assertIn("78+", hook)
        self.assertIn("人物识记", hook)
        self.assertIn("集中突破", hook)

    def test_generate_hook_supports_urgent_level(self) -> None:
        llm = LLMService()
        hook = llm.generate_hook(
            focus_topic="教育心理学",
            user_profile={"weak_points": ["动机理论"]},
            nudge_level="urgent",
        )
        self.assertIn("优先补齐", hook)
        self.assertIn("动机理论", hook)

    def test_memory_cards_crud_and_rollback_flow(self) -> None:
        user_id = "card-user"
        create = self.client.post(
            "/api/memory-cards",
            json={
                "user_id": user_id,
                "card": {
                    "title": "人物识记口诀",
                    "content": "夸美纽斯是近代教育学之父",
                    "tags": ["人物", "教育学"],
                },
            },
        )
        self.assertEqual(create.status_code, 200)
        created = create.get_json()["card"]
        card_id = created["id"]
        self.assertEqual(created["status"], "active")

        update = self.client.patch(
            f"/api/memory-cards/{card_id}",
            json={
                "user_id": user_id,
                "card": {
                    "content": "赫尔巴特是科学教育学奠基人",
                    "tags": ["人物", "教育心理学"],
                },
            },
        )
        self.assertEqual(update.status_code, 200)
        updated = update.get_json()["card"]
        self.assertIn("赫尔巴特", updated["content"])
        self.assertIn("教育心理学", updated["tags"])

        delete = self.client.delete(f"/api/memory-cards/{card_id}", json={"user_id": user_id})
        self.assertEqual(delete.status_code, 200)
        deleted = delete.get_json()["card"]
        self.assertEqual(deleted["status"], "deleted")

        rollback = self.client.post(
            f"/api/memory-cards/{card_id}/rollback",
            json={"user_id": user_id},
        )
        self.assertEqual(rollback.status_code, 200)
        restored = rollback.get_json()["card"]
        self.assertEqual(restored["status"], "active")
        self.assertIn("赫尔巴特", restored["content"])

        active_list = self.client.get(f"/api/memory-cards?user_id={user_id}")
        self.assertEqual(active_list.status_code, 200)
        cards = active_list.get_json()["cards"]
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["status"], "active")

    def test_learning_export_answer_flow_creates_cards_and_reviews(self) -> None:
        user_id = "learning-export-user"
        export = self.client.post(
            "/api/learning/export-answer",
            json={
                "user_id": user_id,
                "source_question": "这道错题我总错在教育目的",
                "answer_text": "教育目的不是教学目标。错题复盘先看概念边界，再对照题干关键词。",
            },
        )
        self.assertEqual(export.status_code, 200)
        payload = export.get_json()["export"]
        self.assertIn("学习卡片", payload["summary_card"]["title"])
        self.assertGreaterEqual(payload["term_cards_added"], 1)
        self.assertGreaterEqual(payload["review_records_created"], 1)
        self.assertIsInstance(payload.get("cards"), list)
        self.assertTrue(any(item.get("is_primary") for item in payload.get("cards", [])))
        self.assertIn(payload.get("primary_card_type"), {"definition", "comparison", "steps", "mistake", "mnemonic"})
        if payload.get("cards"):
            self.assertIn(payload["cards"][0].get("card_type"), {"definition", "comparison", "steps", "mistake", "mnemonic"})

        cards = self.client.get(f"/api/memory-cards?user_id={user_id}")
        self.assertEqual(cards.status_code, 200)
        listed = cards.get_json()["cards"]
        self.assertTrue(any(item.get("card_type") in {"definition", "comparison", "steps", "mistake", "mnemonic"} for item in listed))
        titles = [str(item["title"]) for item in listed]
        self.assertTrue(any(title.startswith("学习卡片：") for title in titles))
        self.assertTrue(any(title.startswith(prefix) for title in titles for prefix in ("定义卡：", "辨析卡：", "步骤卡：", "错因卡：", "速记卡：")))

    def test_learning_export_filters_gibberish_terms(self) -> None:
        user_id = "learning-export-clean-user"
        export = self.client.post(
            "/api/learning/export-answer",
            json={
                "user_id": user_id,
                "source_question": "教育学基础术语梳理",
                "answer_text": "先看**构进行神人**这个错误写法，再看教育目的、教学目标和课程标准的区别。",
            },
        )
        self.assertEqual(export.status_code, 200)
        cards = self.client.get(f"/api/memory-cards?user_id={user_id}")
        self.assertEqual(cards.status_code, 200)
        listed = cards.get_json()["cards"]
        titles = [str(item["title"]) for item in listed]
        self.assertTrue(any(title.startswith("学习卡片：") for title in titles))
        self.assertFalse(any(title.endswith("：构进行神人") for title in titles))
        self.assertTrue(any(title.endswith("：教育目的") or title.endswith("：教学目标") or title.endswith("：课程标准") for title in titles))

    def test_memory_service_accepts_dynamic_term_whitelist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = str(Path(temp_dir) / "whitelist_test.db")
            original = os.environ.get("MINDSHADOW_TERM_WHITELIST")
            os.environ["MINDSHADOW_TERM_WHITELIST"] = "最近发展区, 课堂提问链"
            try:
                service = MemoryService(db_path=db_path)
                exported = service.export_answer_to_learning_assets(
                    user_id="whitelist-user",
                    source_question="教育心理学概念复盘",
                    answer_text="本题先抓住最近发展区，再使用课堂提问链推进学生思考。",
                )
            finally:
                if original is None:
                    os.environ.pop("MINDSHADOW_TERM_WHITELIST", None)
                else:
                    os.environ["MINDSHADOW_TERM_WHITELIST"] = original
            terms = exported["terms"]
            self.assertIn("最近发展区", terms)
            self.assertIn("课堂提问链", terms)

    def test_learning_export_prioritizes_meaningful_terms_and_term_limit(self) -> None:
        user_id = "learning-export-priority-user"
        original = os.environ.get("MINDSHADOW_EXPORT_TERM_LIMIT")
        os.environ["MINDSHADOW_EXPORT_TERM_LIMIT"] = "4"
        try:
            export = self.client.post(
                "/api/learning/export-answer",
                json={
                    "user_id": user_id,
                    "source_question": "教学设计错题复盘",
                    "answer_text": (
                        "这题关键看教学目标、课程标准、形成性评价、终结性评价。"
                        "其中教学目标是课堂达成标准，课程标准是学段框架，形成性评价用于过程反馈，终结性评价用于阶段判断。"
                        "这个、那个、首先、然后这些词不是概念。"
                    ),
                },
            )
        finally:
            if original is None:
                os.environ.pop("MINDSHADOW_EXPORT_TERM_LIMIT", None)
            else:
                os.environ["MINDSHADOW_EXPORT_TERM_LIMIT"] = original
        self.assertEqual(export.status_code, 200)
        payload = export.get_json()["export"]
        terms = payload["terms"]
        self.assertLessEqual(len(terms), 2)
        self.assertGreaterEqual(len(terms), 1)
        self.assertTrue(any(item in {"教学目标", "课程标准", "形成性评价", "终结性评价"} for item in terms))
        self.assertFalse(any(item in {"这个", "那个", "首先", "然后"} for item in terms))
        self.assertEqual(payload["term_cards_limit"], 2)
        decision = payload["export_decision"]
        self.assertTrue(decision["allow_term_cards"])
        self.assertIsNone(decision["reject_reason"])
        self.assertGreaterEqual(len(payload["quality_scores"]), len(terms))

    def test_learning_export_rejects_interrogative_noise_term(self) -> None:
        user_id = "learning-export-noise-user"
        export = self.client.post(
            "/api/learning/export-answer",
            json={
                "user_id": user_id,
                "source_question": "术语整理",
                "answer_text": "**为什么：** **为什么：** 教学目标是课堂达成标准，课程标准用于学段要求。",
            },
        )
        self.assertEqual(export.status_code, 200)
        payload = export.get_json()["export"]
        terms = payload["terms"]
        self.assertFalse(any(item == "为什么" for item in terms))
        cards = self.client.get(f"/api/memory-cards?user_id={user_id}")
        self.assertEqual(cards.status_code, 200)
        listed = cards.get_json()["cards"]
        titles = [str(item["title"]) for item in listed]
        self.assertFalse(any(title.endswith("：为什么") for title in titles))
        self.assertTrue(any(title.endswith("：教学目标") or title.endswith("：课程标准") for title in titles))

    def test_learning_export_avoids_generic_mnemonic_terms(self) -> None:
        user_id = "learning-export-mnemonic-user"
        export = self.client.post(
            "/api/learning/export-answer",
            json={
                "user_id": user_id,
                "source_question": "教学的基本任务是什么",
                "answer_text": (
                    "教学的基本任务包括德育、智育、体育、美育、劳动技术教育。"
                    "记忆时可用口诀：德智体美劳。"
                    "其中德育强调方向与价值引导。"
                ),
            },
        )
        self.assertEqual(export.status_code, 200)
        payload = export.get_json()["export"]
        self.assertFalse(any(item == "口诀记忆" or item == "记忆口诀" for item in payload["terms"]))
        cards = payload.get("cards", [])
        self.assertTrue(len(cards) >= 1)
        self.assertTrue(any(str(card.get("card_type")) in {"definition", "comparison", "steps", "mistake"} for card in cards))
        self.assertFalse(any(str(card.get("title", "")).endswith("：口诀记忆") for card in cards))

    def test_learning_export_strips_trailing_qualifier_terms(self) -> None:
        user_id = "learning-export-qualifier-user"
        export = self.client.post(
            "/api/learning/export-answer",
            json={
                "user_id": user_id,
                "source_question": "德育的目标包括哪些",
                "answer_text": (
                    "德育目标主要包括思想目标、政治目标、道德目标、心理健康目标。"
                    "核心是培养学生成为有理想、有道德、有文化、有纪律的社会主义建设者和接班人。"
                ),
            },
        )
        self.assertEqual(export.status_code, 200)
        payload = export.get_json()["export"]
        terms = payload["terms"]
        self.assertFalse(any(str(term).endswith("主要") for term in terms))
        self.assertTrue(any(str(term) == "德育目标" for term in terms))
        cards = payload.get("cards", [])
        self.assertFalse(any(str(card.get("term", "")).endswith("主要") for card in cards))

    def test_learning_export_summary_card_has_structured_content(self) -> None:
        user_id = "learning-export-structured-summary-user"
        export = self.client.post(
            "/api/learning/export-answer",
            json={
                "user_id": user_id,
                "source_question": "德育的目标包括哪些",
                "answer_text": (
                    "德育目标主要包括思想目标、政治目标、道德目标、心理健康目标。"
                    "核心是培养学生成为有理想、有道德、有文化、有纪律的社会主义建设者和接班人。"
                ),
            },
        )
        self.assertEqual(export.status_code, 200)
        payload = export.get_json()["export"]
        summary_content = str(payload["summary_card"]["content"])
        self.assertIn("核心答案：", summary_content)
        self.assertIn("答题动作：", summary_content)
        self.assertIn("自测题：", summary_content)

    def test_learning_export_returns_experience_feedback(self) -> None:
        user_id = "learning-export-experience-user"
        export = self.client.post(
            "/api/learning/export-answer",
            json={
                "user_id": user_id,
                "source_question": "教学的基本任务是什么",
                "answer_text": "教学的基本任务包括德育、智育、体育、美育、劳动技术教育。",
            },
        )
        self.assertEqual(export.status_code, 200)
        payload = export.get_json()["export"]
        experience = payload.get("experience")
        self.assertIsInstance(experience, dict)
        self.assertIn(str(experience.get("status")), {"cards_ready", "summary_only"})
        self.assertTrue(str(experience.get("message", "")).strip())
        self.assertTrue(str(experience.get("next_action", "")).strip())
        generation = payload.get("generation")
        self.assertIsInstance(generation, dict)
        self.assertEqual(generation.get("strategy"), "hybrid_guardrailed")
        self.assertIsInstance(generation.get("llm_enabled"), bool)
        self.assertIsInstance(generation.get("llm_card_limit"), int)
        cards = payload.get("cards", [])
        for card in cards:
            self.assertIn(str(card.get("generation_mode", "")), {"llm", "rule"})

    def test_learning_export_gate_keeps_summary_when_content_is_noise(self) -> None:
        user_id = "learning-export-gate-user"
        export = self.client.post(
            "/api/learning/export-answer",
            json={
                "user_id": user_id,
                "source_question": "帮我整理",
                "answer_text": "嗯嗯，好的！！！~~~",
            },
        )
        self.assertEqual(export.status_code, 200)
        payload = export.get_json()["export"]
        self.assertEqual(payload["terms"], [])
        self.assertEqual(payload["term_cards_added"], 0)
        decision = payload["export_decision"]
        self.assertFalse(decision["allow_term_cards"])
        self.assertIn(decision["reject_reason"], {"too_short_no_structure", "insufficient_information", "high_noise_content"})
        cards = self.client.get(f"/api/memory-cards?user_id={user_id}")
        self.assertEqual(cards.status_code, 200)
        titles = [str(item["title"]) for item in cards.get_json()["cards"]]
        self.assertTrue(any(title.startswith("学习卡片：") for title in titles))
        self.assertFalse(any(title.startswith(prefix) for title in titles for prefix in ("定义卡：", "辨析卡：", "步骤卡：", "错因卡：", "速记卡：")))

    def test_study_plan_generate_and_query_flow(self) -> None:
        user_id = "plan-user"
        chat = self.client.post("/api/chat", json={"text": "我最近在学教育心理学", "user_id": user_id})
        self.assertEqual(chat.status_code, 200)
        profile_update = self.client.post(
            "/api/profile",
            json={
                "user_id": user_id,
                "profile": {
                    "exam_goal": "80+",
                    "study_schedule": "工作日晚间1小时",
                    "weak_points": ["人物识记"],
                },
            },
        )
        self.assertEqual(profile_update.status_code, 200)
        generate = self.client.post("/api/study-plan/generate", json={"user_id": user_id, "date": "2026-03-16"})
        self.assertEqual(generate.status_code, 200)
        payload = generate.get_json()
        self.assertEqual(payload["plan"]["plan_date"], "2026-03-16")
        self.assertEqual(len(payload["plan"]["tasks"]), 3)
        self.assertGreater(payload["plan"]["duration_minutes"], 0)
        checkin = self.client.post(
            "/api/study-plan/checkin",
            json={
                "user_id": user_id,
                "date": "2026-03-16",
                "completed_tasks": 2,
                "note": "第二步有点卡住",
            },
        )
        self.assertEqual(checkin.status_code, 200)
        checkin_payload = checkin.get_json()
        self.assertEqual(checkin_payload["checkin"]["completed_tasks"], 2)

        query = self.client.get("/api/study-plan?user_id=plan-user&date=2026-03-16")
        self.assertEqual(query.status_code, 200)
        queried = query.get_json()["plan"]
        self.assertEqual(queried["plan_date"], "2026-03-16")
        self.assertIn("checkin_question", queried)
        self.assertEqual(queried["completed_tasks"], 2)

    def test_review_template_generate_and_list_flow(self) -> None:
        user_id = "review-user"
        generate = self.client.post(
            "/api/review-template/generate",
            json={
                "user_id": user_id,
                "focus_topic": "教育学",
                "source_question": "这题我总是审题错误，题干读偏了",
            },
        )
        self.assertEqual(generate.status_code, 200)
        review = generate.get_json()["review"]
        self.assertEqual(review["mistake_type"], "审题失误")
        self.assertTrue(review["fix_action"])
        self.assertFalse(review["is_repeat_mistake"])

        second_generate = self.client.post(
            "/api/review-template/generate",
            json={
                "user_id": user_id,
                "focus_topic": "教育学",
                "source_question": "我还是会审题跑偏，题干抓不住重点",
            },
        )
        self.assertEqual(second_generate.status_code, 200)
        second_review = second_generate.get_json()["review"]
        self.assertTrue(second_review["is_repeat_mistake"])

        listing = self.client.get(f"/api/review-records?user_id={user_id}&limit=5")
        self.assertEqual(listing.status_code, 200)
        records = listing.get_json()["records"]
        self.assertGreaterEqual(len(records), 1)
        self.assertEqual(records[0]["mistake_type"], "审题失误")

    def test_nudge_feedback_summary_tracks_reengagement(self) -> None:
        memory = MemoryService(db_path=os.environ["MINDSHADOW_DB_PATH"])
        user_id = "nudge-feedback-user"
        memory.queue_notification(
            user_id=user_id,
            content="【学习节奏提醒】回来做一道题吧",
            trigger_type="inactivity",
            nudge_level="gentle",
        )
        item = memory.pop_pending_notification(user_id=user_id)
        self.assertIsNotNone(item)
        memory.add_message(user_id=user_id, role="user", content="我回来学习了")
        summary = memory.get_nudge_feedback_summary(user_id=user_id, days=7)
        self.assertGreaterEqual(summary["sent_count"], 1)
        self.assertGreaterEqual(summary["reengaged_count"], 1)
        self.assertGreater(summary["reengagement_rate"], 0)

    def test_queue_notification_deduplicates_recent_same_content(self) -> None:
        memory = MemoryService(db_path=os.environ["MINDSHADOW_DB_PATH"])
        user_id = "nudge-dedupe-user"
        content = "【学习节奏提醒】你最近在练教育学，来个30秒小挑战？"
        memory.queue_notification(
            user_id=user_id,
            content=content,
            trigger_type="inactivity",
            nudge_level="focus",
        )
        memory.queue_notification(
            user_id=user_id,
            content=content,
            trigger_type="inactivity",
            nudge_level="focus",
        )
        first = memory.pop_pending_notification(user_id=user_id)
        second = memory.pop_pending_notification(user_id=user_id)
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_nudge_strategy_summary_flow(self) -> None:
        memory = MemoryService(db_path=os.environ["MINDSHADOW_DB_PATH"])
        user_id = "nudge-strategy-user"
        memory.queue_notification(
            user_id=user_id,
            content="【错题反复预警】先做一道同类题",
            trigger_type="repeat_mistake",
            nudge_level="focus",
        )
        sent = memory.pop_pending_notification(user_id=user_id)
        self.assertIsNotNone(sent)
        memory.add_message(user_id=user_id, role="user", content="我回来了，继续刷错题")
        strategy = self.client.get(f"/api/nudge/strategy?user_id={user_id}&days=14")
        self.assertEqual(strategy.status_code, 200)
        payload = strategy.get_json()["summary"]
        self.assertIn("overall", payload)
        self.assertIn("strategies", payload)
        self.assertGreaterEqual(payload["overall"]["sent_count"], 1)
        self.assertGreaterEqual(len(payload["strategies"]), 1)
        self.assertEqual(payload["strategies"][0]["trigger_type"], "repeat_mistake")

    def test_sentence_transformer_provider_falls_back_to_hash_embedding(self) -> None:
        memory = MemoryService(db_path=os.environ["MINDSHADOW_DB_PATH"])
        memory.embedding_provider = "sentence_transformers"
        memory.embedding_model_name = "__invalid_model_name__"
        vector = memory._text_to_embedding("教育目的与课程设计")
        self.assertGreaterEqual(len(vector), 32)
        self.assertLessEqual(len(vector), 512)
        self.assertTrue(any(abs(float(value)) > 0 for value in vector))

    def test_memory_debug_contains_semantic_stats(self) -> None:
        user_id = "semantic-stats-user"
        self.client.post(
            "/api/memory-cards",
            json={
                "user_id": user_id,
                "card": {
                    "title": "课程设计重点",
                    "content": "课程设计常见题型是目标、内容、评价",
                    "tags": ["课程设计", "题型"],
                },
            },
        )
        response = self.client.post(
            "/api/chat",
            json={
                "text": "课程设计题型怎么答",
                "user_id": user_id,
                "include_memory_debug": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("memory_debug", payload)
        self.assertIn("semantic_stats", payload["memory_debug"])
        semantic_stats = payload["memory_debug"]["semantic_stats"]
        self.assertIn("result_count", semantic_stats)
        self.assertIn("avg_vector_similarity", semantic_stats)

    def test_scheduler_supports_exam_and_repeat_triggers(self) -> None:
        memory = MemoryService(db_path=os.environ["MINDSHADOW_DB_PATH"])
        llm = LLMService()
        scheduler = ProactiveScheduler(memory_service=memory, llm_service=llm)
        scheduler.dnd_start = 24
        scheduler.dnd_end = 0
        user_id = "trigger-user"
        memory.add_message(user_id=user_id, role="user", content="今天继续复习")
        near_exam = (datetime.now(UTC).date() + timedelta(days=2)).isoformat()
        memory.upsert_user_profile(user_id=user_id, payload={"exam_date": near_exam, "exam_goal": "80+"})
        scheduler._nudge_job()
        exam_item = memory.pop_pending_notification(user_id=user_id)
        self.assertIsNotNone(exam_item)
        self.assertIn("考前窗口提醒", str(exam_item["content"]))

        memory.upsert_user_profile(user_id=user_id, payload={"exam_date": "", "exam_goal": "80+"})
        memory.create_review_record(
            user_id=user_id,
            payload={
                "focus_topic": "教育学",
                "source_question": "第一次错在审题",
                "mistake_type": "审题失误",
                "reason": "关键词没抓住",
                "fix_action": "先圈关键词",
                "next_drill": "做同类题1道",
            },
        )
        memory.create_review_record(
            user_id=user_id,
            payload={
                "focus_topic": "教育学",
                "source_question": "第二次还是审题偏差",
                "mistake_type": "审题失误",
                "reason": "逻辑顺序错位",
                "fix_action": "先列框架再答题",
                "next_drill": "做同类题2道",
            },
        )
        memory.create_review_record(
            user_id=user_id,
            payload={
                "focus_topic": "教育学",
                "source_question": "第三次仍然审题错误",
                "mistake_type": "审题失误",
                "reason": "审题速度过快",
                "fix_action": "先读题干再看选项",
                "next_drill": "做同类题3道",
            },
        )
        trigger_context = scheduler._resolve_trigger_context(user_id=user_id, now=datetime.now(UTC))
        self.assertIsNotNone(trigger_context)
        self.assertEqual(trigger_context["trigger_type"], "repeat_mistake")

    def test_weekly_report_generate_and_query_flow(self) -> None:
        user_id = "weekly-user"
        today = datetime.now(UTC).date()
        week_start = (today - timedelta(days=today.weekday())).isoformat()
        week_end = (today + timedelta(days=6 - today.weekday())).isoformat()
        plan_date = today.isoformat()

        plan = self.client.post("/api/study-plan/generate", json={"user_id": user_id, "date": plan_date})
        self.assertEqual(plan.status_code, 200)
        checkin = self.client.post(
            "/api/study-plan/checkin",
            json={"user_id": user_id, "date": plan_date, "completed_tasks": 3},
        )
        self.assertEqual(checkin.status_code, 200)
        review = self.client.post(
            "/api/review-template/generate",
            json={
                "user_id": user_id,
                "focus_topic": "教育心理学",
                "source_question": "我这题总是时间不够，后半部分写不完",
            },
        )
        self.assertEqual(review.status_code, 200)

        generate = self.client.post(
            "/api/weekly-report/generate",
            json={"user_id": user_id, "week_start": week_start, "week_end": week_end},
        )
        self.assertEqual(generate.status_code, 200)
        generated_payload = generate.get_json()
        report = generated_payload["report"]
        self.assertIn("summary", report)
        self.assertEqual(len(report["highlights"]), 3)
        self.assertEqual(len(report["next_week_focus"]), 3)
        self.assertIn("stats_snapshot", report)
        self.assertGreaterEqual(int(report["stats_snapshot"]["plan_days"]), 1)
        self.assertGreaterEqual(int(report["stats_snapshot"]["review_count"]), 1)
        self.assertIn("task_completion_rate", report["stats_snapshot"])
        self.assertIn("repeat_mistake_rate", report["stats_snapshot"])
        self.assertIn("is_task_completion_target_met", report["stats_snapshot"])
        self.assertIn("is_repeat_mistake_target_met", report["stats_snapshot"])
        self.assertIn("is_weekly_goal_met", report["stats_snapshot"])
        self.assertIn("nudge_reengagement_rate_7d", report["stats_snapshot"])
        self.assertTrue(report["stats_snapshot"]["is_task_completion_target_met"])
        self.assertFalse(report["stats_snapshot"]["is_repeat_mistake_target_met"])
        self.assertFalse(report["stats_snapshot"]["is_weekly_goal_met"])
        self.assertIn("本周核心目标判定", report["summary"])

        query = self.client.get(
            f"/api/weekly-report?user_id={user_id}&week_start={week_start}&week_end={week_end}"
        )
        self.assertEqual(query.status_code, 200)
        queried = query.get_json()["report"]
        self.assertEqual(queried["week_start"], week_start)
        self.assertEqual(queried["week_end"], week_end)

    def test_evaluation_cases_and_score_flow(self) -> None:
        cases_resp = self.client.get("/api/eval/cases?limit=5")
        self.assertEqual(cases_resp.status_code, 200)
        cases_payload = cases_resp.get_json()
        self.assertGreaterEqual(len(cases_payload["cases"]), 1)
        case_id = cases_payload["cases"][0]["id"]
        score_resp = self.client.post(
            "/api/eval/score",
            json={
                "user_id": "eval-user",
                "case_id": case_id,
                "variant_label": "baseline",
                "answer": "先给结论，再给步骤，最后提醒易错点并做一道限时练习。",
            },
        )
        self.assertEqual(score_resp.status_code, 200)
        score_payload = score_resp.get_json()
        self.assertIn("run", score_payload)
        self.assertIn("score_detail", score_payload["run"])
        self.assertIn("total_score", score_payload["run"]["score_detail"])

    def test_evaluation_ab_compare_flow(self) -> None:
        cases_resp = self.client.get("/api/eval/cases?limit=1")
        self.assertEqual(cases_resp.status_code, 200)
        case_id = cases_resp.get_json()["cases"][0]["id"]
        compare_resp = self.client.post(
            "/api/eval/ab-compare",
            json={
                "user_id": "eval-ab-user",
                "case_id": case_id,
                "label_a": "PromptA",
                "label_b": "PromptB",
                "answer_a": "先说核心结论，再分三步，最后给一个错因提醒。",
                "answer_b": "我觉得大概这样，可能可以试试。",
            },
        )
        self.assertEqual(compare_resp.status_code, 200)
        compare_payload = compare_resp.get_json()
        self.assertIn("winner", compare_payload)
        self.assertIn("run_a", compare_payload)
        self.assertIn("run_b", compare_payload)
        self.assertIn("delta", compare_payload)

    def test_evaluation_trend_flow(self) -> None:
        user_id = "eval-trend-user"
        cases_resp = self.client.get("/api/eval/cases?limit=1")
        self.assertEqual(cases_resp.status_code, 200)
        case_id = cases_resp.get_json()["cases"][0]["id"]
        first = self.client.post(
            "/api/eval/score",
            json={
                "user_id": user_id,
                "case_id": case_id,
                "variant_label": "PromptA",
                "answer": "先结论，再步骤，最后复盘错因并做限时练习。",
            },
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            "/api/eval/score",
            json={
                "user_id": user_id,
                "case_id": case_id,
                "variant_label": "PromptB",
                "answer": "先解释背景，然后给例子。",
            },
        )
        self.assertEqual(second.status_code, 200)
        trend = self.client.get(f"/api/eval/trends?user_id={user_id}&limit=20")
        self.assertEqual(trend.status_code, 200)
        summary = trend.get_json()["summary"]
        self.assertGreaterEqual(int(summary["total_runs"]), 2)
        self.assertGreaterEqual(len(summary["variants"]), 2)
        self.assertIn("best_variant", summary)


if __name__ == "__main__":
    unittest.main()
