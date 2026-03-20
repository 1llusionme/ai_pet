import os
import time
import uuid
import json
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory, stream_with_context
from werkzeug.exceptions import HTTPException

from server.services.knowledge_base import KnowledgeBaseService
from server.services.llm import LLMService
from server.services.memory import MemoryService
from server.services.scheduler import ProactiveScheduler


def load_local_env_file() -> None:
    env_path = Path(__file__).resolve().parent / ".env.local"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def create_app() -> Flask:
    load_local_env_file()
    app = Flask(__name__)
    memory_service = MemoryService(db_path=os.getenv("MINDSHADOW_DB_PATH", "mindshadow.db"))
    llm_service = LLMService()
    default_kb_path = Path(__file__).resolve().parent / "knowledge_base" / "teaching_exam_kb.json"
    knowledge_service = KnowledgeBaseService(kb_path=os.getenv("MINDSHADOW_KB_PATH", str(default_kb_path)))
    scheduler = ProactiveScheduler(memory_service=memory_service, llm_service=llm_service)
    scheduler.start()
    uploads_dir = Path(os.getenv("MINDSHADOW_UPLOAD_DIR", str(Path(__file__).resolve().parent / "uploads")))
    web_project_root = Path(__file__).resolve().parent.parent / "docs" / "idea2mvp"
    web_dist_dir = web_project_root / "ai_teacherexam" / "dist"
    if not web_dist_dir.exists():
        web_dist_dir = web_project_root / "teacherexam_ai" / "dist"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    rate_limit_max_requests = int(os.getenv("MINDSHADOW_RATE_LIMIT_MAX_REQUESTS_PER_MINUTE", "20"))
    rate_limit_window_seconds = 60
    user_request_windows: dict[str, deque[float]] = defaultdict(deque)
    rate_limit_lock = Lock()
    metrics_lock = Lock()
    metrics: dict[str, Any] = {
        "chat_requests": 0,
        "ingest_requests": 0,
        "study_plan_requests": 0,
        "study_checkin_requests": 0,
        "review_requests": 0,
        "weekly_report_requests": 0,
        "eval_score_requests": 0,
        "eval_compare_requests": 0,
        "eval_trend_requests": 0,
        "nudge_strategy_requests": 0,
        "rate_limited_requests": 0,
        "remote_replies": 0,
        "mock_replies": 0,
        "image_upload_requests": 0,
        "vision_requests": 0,
        "search_requests": 0,
        "memory_recall_summary_requests": 0,
        "analytics_event_requests": 0,
        "learning_export_requests": 0,
        "errors": 0,
        "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    ops_token = str(os.getenv("MINDSHADOW_OPS_TOKEN", "")).strip()
    memory_debug_enabled = str(os.getenv("MINDSHADOW_MEMORY_DEBUG_ENABLED", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    hybrid_recall_enabled = str(os.getenv("MINDSHADOW_HYBRID_RECALL_ENABLED", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    raw_hybrid_ratio = str(os.getenv("MINDSHADOW_HYBRID_RECALL_RATIO", "0")).strip()
    try:
        hybrid_recall_ratio = min(max(float(raw_hybrid_ratio), 0.0), 1.0)
    except ValueError:
        hybrid_recall_ratio = 0.0
    raw_whitelist = str(os.getenv("MINDSHADOW_HYBRID_RECALL_WHITELIST", "")).strip()
    hybrid_whitelist = {item.strip() for item in raw_whitelist.split(",") if item.strip()}
    hybrid_config: dict[str, Any] = {
        "enabled": hybrid_recall_enabled,
        "ratio": hybrid_recall_ratio,
        "top_k": 3,
        "time_decay_days": 14.0,
        "freshness_weight": 0.2,
        "semantic_weight": 0.55,
        "min_similarity": 0.12,
        "source_weights": {
            "message": 1.0,
            "review": 1.05,
            "memory_card": 1.1,
        },
    }

    def track_metric(name: str) -> None:
        with metrics_lock:
            metrics[name] = int(metrics.get(name, 0)) + 1
            metrics["last_updated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def record_mode(mode: str) -> None:
        if mode == "remote":
            track_metric("remote_replies")
        else:
            track_metric("mock_replies")

    def ensure_rate_limit(user_id: str):
        now = time.time()
        with rate_limit_lock:
            bucket = user_request_windows[user_id]
            while bucket and now - bucket[0] > rate_limit_window_seconds:
                bucket.popleft()
            if len(bucket) >= rate_limit_max_requests:
                retry_after = max(1, int(rate_limit_window_seconds - (now - bucket[0])))
                return False, retry_after
            bucket.append(now)
            return True, 0

    def resolve_week_range(raw_start: str, raw_end: str) -> tuple[str, str]:
        start = str(raw_start).strip()
        end = str(raw_end).strip()
        if start and end:
            return start, end
        today = datetime.now(timezone.utc).date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return monday.isoformat(), sunday.isoformat()

    def require_ops_token() -> bool:
        if not ops_token:
            return True
        token = str(request.headers.get("X-Ops-Token", "")).strip()
        return token == ops_token

    def include_memory_debug(payload: dict[str, Any]) -> bool:
        if memory_debug_enabled:
            return True
        raw = payload.get("include_memory_debug", False)
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def profile_fields_used(user_profile: dict[str, Any]) -> list[str]:
        fields: list[str] = []
        for field in ("exam_goal", "exam_date", "response_style", "weak_points", "study_schedule", "motivation_note"):
            value = user_profile.get(field)
            if isinstance(value, list):
                if value:
                    fields.append(field)
                continue
            if str(value or "").strip():
                fields.append(field)
        return fields

    def build_memory_debug_payload(
        mode: str,
        recent_messages: list[dict[str, Any]],
        user_profile: dict[str, Any],
        web_context: list[dict[str, Any]],
        kb_context: list[dict[str, Any]],
        semantic_context: list[dict[str, Any]],
        hybrid_used: bool,
        hybrid_fallback_reason: str,
    ) -> dict[str, Any]:
        sources: list[str] = []
        if recent_messages:
            sources.append("recent")
        fields_used = profile_fields_used(user_profile=user_profile)
        if fields_used:
            sources.append("profile")
        if kb_context:
            sources.append("kb")
        if semantic_context:
            sources.append("semantic")
        if web_context:
            sources.append("web")
        fallback_reason = ""
        if mode != "remote":
            fallback_reason = "mock_fallback"
        elif not sources:
            fallback_reason = "no_relevant_memory"
        if hybrid_used and not semantic_context and hybrid_fallback_reason:
            fallback_reason = hybrid_fallback_reason
        semantic_scores = [float(item.get("score", 0.0) or 0.0) for item in semantic_context]
        vector_scores = [float(item.get("vector_similarity", 0.0) or 0.0) for item in semantic_context]
        source_type_counts: dict[str, int] = {}
        for item in semantic_context:
            source_type = str(item.get("source_type", "")).strip() or "unknown"
            source_type_counts[source_type] = int(source_type_counts.get(source_type, 0)) + 1
        semantic_stats = {
            "result_count": len(semantic_context),
            "avg_score": round(sum(semantic_scores) / len(semantic_scores), 6) if semantic_scores else 0.0,
            "top_score": round(max(semantic_scores), 6) if semantic_scores else 0.0,
            "avg_vector_similarity": round(sum(vector_scores) / len(vector_scores), 6) if vector_scores else 0.0,
            "source_type_counts": source_type_counts,
        }
        return {
            "memory_sources_used": sources,
            "profile_fields_used": fields_used,
            "fallback_reason": fallback_reason,
            "hybrid_used": hybrid_used,
            "semantic_stats": semantic_stats,
        }

    def build_memory_explanation_card(
        memory_debug_payload: dict[str, Any],
        semantic_context: list[dict[str, Any]],
        kb_context: list[dict[str, Any]],
    ) -> dict[str, Any]:
        memory_sources = list(memory_debug_payload.get("memory_sources_used", []))
        profile_fields = list(memory_debug_payload.get("profile_fields_used", []))
        references: list[dict[str, Any]] = []
        for item in semantic_context[:3]:
            references.append(
                {
                    "type": "semantic",
                    "title": str(item.get("title", "")),
                    "source_type": str(item.get("source_type", "")),
                    "score": float(item.get("score", 0.0) or 0.0),
                }
            )
        for item in kb_context[:2]:
            references.append(
                {
                    "type": "kb",
                    "title": str(item.get("title", "")),
                    "page": str(item.get("page", "")),
                }
            )
        return {
            "memory_sources": memory_sources,
            "profile_fields": profile_fields,
            "references": references,
            "fallback_reason": str(memory_debug_payload.get("fallback_reason", "")),
        }

    def include_memory_explanation(payload: dict[str, Any]) -> bool:
        raw = payload.get("include_memory_explanation", False)
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}

    def normalize_quote(raw_value: Any, limit: int = 220) -> str:
        cleaned = re.sub(r"\s+", " ", str(raw_value or "").strip())
        return cleaned[:limit]

    def normalize_conversation_id(raw_value: Any) -> str:
        normalized = str(raw_value or "").strip()
        if not normalized:
            return "default"
        safe = re.sub(r"[^a-zA-Z0-9_-]", "-", normalized)
        safe = re.sub(r"-{2,}", "-", safe).strip("-")
        return safe[:64] or "default"

    def to_citations(
        web_context: list[dict[str, Any]],
        kb_context: list[dict[str, Any]],
        semantic_context: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for item in kb_context:
            quote = normalize_quote(item.get("snippet", ""))
            if not quote:
                continue
            citations.append(
                {
                    "source_type": "kb",
                    "source_label": "知识库",
                    "title": str(item.get("title", "")).strip() or "本地知识库",
                    "page": str(item.get("page", "")).strip(),
                    "url": "",
                    "quote": quote,
                }
            )
        for item in semantic_context:
            quote = normalize_quote(item.get("snippet", ""))
            if not quote:
                continue
            source_type = str(item.get("source_type", "")).strip() or "message"
            label_map = {
                "message": "历史消息",
                "review": "复盘记录",
                "memory_card": "记忆卡片",
            }
            citations.append(
                {
                    "source_type": "semantic",
                    "source_label": "历史记忆引用",
                    "semantic_source_type": source_type,
                    "semantic_source_label": label_map.get(source_type, "历史记忆"),
                    "title": str(item.get("title", "")).strip() or label_map.get(source_type, "历史记忆"),
                    "page": "",
                    "url": "",
                    "quote": quote,
                }
            )
        for item in web_context:
            quote = normalize_quote(item.get("snippet", ""))
            if not quote:
                continue
            citations.append(
                {
                    "source_type": "web",
                    "source_label": "联网检索",
                    "title": str(item.get("title", "")).strip() or "联网来源",
                    "page": "",
                    "url": str(item.get("url", "")).strip(),
                    "quote": quote,
                }
            )
        return citations[:5]

    def parse_small_number_token(token: str) -> int | None:
        normalized = str(token or "").strip()
        if not normalized:
            return None
        if normalized.isdigit():
            number = int(normalized)
            return number if 2 <= number <= 20 else None
        digits = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
        if normalized == "十":
            return 10
        if "十" in normalized:
            parts = normalized.split("十", 1)
            left = 1 if parts[0] == "" else digits.get(parts[0])
            right = 0 if parts[1] == "" else digits.get(parts[1])
            if left is None or right is None:
                return None
            number = left * 10 + right
            return number if 2 <= number <= 20 else None
        number = digits.get(normalized)
        if number is None:
            return None
        return number if 2 <= number <= 20 else None

    def detect_citation_conflict(citations: list[dict[str, Any]]) -> bool:
        if len(citations) < 2:
            return False
        token_pattern = re.compile(r"\d+|[一二三四五六七八九十两]{1,3}")
        number_by_source: dict[str, set[int]] = defaultdict(set)
        for index, citation in enumerate(citations):
            quote = str(citation.get("quote", ""))
            if not quote:
                continue
            source_key = f"{citation.get('source_type', 'unknown')}:{index}"
            for token in token_pattern.findall(quote):
                parsed = parse_small_number_token(token)
                if parsed is not None:
                    number_by_source[source_key].add(parsed)
        all_numbers = {number for values in number_by_source.values() for number in values}
        if len(all_numbers) < 2:
            return False
        sources_with_numbers = [values for values in number_by_source.values() if values]
        return len(sources_with_numbers) >= 2

    def build_citation_summary(citations: list[dict[str, Any]]) -> dict[str, Any]:
        source_types = {str(item.get("source_type", "")).strip() for item in citations}
        return {
            "total": len(citations),
            "has_kb": "kb" in source_types,
            "has_semantic": "semantic" in source_types,
            "has_web": "web" in source_types,
            "has_conflict": detect_citation_conflict(citations),
        }

    def should_use_hybrid_recall(user_id: str, payload: dict[str, Any]) -> bool:
        if not bool(hybrid_config.get("enabled", False)):
            return False
        if user_id in hybrid_whitelist:
            return True
        force_raw = payload.get("force_hybrid_recall", False)
        force_value = force_raw if isinstance(force_raw, bool) else str(force_raw).strip().lower() in {"1", "true", "yes", "on"}
        if force_value and require_ops_token():
            return True
        ratio = min(max(float(hybrid_config.get("ratio", 0.0) or 0.0), 0.0), 1.0)
        if ratio <= 0:
            return False
        bucket = (sum(ord(char) for char in user_id) % 1000) / 1000
        return bucket < ratio

    def readiness_snapshot() -> dict[str, Any]:
        db_ok = True
        db_error = ""
        try:
            memory_service.get_recent_messages(user_id="default", limit=1)
        except Exception as exc:
            db_ok = False
            db_error = str(exc)
        kb_ok = bool(getattr(knowledge_service, "documents", []))
        uploads_ok = uploads_dir.exists() and os.access(uploads_dir, os.W_OK)
        scheduler_ok = bool(scheduler.scheduler.running)
        checks = {
            "db": {"ok": db_ok, "error": db_error or None},
            "kb": {"ok": kb_ok, "documents": len(getattr(knowledge_service, "documents", []))},
            "uploads": {"ok": uploads_ok, "path": str(uploads_dir)},
            "scheduler": {"ok": scheduler_ok},
        }
        overall_ok = all(bool(item.get("ok")) for item in checks.values())
        return {"ok": overall_ok, "checks": checks}

    @app.before_request
    def attach_request_id():
        request_id = str(request.headers.get("X-Request-ID", "")).strip()
        if not request_id:
            request_id = uuid.uuid4().hex
        g.request_id = request_id

    @app.after_request
    def add_cors_headers(response):
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Ops-Token, X-Request-ID"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        return response

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        if isinstance(exc, HTTPException):
            track_metric("errors")
            return (
                jsonify(
                    {
                        "error": str(exc.description),
                        "request_id": getattr(g, "request_id", ""),
                    }
                ),
                int(exc.code or 500),
            )
        app.logger.exception("[error] request_id=%s", getattr(g, "request_id", ""))
        track_metric("errors")
        return (
            jsonify(
                {
                    "error": "服务内部异常，请稍后再试",
                    "request_id": getattr(g, "request_id", ""),
                }
            ),
            500,
        )

    @app.route("/api/health", methods=["GET"])
    def health():
        with metrics_lock:
            current_metrics = dict(metrics)
        return jsonify(
            {
                "status": "ok",
                "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "llm": llm_service.status(),
                "metrics": current_metrics,
            }
        )

    @app.route("/api/ready", methods=["GET"])
    def ready():
        snapshot = readiness_snapshot()
        status_code = 200 if snapshot["ok"] else 503
        return jsonify(snapshot), status_code

    @app.route("/api/ops/metrics", methods=["GET"])
    def ops_metrics():
        if not require_ops_token():
            track_metric("errors")
            return jsonify({"error": "forbidden"}), 403
        with metrics_lock:
            current_metrics = dict(metrics)
        return jsonify(
            {
                "time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "metrics": current_metrics,
            }
        )

    @app.route("/api/ops/persona-config", methods=["GET", "OPTIONS", "POST"])
    def ops_persona_config():
        if request.method == "OPTIONS":
            return ("", 204)
        if not require_ops_token():
            track_metric("errors")
            return jsonify({"error": "forbidden"}), 403
        if request.method == "GET":
            return jsonify(llm_service.persona_config_status())
        payload = request.get_json(silent=True) or {}
        config_payload = payload.get("config", payload)
        if not isinstance(config_payload, dict):
            track_metric("errors")
            return jsonify({"error": "config must be an object"}), 400
        try:
            updated = llm_service.update_persona_config(config_payload)
        except ValueError as exc:
            track_metric("errors")
            return jsonify({"error": str(exc)}), 400
        return jsonify({"config": updated, "path": llm_service.persona_config_status().get("path", "")})

    @app.route("/api/memory/hybrid-config", methods=["GET", "OPTIONS", "POST"])
    def memory_hybrid_config():
        if request.method == "OPTIONS":
            return ("", 204)
        if request.method == "GET":
            return jsonify(
                {
                    "hybrid_config": {
                        **hybrid_config,
                        "whitelist_size": len(hybrid_whitelist),
                    }
                }
            )
        if not require_ops_token():
            track_metric("errors")
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        enabled = payload.get("enabled")
        ratio = payload.get("ratio")
        top_k = payload.get("top_k")
        time_decay_days = payload.get("time_decay_days")
        freshness_weight = payload.get("freshness_weight")
        semantic_weight = payload.get("semantic_weight")
        min_similarity = payload.get("min_similarity")
        source_weights = payload.get("source_weights")
        if enabled is not None:
            hybrid_config["enabled"] = bool(enabled)
        if ratio is not None:
            hybrid_config["ratio"] = min(max(float(ratio), 0.0), 1.0)
        if top_k is not None:
            hybrid_config["top_k"] = max(1, min(int(top_k), 8))
        if time_decay_days is not None:
            hybrid_config["time_decay_days"] = max(1.0, min(float(time_decay_days), 90.0))
        if freshness_weight is not None:
            hybrid_config["freshness_weight"] = min(max(float(freshness_weight), 0.0), 0.8)
        if semantic_weight is not None:
            hybrid_config["semantic_weight"] = min(max(float(semantic_weight), 0.0), 0.9)
        if min_similarity is not None:
            hybrid_config["min_similarity"] = min(max(float(min_similarity), 0.0), 0.9)
        if isinstance(source_weights, dict):
            normalized_weights: dict[str, float] = {}
            for key, value in source_weights.items():
                name = str(key).strip()
                if not name:
                    continue
                normalized_weights[name] = max(0.1, min(float(value), 2.0))
            if normalized_weights:
                hybrid_config["source_weights"] = normalized_weights
        return jsonify({"hybrid_config": {**hybrid_config, "whitelist_size": len(hybrid_whitelist)}})

    @app.route("/api/memory/embedding-config", methods=["GET", "OPTIONS", "POST"])
    def memory_embedding_config():
        if request.method == "OPTIONS":
            return ("", 204)
        if request.method == "GET":
            return jsonify({"embedding_config": memory_service.embedding_runtime_status()})
        if not require_ops_token():
            track_metric("errors")
            return jsonify({"error": "forbidden"}), 403
        payload = request.get_json(silent=True) or {}
        provider = str(payload.get("provider", "")).strip()
        model_name = payload.get("model")
        if not provider:
            provider = str(memory_service.embedding_runtime_status().get("provider", "hash"))
        updated = memory_service.set_embedding_runtime(provider=provider, model_name=model_name)
        reindex_requested = payload.get("reindex", False)
        reindex_value = reindex_requested if isinstance(reindex_requested, bool) else str(reindex_requested).strip().lower() in {"1", "true", "yes", "on"}
        reindex_user_id = str(payload.get("reindex_user_id", "")).strip()
        reindex_result: dict[str, Any] = {}
        if reindex_value or reindex_user_id:
            reindex_result = memory_service.reindex_semantic_vectors(user_id=reindex_user_id or None)
        return jsonify(
            {
                "embedding_config": updated,
                "reindex": reindex_result,
            }
        )

    @app.route("/api/ops/recall-dashboard", methods=["GET", "OPTIONS"])
    def recall_dashboard():
        if request.method == "OPTIONS":
            return ("", 204)
        if not require_ops_token():
            track_metric("errors")
            return jsonify({"error": "forbidden"}), 403
        user_id = str(request.args.get("user_id", "default")).strip() or "default"
        days = int(request.args.get("days", 14))
        week_start, week_end = resolve_week_range(
            request.args.get("week_start", ""),
            request.args.get("week_end", ""),
        )
        recall_summary = memory_service.summarize_recall_events(user_id=user_id, days=days, limit=400)
        answer_quality_summary = memory_service.summarize_answer_render_events(user_id=user_id, days=days, limit=800)
        nudge_summary = memory_service.summarize_nudge_strategy(user_id=user_id, days=days)
        weekly_stats = memory_service.aggregate_weekly_learning(
            user_id=user_id,
            week_start=week_start,
            week_end=week_end,
        )
        return jsonify(
            {
                "user_id": user_id,
                "days": days,
                "week_start": week_start,
                "week_end": week_end,
                "recall": recall_summary,
                "answer_quality": answer_quality_summary,
                "nudge": nudge_summary,
                "weekly_learning": weekly_stats,
            }
        )

    @app.route("/api/analytics/events", methods=["OPTIONS", "POST"])
    def analytics_events():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "default")).strip() or "default"
        event_name = str(payload.get("event_name", "")).strip()
        event_payload = payload.get("event_payload")
        if not event_name:
            track_metric("errors")
            return jsonify({"error": "event_name is required"}), 400
        normalized_payload = event_payload if isinstance(event_payload, dict) else {}
        memory_service.log_answer_render_event(
            user_id=user_id,
            event_name=event_name,
            payload=normalized_payload,
        )
        track_metric("analytics_event_requests")
        return jsonify(
            {
                "ok": True,
                "event_name": event_name,
            }
        )

    @app.route("/api/chat", methods=["OPTIONS", "POST"])
    def chat():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text", "")).strip()
        user_id = str(payload.get("user_id", "default"))
        conversation_id = normalize_conversation_id(payload.get("conversation_id", "default"))
        if not text:
            track_metric("errors")
            return jsonify({"error": "text is required"}), 400
        allowed, retry_after = ensure_rate_limit(user_id)
        if not allowed:
            track_metric("rate_limited_requests")
            response = jsonify({"error": "请求过于频繁，请稍后再试", "retry_after_seconds": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response

        track_metric("chat_requests")
        web_context = llm_service.search_web_context(text)
        if web_context:
            track_metric("search_requests")
        kb_context = knowledge_service.search(query=text, top_k=3)
        semantic_context: list[dict[str, Any]] = []
        hybrid_used = should_use_hybrid_recall(user_id=user_id, payload=payload)
        hybrid_fallback_reason = ""
        if hybrid_used:
            try:
                semantic_context = memory_service.hybrid_semantic_recall(
                    user_id=user_id,
                    query_text=text,
                    top_k=int(hybrid_config.get("top_k", 3)),
                    time_decay_days=float(hybrid_config.get("time_decay_days", 14.0)),
                    freshness_weight=float(hybrid_config.get("freshness_weight", 0.2)),
                    semantic_weight=float(hybrid_config.get("semantic_weight", 0.55)),
                    min_similarity=float(hybrid_config.get("min_similarity", 0.12)),
                    source_weights=hybrid_config.get("source_weights", {}),
                )
            except Exception:
                semantic_context = []
                hybrid_fallback_reason = "hybrid_fallback"
        memory_service.add_message(user_id=user_id, role="user", content=text, conversation_id=conversation_id)
        memory_service.auto_update_profile_from_message(user_id=user_id, message=text)
        recent_messages = memory_service.get_recent_messages(user_id=user_id, limit=10)
        focus_topic = memory_service.get_focus_topic(user_id=user_id)
        user_profile = memory_service.get_user_profile(user_id=user_id)
        ai_reply = llm_service.chat(
            recent_messages=recent_messages,
            focus_topic=focus_topic,
            web_context=web_context,
            kb_context=kb_context,
            semantic_context=semantic_context,
            user_profile=user_profile,
        )
        memory_service.add_message(user_id=user_id, role="ai", content=ai_reply, conversation_id=conversation_id)
        mode = str(llm_service.status().get("last_response_source", "mock"))
        memory_debug_payload = build_memory_debug_payload(
            mode=mode,
            recent_messages=recent_messages,
            user_profile=user_profile,
            web_context=web_context,
            kb_context=kb_context,
            semantic_context=semantic_context,
            hybrid_used=hybrid_used,
            hybrid_fallback_reason=hybrid_fallback_reason,
        )
        memory_service.log_recall_event(
            user_id=user_id,
            channel="chat",
            mode=mode,
            query_text=text,
            memory_sources_used=memory_debug_payload["memory_sources_used"],
            profile_fields_used=memory_debug_payload["profile_fields_used"],
            fallback_reason=memory_debug_payload["fallback_reason"],
            search_used=bool(web_context),
            kb_used=bool(kb_context),
            response_chars=len(ai_reply),
        )
        record_mode(mode)
        app.logger.info("[chat] user_id=%s conversation_id=%s mode=%s chars=%s", user_id, conversation_id, mode, len(text))
        citations = to_citations(
            web_context=web_context,
            kb_context=kb_context,
            semantic_context=semantic_context,
        )
        response_payload = {
            "reply": ai_reply,
            "mode": mode,
            "search_used": bool(web_context),
            "sources": web_context[:3],
            "kb_used": bool(kb_context),
            "kb_sources": kb_context[:3],
            "semantic_used": bool(semantic_context),
            "semantic_sources": semantic_context[:3],
            "citations": citations,
            "citation_summary": build_citation_summary(citations),
        }
        if include_memory_debug(payload=payload):
            response_payload["memory_debug"] = memory_debug_payload
        if include_memory_explanation(payload=payload):
            response_payload["memory_explanation"] = build_memory_explanation_card(
                memory_debug_payload=memory_debug_payload,
                semantic_context=semantic_context,
                kb_context=kb_context,
            )
        return jsonify(response_payload)

    @app.route("/api/chat/stream", methods=["OPTIONS", "POST"])
    def chat_stream():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text", "")).strip()
        user_id = str(payload.get("user_id", "default"))
        conversation_id = normalize_conversation_id(payload.get("conversation_id", "default"))
        if not text:
            track_metric("errors")
            return jsonify({"error": "text is required"}), 400
        allowed, retry_after = ensure_rate_limit(user_id)
        if not allowed:
            track_metric("rate_limited_requests")
            response = jsonify({"error": "请求过于频繁，请稍后再试", "retry_after_seconds": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response

        track_metric("chat_requests")
        web_context = llm_service.search_web_context(text)
        if web_context:
            track_metric("search_requests")
        kb_context = knowledge_service.search(query=text, top_k=3)
        semantic_context: list[dict[str, Any]] = []
        hybrid_used = should_use_hybrid_recall(user_id=user_id, payload=payload)
        hybrid_fallback_reason = ""
        if hybrid_used:
            try:
                semantic_context = memory_service.hybrid_semantic_recall(
                    user_id=user_id,
                    query_text=text,
                    top_k=int(hybrid_config.get("top_k", 3)),
                    time_decay_days=float(hybrid_config.get("time_decay_days", 14.0)),
                    freshness_weight=float(hybrid_config.get("freshness_weight", 0.2)),
                    semantic_weight=float(hybrid_config.get("semantic_weight", 0.55)),
                    min_similarity=float(hybrid_config.get("min_similarity", 0.12)),
                    source_weights=hybrid_config.get("source_weights", {}),
                )
            except Exception:
                semantic_context = []
                hybrid_fallback_reason = "hybrid_fallback"
        memory_service.add_message(user_id=user_id, role="user", content=text, conversation_id=conversation_id)
        memory_service.auto_update_profile_from_message(user_id=user_id, message=text)
        recent_messages = memory_service.get_recent_messages(user_id=user_id, limit=10)
        focus_topic = memory_service.get_focus_topic(user_id=user_id)
        user_profile = memory_service.get_user_profile(user_id=user_id)
        mode, stream_iter = llm_service.chat_stream(
            recent_messages=recent_messages,
            focus_topic=focus_topic,
            web_context=web_context,
            kb_context=kb_context,
            semantic_context=semantic_context,
            user_profile=user_profile,
        )
        record_mode(mode)
        app.logger.info(
            "[chat_stream] user_id=%s conversation_id=%s mode=%s chars=%s",
            user_id,
            conversation_id,
            mode,
            len(text),
        )

        @stream_with_context
        def generate():
            chunks: list[str] = []
            yield json.dumps(
                {
                    "type": "meta",
                    "mode": mode,
                    "search_used": bool(web_context),
                    "kb_used": bool(kb_context),
                    "semantic_used": bool(semantic_context),
                    **(
                        {"memory_debug": build_memory_debug_payload(
                            mode=mode,
                            recent_messages=recent_messages,
                            user_profile=user_profile,
                            web_context=web_context,
                            kb_context=kb_context,
                            semantic_context=semantic_context,
                            hybrid_used=hybrid_used,
                            hybrid_fallback_reason=hybrid_fallback_reason,
                        )}
                        if include_memory_debug(payload=payload)
                        else {}
                    ),
                },
                ensure_ascii=False,
            ) + "\n"
            for delta in stream_iter:
                if not delta:
                    continue
                chunks.append(delta)
                yield json.dumps({"type": "delta", "delta": delta}, ensure_ascii=False) + "\n"
            reply = "".join(chunks).strip()
            if not reply:
                reply = llm_service.chat(
                    recent_messages=recent_messages,
                    focus_topic=focus_topic,
                    web_context=web_context,
                    kb_context=kb_context,
                    semantic_context=semantic_context,
                    user_profile=user_profile,
                )
            memory_service.add_message(user_id=user_id, role="ai", content=reply, conversation_id=conversation_id)
            final_mode = str(llm_service.status().get("last_response_source", mode))
            memory_debug_payload = build_memory_debug_payload(
                mode=final_mode,
                recent_messages=recent_messages,
                user_profile=user_profile,
                web_context=web_context,
                kb_context=kb_context,
                semantic_context=semantic_context,
                hybrid_used=hybrid_used,
                hybrid_fallback_reason=hybrid_fallback_reason,
            )
            memory_explanation_payload = build_memory_explanation_card(
                memory_debug_payload=memory_debug_payload,
                semantic_context=semantic_context,
                kb_context=kb_context,
            )
            memory_service.log_recall_event(
                user_id=user_id,
                channel="chat_stream",
                mode=final_mode,
                query_text=text,
                memory_sources_used=memory_debug_payload["memory_sources_used"],
                profile_fields_used=memory_debug_payload["profile_fields_used"],
                fallback_reason=memory_debug_payload["fallback_reason"],
                search_used=bool(web_context),
                kb_used=bool(kb_context),
                response_chars=len(reply),
            )
            if final_mode != mode:
                record_mode(final_mode)
            citations = to_citations(
                web_context=web_context,
                kb_context=kb_context,
                semantic_context=semantic_context,
            )
            yield json.dumps(
                {
                    "type": "done",
                    "reply": reply,
                    "mode": final_mode,
                    "search_used": bool(web_context),
                    "sources": web_context[:3],
                    "kb_used": bool(kb_context),
                    "kb_sources": kb_context[:3],
                    "semantic_used": bool(semantic_context),
                    "semantic_sources": semantic_context[:3],
                    "citations": citations,
                    "citation_summary": build_citation_summary(citations),
                    **({"memory_debug": memory_debug_payload} if include_memory_debug(payload=payload) else {}),
                    **(
                        {"memory_explanation": memory_explanation_payload}
                        if include_memory_explanation(payload=payload)
                        else {}
                    ),
                },
                ensure_ascii=False,
            ) + "\n"

        return Response(
            generate(),
            mimetype="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.route("/api/history", methods=["GET"])
    def history():
        user_id = request.args.get("user_id", "default")
        conversation_id = normalize_conversation_id(request.args.get("conversation_id", "default"))
        limit = int(request.args.get("limit", 50))
        messages = memory_service.get_recent_messages(
            user_id=user_id,
            limit=limit,
            conversation_id=conversation_id,
        )
        return jsonify({"messages": messages})

    @app.route("/api/memory/recall-summary", methods=["GET", "OPTIONS"])
    def memory_recall_summary():
        if request.method == "OPTIONS":
            return ("", 204)
        user_id = str(request.args.get("user_id", "default")).strip() or "default"
        days = int(request.args.get("days", 7))
        limit = int(request.args.get("limit", 200))
        summary = memory_service.summarize_recall_events(user_id=user_id, days=days, limit=limit)
        track_metric("memory_recall_summary_requests")
        return jsonify({"user_id": user_id, "summary": summary})

    @app.route("/api/ingest", methods=["OPTIONS", "POST"])
    def ingest():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        content = str(payload.get("content", "")).strip()
        user_id = str(payload.get("user_id", "default"))
        conversation_id = normalize_conversation_id(payload.get("conversation_id", "default"))
        if not content:
            track_metric("errors")
            return jsonify({"error": "content is required"}), 400
        allowed, retry_after = ensure_rate_limit(user_id)
        if not allowed:
            track_metric("rate_limited_requests")
            response = jsonify({"error": "请求过于频繁，请稍后再试", "retry_after_seconds": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response

        track_metric("ingest_requests")
        truncated = content[:5000]
        summary = llm_service.summarize_learning_text(truncated)
        memory_service.add_memory(
            user_id=user_id,
            memory_type="L0_raw",
            content=truncated,
            topic=summary["topic"],
            confusion_risk=summary["confusion_risk"],
        )
        for concept in summary["concepts"]:
            memory_service.add_memory(
                user_id=user_id,
                memory_type="L1_concept",
                content=concept,
                topic=summary["topic"],
                confusion_risk=summary["confusion_risk"],
            )
        ack = llm_service.ingest_ack(topic=summary["topic"], concepts=summary["concepts"])
        memory_service.add_message(
            user_id=user_id,
            role="system",
            content="知识吸收完毕 💖",
            conversation_id=conversation_id,
        )
        memory_service.add_message(user_id=user_id, role="ai", content=ack, conversation_id=conversation_id)
        mode = str(llm_service.status().get("last_response_source", "mock"))
        record_mode(mode)
        app.logger.info("[ingest] user_id=%s mode=%s chars=%s", user_id, mode, len(content))
        return jsonify(
            {
                "topic": summary["topic"],
                "concepts": summary["concepts"],
                "confusion_risk": summary["confusion_risk"],
                "ack": ack,
                "mode": mode,
            }
        )

    @app.route("/api/notifications", methods=["GET"])
    def notifications():
        user_id = request.args.get("user_id", "default")
        item = memory_service.pop_pending_notification(user_id=user_id)
        if item is None:
            return jsonify({"notification": None})
        return jsonify({"notification": item})

    @app.route("/api/nudge/strategy", methods=["GET", "OPTIONS"])
    def nudge_strategy():
        if request.method == "OPTIONS":
            return ("", 204)
        user_id = str(request.args.get("user_id", "default")).strip() or "default"
        days = int(request.args.get("days", 14))
        summary = memory_service.summarize_nudge_strategy(user_id=user_id, days=days)
        track_metric("nudge_strategy_requests")
        return jsonify({"user_id": user_id, "summary": summary})

    @app.route("/api/profile", methods=["GET", "OPTIONS", "POST"])
    def profile():
        if request.method == "OPTIONS":
            return ("", 204)
        if request.method == "GET":
            user_id = str(request.args.get("user_id", "default")).strip() or "default"
            payload = memory_service.get_user_profile(user_id=user_id)
            return jsonify({"user_id": user_id, "profile": payload})
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "default")).strip() or "default"
        profile_payload = payload.get("profile", {})
        if not isinstance(profile_payload, dict):
            track_metric("errors")
            return jsonify({"error": "profile must be an object"}), 400
        updated = memory_service.upsert_user_profile(user_id=user_id, payload=profile_payload)
        return jsonify({"user_id": user_id, "profile": updated})

    @app.route("/api/learning/export-answer", methods=["OPTIONS", "POST"])
    def learning_export_answer():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "default")).strip() or "default"
        source_question = str(payload.get("source_question", "")).strip()
        answer_text = str(payload.get("answer_text", "")).strip()
        if not answer_text:
            track_metric("errors")
            return jsonify({"error": "answer_text is required"}), 400
        try:
            exported = memory_service.export_answer_to_learning_assets(
                user_id=user_id,
                source_question=source_question,
                answer_text=answer_text,
                llm_service=llm_service,
            )
        except ValueError as exc:
            track_metric("errors")
            return jsonify({"error": str(exc)}), 400
        track_metric("learning_export_requests")
        decision = exported.get("export_decision", {}) if isinstance(exported, dict) else {}
        reject_reason = str(decision.get("reject_reason", "")).strip() if isinstance(decision, dict) else ""
        if reject_reason:
            track_metric("learning_card_export_rejected")
        created_count = int(exported.get("term_cards_added", 0) or 0) if isinstance(exported, dict) else 0
        if created_count > 0:
            track_metric("learning_card_created")
        primary_card_type = str(exported.get("primary_card_type", "")).strip() if isinstance(exported, dict) else ""
        if primary_card_type:
            safe_type = re.sub(r"[^a-z_]", "", primary_card_type.lower())
            if safe_type:
                track_metric(f"learning_card_type_{safe_type}")
        return jsonify({"user_id": user_id, "export": exported})

    @app.route("/api/memory-cards", methods=["GET", "OPTIONS", "POST"])
    def memory_cards():
        if request.method == "OPTIONS":
            return ("", 204)
        if request.method == "GET":
            user_id = str(request.args.get("user_id", "default")).strip() or "default"
            include_deleted = str(request.args.get("include_deleted", "false")).lower() == "true"
            limit = int(request.args.get("limit", 50))
            cards = memory_service.list_memory_cards(
                user_id=user_id,
                include_deleted=include_deleted,
                limit=limit,
            )
            return jsonify({"user_id": user_id, "cards": cards})
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "default")).strip() or "default"
        card_payload = payload.get("card", {})
        if not isinstance(card_payload, dict):
            track_metric("errors")
            return jsonify({"error": "card must be an object"}), 400
        try:
            created = memory_service.create_memory_card(user_id=user_id, payload=card_payload)
            return jsonify({"user_id": user_id, "card": created})
        except ValueError as exc:
            track_metric("errors")
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/memory-cards/<card_id>", methods=["OPTIONS", "PATCH", "DELETE"])
    def memory_card_detail(card_id: str):
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", request.args.get("user_id", "default"))).strip() or "default"
        if request.method == "DELETE":
            deleted = memory_service.delete_memory_card(user_id=user_id, card_id=card_id)
            if deleted is None:
                track_metric("errors")
                return jsonify({"error": "memory card not found"}), 404
            return jsonify({"user_id": user_id, "card": deleted})
        card_payload = payload.get("card", {})
        if not isinstance(card_payload, dict):
            track_metric("errors")
            return jsonify({"error": "card must be an object"}), 400
        updated = memory_service.update_memory_card(user_id=user_id, card_id=card_id, payload=card_payload)
        if updated is None:
            track_metric("errors")
            return jsonify({"error": "memory card not found"}), 404
        return jsonify({"user_id": user_id, "card": updated})

    @app.route("/api/memory-cards/<card_id>/rollback", methods=["OPTIONS", "POST"])
    def memory_card_rollback(card_id: str):
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "default")).strip() or "default"
        version_id = payload.get("version_id")
        rollback = memory_service.rollback_memory_card(
            user_id=user_id,
            card_id=card_id,
            version_id=str(version_id).strip() if version_id is not None else None,
        )
        if rollback is None:
            track_metric("errors")
            return jsonify({"error": "rollback target not found"}), 404
        return jsonify({"user_id": user_id, "card": rollback})

    @app.route("/api/study-plan", methods=["GET", "OPTIONS"])
    def study_plan():
        if request.method == "OPTIONS":
            return ("", 204)
        user_id = str(request.args.get("user_id", "default")).strip() or "default"
        plan_date = str(request.args.get("date", "")).strip() or None
        plan = memory_service.get_daily_study_plan(user_id=user_id, plan_date=plan_date)
        return jsonify({"user_id": user_id, "plan": plan})

    @app.route("/api/study-plan/generate", methods=["OPTIONS", "POST"])
    def generate_study_plan():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "default")).strip() or "default"
        plan_date = str(payload.get("date", "")).strip() or None
        allowed, retry_after = ensure_rate_limit(user_id)
        if not allowed:
            track_metric("rate_limited_requests")
            response = jsonify({"error": "请求过于频繁，请稍后再试", "retry_after_seconds": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response
        track_metric("study_plan_requests")
        focus_topic = memory_service.get_focus_topic(user_id=user_id)
        user_profile = memory_service.get_user_profile(user_id=user_id)
        generated = llm_service.generate_daily_plan(focus_topic=focus_topic, user_profile=user_profile)
        try:
            saved = memory_service.upsert_daily_study_plan(user_id=user_id, plan_payload=generated, plan_date=plan_date)
            mode = str(llm_service.status().get("last_response_source", "mock"))
            record_mode(mode)
            return jsonify({"user_id": user_id, "plan": saved, "mode": mode})
        except ValueError as exc:
            track_metric("errors")
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/study-plan/checkin", methods=["OPTIONS", "POST"])
    def study_plan_checkin():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "default")).strip() or "default"
        plan_date = str(payload.get("date", "")).strip()
        if not plan_date:
            track_metric("errors")
            return jsonify({"error": "date is required"}), 400
        completed_tasks = int(payload.get("completed_tasks", 0) or 0)
        note = str(payload.get("note", "")).strip()
        plan = memory_service.get_daily_study_plan(user_id=user_id, plan_date=plan_date)
        if plan is None:
            track_metric("errors")
            return jsonify({"error": "study plan not found"}), 404
        checkin = memory_service.upsert_daily_plan_checkin(
            user_id=user_id,
            plan_date=plan_date,
            completed_tasks=completed_tasks,
            note=note,
        )
        track_metric("study_checkin_requests")
        latest_plan = memory_service.get_daily_study_plan(user_id=user_id, plan_date=plan_date)
        return jsonify({"user_id": user_id, "checkin": checkin, "plan": latest_plan})

    @app.route("/api/review-records", methods=["GET", "OPTIONS"])
    def review_records():
        if request.method == "OPTIONS":
            return ("", 204)
        user_id = str(request.args.get("user_id", "default")).strip() or "default"
        limit = int(request.args.get("limit", 20))
        records = memory_service.list_review_records(user_id=user_id, limit=limit)
        return jsonify({"user_id": user_id, "records": records})

    @app.route("/api/review-template/generate", methods=["OPTIONS", "POST"])
    def generate_review_template():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "default")).strip() or "default"
        source_question = str(payload.get("source_question", "")).strip()
        focus_topic = str(payload.get("focus_topic", "")).strip() or memory_service.get_focus_topic(user_id=user_id)
        if not source_question:
            track_metric("errors")
            return jsonify({"error": "source_question is required"}), 400
        allowed, retry_after = ensure_rate_limit(user_id)
        if not allowed:
            track_metric("rate_limited_requests")
            response = jsonify({"error": "请求过于频繁，请稍后再试", "retry_after_seconds": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response
        track_metric("review_requests")
        user_profile = memory_service.get_user_profile(user_id=user_id)
        template = llm_service.generate_review_template(
            focus_topic=focus_topic,
            source_question=source_question,
            user_profile=user_profile,
        )
        try:
            saved = memory_service.create_review_record(
                user_id=user_id,
                payload={
                    "focus_topic": focus_topic,
                    "source_question": source_question,
                    **template,
                },
            )
            mode = str(llm_service.status().get("last_response_source", "mock"))
            record_mode(mode)
            return jsonify({"user_id": user_id, "review": saved, "mode": mode})
        except ValueError as exc:
            track_metric("errors")
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/weekly-report", methods=["GET", "OPTIONS"])
    def weekly_report():
        if request.method == "OPTIONS":
            return ("", 204)
        user_id = str(request.args.get("user_id", "default")).strip() or "default"
        week_start, week_end = resolve_week_range(
            raw_start=str(request.args.get("week_start", "")),
            raw_end=str(request.args.get("week_end", "")),
        )
        report = memory_service.get_weekly_report(user_id=user_id, week_start=week_start, week_end=week_end)
        return jsonify({"user_id": user_id, "week_start": week_start, "week_end": week_end, "report": report})

    @app.route("/api/weekly-report/generate", methods=["OPTIONS", "POST"])
    def generate_weekly_report():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "default")).strip() or "default"
        week_start, week_end = resolve_week_range(
            raw_start=str(payload.get("week_start", "")),
            raw_end=str(payload.get("week_end", "")),
        )
        allowed, retry_after = ensure_rate_limit(user_id)
        if not allowed:
            track_metric("rate_limited_requests")
            response = jsonify({"error": "请求过于频繁，请稍后再试", "retry_after_seconds": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response
        track_metric("weekly_report_requests")
        weekly_stats = memory_service.aggregate_weekly_learning(
            user_id=user_id,
            week_start=week_start,
            week_end=week_end,
        )
        focus_topic = memory_service.get_focus_topic(user_id=user_id)
        user_profile = memory_service.get_user_profile(user_id=user_id)
        generated = llm_service.generate_weekly_report(
            focus_topic=focus_topic,
            weekly_stats=weekly_stats,
            user_profile=user_profile,
        )
        try:
            saved = memory_service.upsert_weekly_report(
                user_id=user_id,
                week_start=week_start,
                week_end=week_end,
                payload=generated,
                stats_snapshot=weekly_stats,
            )
            mode = str(llm_service.status().get("last_response_source", "mock"))
            record_mode(mode)
            return jsonify(
                {
                    "user_id": user_id,
                    "week_start": week_start,
                    "week_end": week_end,
                    "report": saved,
                    "mode": mode,
                }
            )
        except ValueError as exc:
            track_metric("errors")
            return jsonify({"error": str(exc)}), 400

    @app.route("/api/eval/cases", methods=["GET", "OPTIONS"])
    def eval_cases():
        if request.method == "OPTIONS":
            return ("", 204)
        limit = int(request.args.get("limit", 30))
        cases = memory_service.list_evaluation_cases(limit=limit)
        return jsonify({"cases": cases})

    @app.route("/api/eval/score", methods=["OPTIONS", "POST"])
    def eval_score():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "default")).strip() or "default"
        case_id = str(payload.get("case_id", "")).strip()
        answer = str(payload.get("answer", "")).strip()
        variant_label = str(payload.get("variant_label", "baseline")).strip() or "baseline"
        if not case_id:
            track_metric("errors")
            return jsonify({"error": "case_id is required"}), 400
        if not answer:
            track_metric("errors")
            return jsonify({"error": "answer is required"}), 400
        case = memory_service.get_evaluation_case(case_id=case_id)
        if case is None:
            track_metric("errors")
            return jsonify({"error": "evaluation case not found"}), 404
        user_profile = memory_service.get_user_profile(user_id=user_id)
        score_detail = llm_service.score_answer(
            question=str(case.get("question", "")),
            answer=answer,
            reference_points=case.get("reference_points", []),
            expected_style=str(case.get("expected_style", "")),
            user_profile=user_profile,
        )
        try:
            run = memory_service.create_evaluation_run(
                user_id=user_id,
                case_id=case_id,
                variant_label=variant_label,
                answer=answer,
                score_detail=score_detail,
                total_score=float(score_detail.get("total_score", 0.0) or 0.0),
            )
        except ValueError as exc:
            track_metric("errors")
            return jsonify({"error": str(exc)}), 400
        track_metric("eval_score_requests")
        return jsonify({"case": case, "run": run})

    @app.route("/api/eval/ab-compare", methods=["OPTIONS", "POST"])
    def eval_ab_compare():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get("user_id", "default")).strip() or "default"
        case_id = str(payload.get("case_id", "")).strip()
        answer_a = str(payload.get("answer_a", "")).strip()
        answer_b = str(payload.get("answer_b", "")).strip()
        label_a = str(payload.get("label_a", "A")).strip() or "A"
        label_b = str(payload.get("label_b", "B")).strip() or "B"
        if not case_id or not answer_a or not answer_b:
            track_metric("errors")
            return jsonify({"error": "case_id, answer_a and answer_b are required"}), 400
        case = memory_service.get_evaluation_case(case_id=case_id)
        if case is None:
            track_metric("errors")
            return jsonify({"error": "evaluation case not found"}), 404
        user_profile = memory_service.get_user_profile(user_id=user_id)
        score_a = llm_service.score_answer(
            question=str(case.get("question", "")),
            answer=answer_a,
            reference_points=case.get("reference_points", []),
            expected_style=str(case.get("expected_style", "")),
            user_profile=user_profile,
        )
        score_b = llm_service.score_answer(
            question=str(case.get("question", "")),
            answer=answer_b,
            reference_points=case.get("reference_points", []),
            expected_style=str(case.get("expected_style", "")),
            user_profile=user_profile,
        )
        run_a = memory_service.create_evaluation_run(
            user_id=user_id,
            case_id=case_id,
            variant_label=label_a,
            answer=answer_a,
            score_detail=score_a,
            total_score=float(score_a.get("total_score", 0.0) or 0.0),
        )
        run_b = memory_service.create_evaluation_run(
            user_id=user_id,
            case_id=case_id,
            variant_label=label_b,
            answer=answer_b,
            score_detail=score_b,
            total_score=float(score_b.get("total_score", 0.0) or 0.0),
        )
        score_a_total = float(score_a.get("total_score", 0.0) or 0.0)
        score_b_total = float(score_b.get("total_score", 0.0) or 0.0)
        winner = "tie"
        if score_a_total > score_b_total:
            winner = label_a
        elif score_b_total > score_a_total:
            winner = label_b
        track_metric("eval_compare_requests")
        return jsonify(
            {
                "case": case,
                "winner": winner,
                "delta": round(abs(score_a_total - score_b_total), 4),
                "run_a": run_a,
                "run_b": run_b,
            }
        )

    @app.route("/api/eval/trends", methods=["GET", "OPTIONS"])
    def eval_trends():
        if request.method == "OPTIONS":
            return ("", 204)
        user_id = str(request.args.get("user_id", "default")).strip() or "default"
        limit = int(request.args.get("limit", 200))
        summary = memory_service.summarize_evaluation_runs(user_id=user_id, limit=limit)
        track_metric("eval_trend_requests")
        return jsonify({"user_id": user_id, "summary": summary})

    @app.route("/uploads/<path:filename>", methods=["GET"])
    def serve_upload(filename: str):
        return send_from_directory(uploads_dir, filename)

    @app.route("/", methods=["GET"])
    def serve_web_index_root():
        if not web_dist_dir.exists():
            return """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>MindShadow 体验版</title>
    <style>
      body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0b1020; color: #e6ecff; }
      .wrap { max-width: 860px; margin: 0 auto; padding: 24px; }
      .card { background: #121a31; border: 1px solid #253055; border-radius: 14px; padding: 16px; margin-bottom: 14px; }
      .row { display: flex; gap: 10px; }
      textarea { width: 100%; min-height: 96px; background: #0d1429; color: #e6ecff; border: 1px solid #2b3d74; border-radius: 10px; padding: 10px; }
      button { background: #4f7cff; color: #fff; border: 0; border-radius: 10px; padding: 10px 14px; font-weight: 600; cursor: pointer; }
      button:disabled { opacity: 0.6; cursor: not-allowed; }
      .status { font-size: 13px; opacity: 0.92; }
      .bubble { background: #0d1429; border: 1px solid #2b3d74; border-radius: 10px; padding: 10px; margin-top: 8px; white-space: pre-wrap; }
      .user { border-color: #4f7cff; }
      .meta { font-size: 12px; opacity: 0.8; margin-top: 6px; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="card">
        <h2 style="margin:0 0 10px">MindShadow 体验版</h2>
        <div id="health" class="status">服务状态检测中...</div>
      </div>
      <div class="card">
        <div class="row">
          <textarea id="input" placeholder="输入你的问题，比如：帮我制定本周教招复习计划"></textarea>
        </div>
        <div style="margin-top:10px" class="row">
          <button id="send">发送</button>
        </div>
      </div>
      <div id="chat" class="card"></div>
    </div>
    <script>
      const healthEl = document.getElementById("health");
      const chatEl = document.getElementById("chat");
      const inputEl = document.getElementById("input");
      const sendBtn = document.getElementById("send");
      const userId = "pm-demo";

      function addBubble(role, text, extra) {
        const div = document.createElement("div");
        div.className = "bubble" + (role === "用户" ? " user" : "");
        div.innerHTML = "<strong>" + role + "</strong><div style='margin-top:6px'>" + text + "</div>" + (extra ? "<div class='meta'>" + extra + "</div>" : "");
        chatEl.prepend(div);
      }

      async function checkHealth() {
        try {
          const res = await fetch("/api/health");
          const data = await res.json();
          const llm = data && data.llm ? data.llm : {};
          healthEl.textContent = "服务在线｜模型模式：" + (llm.remote_ready ? "远程可用" : "本地回复");
        } catch (e) {
          healthEl.textContent = "服务离线，请检查后端";
        }
      }

      async function send() {
        const text = (inputEl.value || "").trim();
        if (!text) return;
        sendBtn.disabled = true;
        addBubble("用户", text);
        inputEl.value = "";
        try {
          const res = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, text }),
          });
          const data = await res.json();
          if (!res.ok) {
            addBubble("系统", data.error || "请求失败");
          } else {
            addBubble("AI", data.reply || "", "模式：" + (data.mode || "-"));
          }
        } catch (e) {
          addBubble("系统", "网络异常，请稍后重试");
        } finally {
          sendBtn.disabled = false;
        }
      }

      sendBtn.addEventListener("click", send);
      inputEl.addEventListener("keydown", (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === "Enter") send();
      });
      checkHealth();
    </script>
  </body>
</html>
"""
        return send_from_directory(web_dist_dir, "index.html")

    @app.route("/app", methods=["GET"])
    def serve_web_app_index():
        return redirect("/", code=302)

    @app.route("/app/<path:filename>", methods=["GET"])
    def serve_web_app_asset(filename: str):
        return redirect("/", code=302)

    @app.route("/assets/<path:filename>", methods=["GET"])
    def serve_web_root_asset(filename: str):
        assets_dir = web_dist_dir / "assets"
        if not assets_dir.exists():
            return jsonify({"error": "web dist assets not found, run frontend build first"}), 404
        return send_from_directory(assets_dir, filename)

    @app.route("/api/upload-image", methods=["OPTIONS", "POST"])
    def upload_image():
        if request.method == "OPTIONS":
            return ("", 204)
        user_id = str(request.form.get("user_id", "default"))
        allowed, retry_after = ensure_rate_limit(user_id)
        if not allowed:
            track_metric("rate_limited_requests")
            response = jsonify({"error": "请求过于频繁，请稍后再试", "retry_after_seconds": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response
        file = request.files.get("image")
        if file is None or not file.filename:
            track_metric("errors")
            return jsonify({"error": "image is required"}), 400
        ext = Path(file.filename).suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            track_metric("errors")
            return jsonify({"error": "仅支持 jpg/jpeg/png/webp 图片"}), 400
        image_id = uuid.uuid4().hex
        stored_name = f"{image_id}{ext}"
        stored_path = uploads_dir / stored_name
        file.save(stored_path)
        track_metric("image_upload_requests")
        image_url = f"{request.host_url.rstrip('/')}/uploads/{stored_name}"
        app.logger.info("[upload] user_id=%s image=%s size=%s", user_id, stored_name, stored_path.stat().st_size)
        return jsonify({"image_id": image_id, "image_url": image_url})

    @app.route("/api/vision-query", methods=["OPTIONS", "POST"])
    def vision_query():
        if request.method == "OPTIONS":
            return ("", 204)
        payload = request.get_json(silent=True) or {}
        question = str(payload.get("question", "")).strip()
        image_url = str(payload.get("image_url", "")).strip()
        user_id = str(payload.get("user_id", "default"))
        conversation_id = normalize_conversation_id(payload.get("conversation_id", "default"))
        if not question:
            track_metric("errors")
            return jsonify({"error": "question is required"}), 400
        if not image_url:
            track_metric("errors")
            return jsonify({"error": "image_url is required"}), 400
        allowed, retry_after = ensure_rate_limit(user_id)
        if not allowed:
            track_metric("rate_limited_requests")
            response = jsonify({"error": "请求过于频繁，请稍后再试", "retry_after_seconds": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response
        track_metric("vision_requests")
        web_context = llm_service.search_web_context(question)
        if web_context:
            track_metric("search_requests")
        kb_context = knowledge_service.search(query=question, top_k=3)
        user_profile = memory_service.get_user_profile(user_id=user_id)
        reply = llm_service.answer_with_image(
            question=question,
            image_url=image_url,
            web_context=web_context,
            kb_context=kb_context,
            user_profile=user_profile,
        )
        memory_service.add_message(
            user_id=user_id,
            role="user",
            content=f"[图片提问] {question}",
            conversation_id=conversation_id,
        )
        memory_service.add_message(user_id=user_id, role="ai", content=reply, conversation_id=conversation_id)
        mode = str(llm_service.status().get("last_response_source", "mock"))
        record_mode(mode)
        app.logger.info("[vision] user_id=%s mode=%s", user_id, mode)
        citations = to_citations(
            web_context=web_context,
            kb_context=kb_context,
            semantic_context=[],
        )
        return jsonify(
            {
                "reply": reply,
                "mode": mode,
                "search_used": bool(web_context),
                "sources": web_context[:3],
                "kb_used": bool(kb_context),
                "kb_sources": kb_context[:3],
                "citations": citations,
                "citation_summary": build_citation_summary(citations),
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("MINDSHADOW_HOST", "0.0.0.0")
    port = int(os.getenv("MINDSHADOW_PORT", "5001"))
    app.run(host=host, port=port, debug=True)
