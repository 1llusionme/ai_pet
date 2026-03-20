import sqlite3
import json
import re
import hashlib
import math
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

UTC = timezone.utc

DEFAULT_TERM_WHITELIST = (
    "教育目的",
    "教学目标",
    "课程标准",
    "教育本质",
    "教育功能",
    "德育原则",
    "教学原则",
    "教学方法",
    "教学过程",
    "课程目标",
    "课程评价",
    "形成性评价",
    "终结性评价",
    "最近发展区",
    "有意义学习",
    "先行组织者",
    "多元智能",
    "建构主义",
    "行为主义",
    "认知主义",
    "教育机智",
    "班级管理",
    "课堂提问",
    "课堂纪律",
    "教育公平",
    "素质教育",
    "核心素养",
    "教师职业道德",
    "因材施教",
    "启发性原则",
    "循序渐进",
    "理论联系实际",
    "赫尔巴特",
    "杜威",
    "夸美纽斯",
    "苏霍姆林斯基",
    "皮亚杰",
    "维果茨基",
    "布鲁纳",
    "奥苏贝尔",
)


class MemoryService:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.embedding_provider = str(os.getenv("MINDSHADOW_EMBEDDING_PROVIDER", "hash")).strip().lower() or "hash"
        self.embedding_model_name = str(
            os.getenv("MINDSHADOW_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        ).strip()
        self.term_whitelist = self._load_term_whitelist()
        self._embedding_model: Any = None
        self._embedding_model_failed = False
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True) if "/" in self.db_path else None
        self._init_db()

    def _load_term_whitelist(self) -> tuple[str, ...]:
        terms: list[str] = list(DEFAULT_TERM_WHITELIST)
        dynamic_text = str(os.getenv("MINDSHADOW_TERM_WHITELIST", "")).strip()
        whitelist_path = str(os.getenv("MINDSHADOW_TERM_WHITELIST_PATH", "")).strip()
        if whitelist_path:
            try:
                file_text = Path(whitelist_path).read_text(encoding="utf-8")
                if file_text.strip():
                    dynamic_text = f"{dynamic_text}\n{file_text}" if dynamic_text else file_text
            except OSError:
                pass
        if dynamic_text:
            candidates = re.split(r"[\n,，;；|]+", dynamic_text)
            for candidate in candidates:
                normalized = self._sanitize_focus_term(candidate)
                if normalized:
                    terms.append(normalized)
        normalized_terms: list[str] = []
        seen: set[str] = set()
        for term in terms:
            cleaned = self._sanitize_focus_term(term)
            if not cleaned or not self._is_valid_focus_term(cleaned):
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            normalized_terms.append(cleaned)
        return tuple(normalized_terms)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL DEFAULT 'default',
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            columns = conn.execute("PRAGMA table_info(messages)").fetchall()
            if not any(str(row["name"]) == "conversation_id" for row in columns):
                conn.execute("ALTER TABLE messages ADD COLUMN conversation_id TEXT NOT NULL DEFAULT 'default'")
            conn.execute("UPDATE messages SET conversation_id = 'default' WHERE conversation_id IS NULL OR conversation_id = ''")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    topic TEXT,
                    confusion_risk TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    exam_goal TEXT,
                    exam_date TEXT,
                    response_style TEXT,
                    weak_points TEXT,
                    study_schedule TEXT,
                    motivation_note TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_card_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_id INTEGER NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_study_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    plan_date TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    tasks TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    checkin_question TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, plan_date)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    focus_topic TEXT NOT NULL,
                    source_question TEXT NOT NULL,
                    mistake_type TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    fix_action TEXT NOT NULL,
                    next_drill TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            try:
                conn.execute("ALTER TABLE review_records ADD COLUMN is_repeat_mistake INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_plan_checkins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    plan_date TEXT NOT NULL,
                    completed_tasks INTEGER NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, plan_date)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS weekly_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    week_start TEXT NOT NULL,
                    week_end TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    highlights TEXT NOT NULL,
                    next_week_focus TEXT NOT NULL,
                    coach_message TEXT NOT NULL,
                    stats_snapshot TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, week_start, week_end)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS nudge_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    notification_id INTEGER NOT NULL,
                    trigger_type TEXT NOT NULL,
                    nudge_level TEXT NOT NULL,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    is_reengaged INTEGER,
                    reengaged_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(notification_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_code TEXT NOT NULL UNIQUE,
                    focus_topic TEXT NOT NULL,
                    question TEXT NOT NULL,
                    reference_points TEXT NOT NULL,
                    expected_style TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    case_id INTEGER NOT NULL,
                    variant_label TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    score_detail TEXT NOT NULL,
                    total_score REAL NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_recall_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    query_digest TEXT NOT NULL,
                    memory_sources_used TEXT NOT NULL,
                    profile_fields_used TEXT NOT NULL,
                    fallback_reason TEXT NOT NULL,
                    search_used INTEGER NOT NULL DEFAULT 0,
                    kb_used INTEGER NOT NULL DEFAULT 0,
                    response_chars INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS answer_render_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    event_payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS profile_conflict_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    old_value TEXT NOT NULL,
                    new_value TEXT NOT NULL,
                    source_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    dim INTEGER NOT NULL,
                    UNIQUE(user_id, source_type, source_id)
                )
                """
            )
            self._seed_evaluation_cases(conn=conn)

    def add_message(self, user_id: str, role: str, content: str, conversation_id: str = "default") -> None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        normalized_conversation_id = str(conversation_id or "default").strip()[:64] or "default"
        with self._conn() as conn:
            result = conn.execute(
                """
                INSERT INTO messages (user_id, conversation_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, normalized_conversation_id, role, content, now),
            )
            source_id = str(int(result.lastrowid or 0))
            self._upsert_vector_row(
                conn=conn,
                user_id=user_id,
                source_type="message",
                source_id=source_id,
                title=f"历史对话-{role}",
                content=content,
                created_at=now,
            )
            if role == "user":
                self._mark_reengaged_after_user_message(conn=conn, user_id=user_id, now=now)

    def get_recent_messages(self, user_id: str, limit: int = 10, conversation_id: Optional[str] = None) -> list[dict[str, Any]]:
        normalized_conversation_id = str(conversation_id or "").strip()[:64]
        with self._conn() as conn:
            if normalized_conversation_id:
                rows = conn.execute(
                    """
                    SELECT id, role, content, created_at
                    FROM messages
                    WHERE user_id = ? AND conversation_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (user_id, normalized_conversation_id, max(1, min(limit, 200))),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, role, content, created_at
                    FROM messages
                    WHERE user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (user_id, max(1, min(limit, 200))),
                ).fetchall()
        messages = [
            {
                "id": str(row["id"]),
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["created_at"],
            }
            for row in reversed(rows)
        ]
        return messages

    def log_recall_event(
        self,
        user_id: str,
        channel: str,
        mode: str,
        query_text: str,
        memory_sources_used: list[str],
        profile_fields_used: list[str],
        fallback_reason: str,
        search_used: bool,
        kb_used: bool,
        response_chars: int,
    ) -> None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        normalized_channel = str(channel or "chat").strip()[:32] or "chat"
        normalized_mode = str(mode or "mock").strip()[:16] or "mock"
        normalized_fallback = str(fallback_reason or "").strip()[:64]
        digest = hashlib.sha256(str(query_text).encode("utf-8")).hexdigest()[:16]
        source_tokens = [str(item).strip() for item in memory_sources_used if str(item).strip()]
        profile_tokens = [str(item).strip() for item in profile_fields_used if str(item).strip()]
        source_json = json.dumps(sorted(set(source_tokens)), ensure_ascii=False)
        profile_json = json.dumps(sorted(set(profile_tokens)), ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memory_recall_events (
                    user_id, channel, mode, query_digest, memory_sources_used, profile_fields_used,
                    fallback_reason, search_used, kb_used, response_chars, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    normalized_channel,
                    normalized_mode,
                    digest,
                    source_json,
                    profile_json,
                    normalized_fallback,
                    1 if search_used else 0,
                    1 if kb_used else 0,
                    max(0, int(response_chars or 0)),
                    now,
                ),
            )

    def summarize_recall_events(self, user_id: str, days: int = 7, limit: int = 200) -> dict[str, Any]:
        window_days = max(1, min(int(days or 7), 90))
        start = (datetime.now(UTC).date() - timedelta(days=window_days - 1)).isoformat()
        capped_limit = max(1, min(int(limit or 200), 1000))
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, channel, mode, query_digest, memory_sources_used, profile_fields_used,
                       fallback_reason, search_used, kb_used, response_chars, created_at
                FROM memory_recall_events
                WHERE user_id = ?
                  AND substr(created_at, 1, 10) >= ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, start, capped_limit),
            ).fetchall()
        channel_counts: dict[str, int] = {}
        mode_counts: dict[str, int] = {}
        fallback_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        profile_field_counts: dict[str, int] = {}
        search_count = 0
        kb_count = 0
        response_chars_total = 0
        events: list[dict[str, Any]] = []
        for row in rows:
            channel = str(row["channel"] or "")
            mode = str(row["mode"] or "")
            fallback_reason = str(row["fallback_reason"] or "")
            channel_counts[channel] = channel_counts.get(channel, 0) + 1
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
            if fallback_reason:
                fallback_counts[fallback_reason] = fallback_counts.get(fallback_reason, 0) + 1
            raw_sources = str(row["memory_sources_used"] or "[]")
            raw_profile_fields = str(row["profile_fields_used"] or "[]")
            try:
                parsed_sources = json.loads(raw_sources)
                source_tokens = [str(item).strip() for item in parsed_sources if str(item).strip()] if isinstance(parsed_sources, list) else []
            except json.JSONDecodeError:
                source_tokens = []
            try:
                parsed_profile = json.loads(raw_profile_fields)
                profile_tokens = [str(item).strip() for item in parsed_profile if str(item).strip()] if isinstance(parsed_profile, list) else []
            except json.JSONDecodeError:
                profile_tokens = []
            for token in source_tokens:
                source_counts[token] = source_counts.get(token, 0) + 1
            for token in profile_tokens:
                profile_field_counts[token] = profile_field_counts.get(token, 0) + 1
            search_used = int(row["search_used"] or 0) > 0
            kb_used = int(row["kb_used"] or 0) > 0
            search_count += 1 if search_used else 0
            kb_count += 1 if kb_used else 0
            response_chars = max(0, int(row["response_chars"] or 0))
            response_chars_total += response_chars
            events.append(
                {
                    "id": str(row["id"]),
                    "channel": channel,
                    "mode": mode,
                    "query_digest": str(row["query_digest"] or ""),
                    "memory_sources_used": source_tokens,
                    "profile_fields_used": profile_tokens,
                    "fallback_reason": fallback_reason,
                    "search_used": search_used,
                    "kb_used": kb_used,
                    "response_chars": response_chars,
                    "created_at": str(row["created_at"] or ""),
                }
            )
        total_events = len(rows)
        avg_response_chars = round(response_chars_total / total_events, 2) if total_events else 0.0
        return {
            "window_days": window_days,
            "total_events": total_events,
            "search_used_count": search_count,
            "kb_used_count": kb_count,
            "avg_response_chars": avg_response_chars,
            "by_channel": channel_counts,
            "by_mode": mode_counts,
            "by_fallback_reason": fallback_counts,
            "source_usage_counts": source_counts,
            "profile_field_usage_counts": profile_field_counts,
            "recent_events": events,
        }

    def log_answer_render_event(self, user_id: str, event_name: str, payload: dict[str, Any]) -> None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        normalized_user_id = str(user_id or "default").strip()[:128] or "default"
        normalized_event_name = str(event_name or "").strip()[:64]
        if not normalized_event_name:
            return
        if isinstance(payload, dict):
            normalized_payload: dict[str, Any] = {}
            for key, value in payload.items():
                field = str(key or "").strip()[:48]
                if not field:
                    continue
                if isinstance(value, bool):
                    normalized_payload[field] = value
                    continue
                if isinstance(value, int | float):
                    normalized_payload[field] = value
                    continue
                normalized_payload[field] = str(value or "").strip()[:240]
        else:
            normalized_payload = {}
        payload_json = json.dumps(normalized_payload, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO answer_render_events (user_id, event_name, event_payload, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (normalized_user_id, normalized_event_name, payload_json, now),
            )

    def summarize_answer_render_events(self, user_id: str, days: int = 7, limit: int = 400) -> dict[str, Any]:
        window_days = max(1, min(int(days or 7), 90))
        capped_limit = max(1, min(int(limit or 400), 2000))
        start = (datetime.now(UTC).date() - timedelta(days=window_days - 1)).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, event_name, event_payload, created_at
                FROM answer_render_events
                WHERE user_id = ?
                  AND substr(created_at, 1, 10) >= ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (str(user_id or "default"), start, capped_limit),
            ).fetchall()
        by_event: dict[str, int] = {}
        visual_lines_total = 0.0
        visual_lines_count = 0
        rich_block_total = 0.0
        rich_block_count = 0
        collapsed_default_count = 0
        expand_open_count = 0
        citation_open_count = 0
        citation_copy_count = 0
        recent_events: list[dict[str, Any]] = []
        for row in rows:
            event_name = str(row["event_name"] or "")
            by_event[event_name] = by_event.get(event_name, 0) + 1
            raw_payload = str(row["event_payload"] or "{}")
            try:
                parsed_payload = json.loads(raw_payload)
            except json.JSONDecodeError:
                parsed_payload = {}
            payload = parsed_payload if isinstance(parsed_payload, dict) else {}
            if event_name == "answer_richtext_rendered":
                visual_raw = payload.get("visual_lines")
                block_raw = payload.get("rich_block_count")
                if isinstance(visual_raw, int | float):
                    visual_lines_total += float(visual_raw)
                    visual_lines_count += 1
                if isinstance(block_raw, int | float):
                    rich_block_total += float(block_raw)
                    rich_block_count += 1
                if bool(payload.get("collapsed_by_default", False)):
                    collapsed_default_count += 1
            if event_name == "answer_expand_clicked" and bool(payload.get("expanded", False)):
                expand_open_count += 1
            if event_name == "answer_citation_toggled" and bool(payload.get("expanded", False)):
                citation_open_count += 1
            if event_name == "answer_citation_copied":
                citation_copy_count += 1
            if len(recent_events) < 60:
                recent_events.append(
                    {
                        "id": str(row["id"]),
                        "event_name": event_name,
                        "payload": payload,
                        "created_at": str(row["created_at"] or ""),
                    }
                )
        rendered_count = int(by_event.get("answer_richtext_rendered", 0))
        collapse_rate = round(collapsed_default_count / rendered_count, 4) if rendered_count else 0.0
        expand_rate = round(expand_open_count / rendered_count, 4) if rendered_count else 0.0
        citation_open_rate = round(citation_open_count / rendered_count, 4) if rendered_count else 0.0
        citation_copy_rate = round(citation_copy_count / rendered_count, 4) if rendered_count else 0.0
        return {
            "window_days": window_days,
            "total_events": len(rows),
            "rendered_count": rendered_count,
            "expand_open_count": expand_open_count,
            "citation_open_count": citation_open_count,
            "citation_copy_count": citation_copy_count,
            "collapse_by_default_count": collapsed_default_count,
            "collapse_by_default_rate": collapse_rate,
            "expand_rate": expand_rate,
            "citation_open_rate": citation_open_rate,
            "citation_copy_rate": citation_copy_rate,
            "avg_visual_lines": round(visual_lines_total / visual_lines_count, 2) if visual_lines_count else 0.0,
            "avg_rich_block_count": round(rich_block_total / rich_block_count, 2) if rich_block_count else 0.0,
            "by_event": by_event,
            "recent_events": recent_events,
        }

    def _semantic_terms(self, text: str) -> list[str]:
        raw = str(text or "")
        normalized = raw.lower()
        normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", normalized)
        terms: list[str] = []
        seen: set[str] = set()
        for token in normalized.split():
            item = token.strip()
            if len(item) < 2:
                continue
            if item in seen:
                continue
            seen.add(item)
            terms.append(item)
        for seq in re.findall(r"[\u4e00-\u9fff]{2,}", raw):
            max_size = min(4, len(seq))
            for size in range(2, max_size + 1):
                for index in range(0, len(seq) - size + 1):
                    gram = seq[index : index + size]
                    if gram in seen:
                        continue
                    seen.add(gram)
                    terms.append(gram)
                    if len(terms) >= 96:
                        return terms
        return terms[:96]

    def _embedding_dim(self) -> int:
        if self.embedding_provider in {"sentence_transformers", "st"}:
            model = self._load_sentence_transformer_model()
            if model is not None:
                try:
                    dim = int(model.get_sentence_embedding_dimension())
                    return max(64, min(dim, 4096))
                except Exception:
                    pass
        raw_dim = str(os.getenv("MINDSHADOW_VECTOR_DIM", "128")).strip()
        try:
            dim = int(raw_dim)
        except ValueError:
            dim = 128
        return max(32, min(dim, 512))

    def _load_sentence_transformer_model(self) -> Any:
        if self._embedding_model is not None:
            return self._embedding_model
        if self._embedding_model_failed:
            return None
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            self._embedding_model = SentenceTransformer(self.embedding_model_name)
            return self._embedding_model
        except Exception:
            self._embedding_model_failed = True
            return None

    def _normalized_embedding_provider(self, provider: str) -> str:
        name = str(provider or "").strip().lower()
        if name in {"sentence_transformers", "st"}:
            return "sentence_transformers"
        return "hash"

    def embedding_runtime_status(self) -> dict[str, Any]:
        provider = self._normalized_embedding_provider(self.embedding_provider)
        fallback_to_hash = provider == "sentence_transformers" and self._embedding_model is None and self._embedding_model_failed
        return {
            "provider": provider,
            "model": self.embedding_model_name,
            "model_loaded": bool(self._embedding_model is not None),
            "model_failed": bool(self._embedding_model_failed),
            "fallback_to_hash": fallback_to_hash,
            "signature": self._embedding_signature(),
            "vector_dim": self._embedding_dim(),
        }

    def set_embedding_runtime(self, provider: str, model_name: Optional[str] = None) -> dict[str, Any]:
        self.embedding_provider = self._normalized_embedding_provider(provider)
        if model_name is not None and str(model_name).strip():
            self.embedding_model_name = str(model_name).strip()
        self._embedding_model = None
        self._embedding_model_failed = False
        if self.embedding_provider == "sentence_transformers":
            self._load_sentence_transformer_model()
        return self.embedding_runtime_status()

    def _embedding_signature(self) -> str:
        if self._normalized_embedding_provider(self.embedding_provider) == "sentence_transformers":
            return f"st:{self.embedding_model_name}"
        return f"hash:{self._embedding_dim()}"

    def _hash_embedding(self, text: str, dim: int) -> list[float]:
        normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
        if not normalized:
            return [0.0] * dim
        features: list[str] = []
        for token in self._semantic_terms(normalized)[:80]:
            features.append(f"t:{token}")
        collapsed = normalized.replace(" ", "")
        for seq in re.findall(r"[\u4e00-\u9fff]+", collapsed):
            max_size = min(4, len(seq))
            for size in range(2, max_size + 1):
                for index in range(0, len(seq) - size + 1):
                    features.append(f"c:{seq[index:index + size]}")
        for token in re.findall(r"[a-z0-9]{2,}", normalized):
            max_size = min(4, len(token))
            for size in range(2, max_size + 1):
                for index in range(0, len(token) - size + 1):
                    features.append(f"e:{token[index:index + size]}")
        if not features:
            return [0.0] * dim
        buckets = [0.0] * dim
        for feature in features[:900]:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0) * 0.2
            buckets[index] += sign * weight
        norm = math.sqrt(sum(value * value for value in buckets))
        if norm <= 0:
            return [0.0] * dim
        return [round(value / norm, 8) for value in buckets]

    def _text_to_embedding(self, text: str) -> list[float]:
        normalized = re.sub(r"\s+", " ", str(text or "").strip())
        if not normalized:
            return [0.0] * self._embedding_dim()
        if self._normalized_embedding_provider(self.embedding_provider) == "sentence_transformers":
            model = self._load_sentence_transformer_model()
            if model is not None:
                try:
                    vector = model.encode([normalized], normalize_embeddings=True)[0]
                    return [round(float(value), 8) for value in vector]
                except Exception:
                    pass
        return self._hash_embedding(text=normalized, dim=self._embedding_dim())

    def reindex_semantic_vectors(self, user_id: Optional[str] = None) -> dict[str, Any]:
        target_user_id = str(user_id or "").strip()
        with self._conn() as conn:
            if target_user_id:
                user_ids = [target_user_id]
            else:
                rows = conn.execute(
                    """
                    SELECT DISTINCT user_id FROM (
                        SELECT user_id FROM messages
                        UNION
                        SELECT user_id FROM review_records
                        UNION
                        SELECT user_id FROM memory_cards
                    )
                    """
                ).fetchall()
                user_ids = [str(row["user_id"] or "").strip() for row in rows if str(row["user_id"] or "").strip()]
            touched = 0
            for uid in user_ids:
                self._sync_vector_index(
                    conn=conn,
                    user_id=uid,
                    include_messages=True,
                    include_review_records=True,
                    include_memory_cards=True,
                )
                touched += 1
            if target_user_id:
                row = conn.execute(
                    "SELECT COUNT(1) AS count FROM semantic_vectors WHERE user_id = ?",
                    (target_user_id,),
                ).fetchone()
                vector_count = int((row["count"] if row else 0) or 0)
            else:
                row = conn.execute("SELECT COUNT(1) AS count FROM semantic_vectors").fetchone()
                vector_count = int((row["count"] if row else 0) or 0)
        return {
            "touched_users": touched,
            "target_user_id": target_user_id or "",
            "vector_count": vector_count,
            "embedding": self.embedding_runtime_status(),
        }

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right:
            return 0.0
        size = min(len(left), len(right))
        if size <= 0:
            return 0.0
        dot = 0.0
        left_norm = 0.0
        right_norm = 0.0
        for index in range(size):
            lv = float(left[index] or 0.0)
            rv = float(right[index] or 0.0)
            dot += lv * rv
            left_norm += lv * lv
            right_norm += rv * rv
        if left_norm <= 0 or right_norm <= 0:
            return 0.0
        return max(0.0, min(1.0, dot / (math.sqrt(left_norm) * math.sqrt(right_norm))))

    def _upsert_vector_row(
        self,
        conn: sqlite3.Connection,
        user_id: str,
        source_type: str,
        source_id: str,
        title: str,
        content: str,
        created_at: str,
    ) -> None:
        body = str(content or "").strip()
        if not body:
            return
        normalized_created_at = str(created_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"))
        embedding = self._text_to_embedding(text=body)
        dim = len(embedding)
        if dim <= 0:
            embedding = [0.0] * self._embedding_dim()
            dim = len(embedding)
        embedding_key = f"{self._embedding_signature()}::{body}"
        content_hash = hashlib.sha256(embedding_key.encode("utf-8")).hexdigest()
        existing = conn.execute(
            """
            SELECT id, content_hash
            FROM semantic_vectors
            WHERE user_id = ? AND source_type = ? AND source_id = ?
            LIMIT 1
            """,
            (user_id, source_type, source_id),
        ).fetchone()
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        if existing and str(existing["content_hash"] or "") == content_hash:
            conn.execute(
                """
                UPDATE semantic_vectors
                SET title = ?, created_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (str(title or "")[:120], normalized_created_at, now, int(existing["id"])),
            )
            return
        embedding_json = json.dumps(embedding, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO semantic_vectors (
                user_id, source_type, source_id, title, content, created_at, updated_at, content_hash, embedding, dim
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, source_type, source_id) DO UPDATE SET
                title = excluded.title,
                content = excluded.content,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at,
                content_hash = excluded.content_hash,
                embedding = excluded.embedding,
                dim = excluded.dim
            """,
            (
                user_id,
                source_type,
                source_id,
                str(title or "")[:120],
                body[:1200],
                normalized_created_at,
                now,
                content_hash,
                embedding_json,
                dim,
            ),
        )

    def _delete_vector_row(self, conn: sqlite3.Connection, user_id: str, source_type: str, source_id: str) -> None:
        conn.execute(
            """
            DELETE FROM semantic_vectors
            WHERE user_id = ? AND source_type = ? AND source_id = ?
            """,
            (user_id, source_type, source_id),
        )

    def _sync_vector_index(
        self,
        conn: sqlite3.Connection,
        user_id: str,
        include_messages: bool,
        include_review_records: bool,
        include_memory_cards: bool,
    ) -> None:
        if include_messages:
            rows = conn.execute(
                """
                SELECT id, role, content, created_at
                FROM messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT 200
                """,
                (user_id,),
            ).fetchall()
            alive_ids: set[str] = set()
            for row in rows:
                source_id = str(row["id"])
                alive_ids.add(source_id)
                self._upsert_vector_row(
                    conn=conn,
                    user_id=user_id,
                    source_type="message",
                    source_id=source_id,
                    title=f"历史对话-{str(row['role'] or 'user')}",
                    content=str(row["content"] or ""),
                    created_at=str(row["created_at"] or ""),
                )
            existing_rows = conn.execute(
                """
                SELECT source_id
                FROM semantic_vectors
                WHERE user_id = ? AND source_type = 'message'
                """,
                (user_id,),
            ).fetchall()
            for row in existing_rows:
                if str(row["source_id"] or "") not in alive_ids:
                    self._delete_vector_row(conn=conn, user_id=user_id, source_type="message", source_id=str(row["source_id"] or ""))
        if include_review_records:
            rows = conn.execute(
                """
                SELECT id, focus_topic, source_question, reason, fix_action, created_at
                FROM review_records
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT 120
                """,
                (user_id,),
            ).fetchall()
            alive_ids = set()
            for row in rows:
                source_id = str(row["id"])
                alive_ids.add(source_id)
                focus_topic = str(row["focus_topic"] or "复盘记录")
                merged = "；".join(
                    item for item in (str(row["source_question"] or ""), str(row["reason"] or ""), str(row["fix_action"] or "")) if item
                )
                self._upsert_vector_row(
                    conn=conn,
                    user_id=user_id,
                    source_type="review",
                    source_id=source_id,
                    title=f"错题复盘-{focus_topic}",
                    content=merged,
                    created_at=str(row["created_at"] or ""),
                )
            existing_rows = conn.execute(
                """
                SELECT source_id
                FROM semantic_vectors
                WHERE user_id = ? AND source_type = 'review'
                """,
                (user_id,),
            ).fetchall()
            for row in existing_rows:
                if str(row["source_id"] or "") not in alive_ids:
                    self._delete_vector_row(conn=conn, user_id=user_id, source_type="review", source_id=str(row["source_id"] or ""))
        if include_memory_cards:
            rows = conn.execute(
                """
                SELECT id, title, content, tags, updated_at, status
                FROM memory_cards
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT 120
                """,
                (user_id,),
            ).fetchall()
            alive_ids = set()
            for row in rows:
                source_id = str(row["id"])
                status = str(row["status"] or "")
                if status != "active":
                    self._delete_vector_row(conn=conn, user_id=user_id, source_type="memory_card", source_id=source_id)
                    continue
                alive_ids.add(source_id)
                merged = "；".join(item for item in (str(row["title"] or ""), str(row["content"] or ""), str(row["tags"] or "")) if item)
                self._upsert_vector_row(
                    conn=conn,
                    user_id=user_id,
                    source_type="memory_card",
                    source_id=source_id,
                    title=f"记忆卡片-{str(row['title'] or '记忆卡片')}",
                    content=merged,
                    created_at=str(row["updated_at"] or ""),
                )
            existing_rows = conn.execute(
                """
                SELECT source_id
                FROM semantic_vectors
                WHERE user_id = ? AND source_type = 'memory_card'
                """,
                (user_id,),
            ).fetchall()
            for row in existing_rows:
                if str(row["source_id"] or "") not in alive_ids:
                    self._delete_vector_row(conn=conn, user_id=user_id, source_type="memory_card", source_id=str(row["source_id"] or ""))

    def hybrid_semantic_recall(
        self,
        user_id: str,
        query_text: str,
        top_k: int = 3,
        include_messages: bool = True,
        include_review_records: bool = True,
        include_memory_cards: bool = True,
        time_decay_days: float = 14.0,
        freshness_weight: float = 0.2,
        semantic_weight: float = 0.55,
        min_similarity: float = 0.12,
        source_weights: Optional[dict[str, float]] = None,
    ) -> list[dict[str, Any]]:
        query = str(query_text).strip()
        if not query:
            return []
        query_terms = self._semantic_terms(text=query)
        now = datetime.now(UTC)
        with self._conn() as conn:
            self._sync_vector_index(
                conn=conn,
                user_id=user_id,
                include_messages=include_messages,
                include_review_records=include_review_records,
                include_memory_cards=include_memory_cards,
            )
            candidate_filters: list[str] = []
            candidate_args: list[Any] = [user_id]
            if include_messages:
                candidate_filters.append("source_type = 'message'")
            if include_review_records:
                candidate_filters.append("source_type = 'review'")
            if include_memory_cards:
                candidate_filters.append("source_type = 'memory_card'")
            if not candidate_filters:
                return []
            where_sql = " OR ".join(candidate_filters)
            candidates = conn.execute(
                f"""
                SELECT source_type, source_id, title, content, created_at, embedding
                FROM semantic_vectors
                WHERE user_id = ? AND ({where_sql})
                ORDER BY updated_at DESC
                LIMIT 280
                """,
                tuple(candidate_args),
            ).fetchall()
        if not candidates:
            return []
        scored: list[dict[str, Any]] = []
        decay_days = max(1.0, float(time_decay_days or 14.0))
        freshness_ratio = min(max(float(freshness_weight or 0.2), 0.0), 0.8)
        semantic_ratio = min(max(float(semantic_weight or 0.55), 0.0), 0.9)
        min_similarity_score = min(max(float(min_similarity or 0.12), 0.0), 0.9)
        source_weight_map = source_weights or {}
        query_embedding = self._text_to_embedding(text=query)
        for item in candidates:
            content = str(item["content"] or "")
            content_terms = self._semantic_terms(text=content)
            matched_terms = [term for term in query_terms if term in content_terms] if query_terms else []
            created_at = str(item["created_at"] or "").strip()
            freshness = 0.0
            if created_at:
                try:
                    created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    age_days = max(0.0, (now - created_dt).total_seconds() / 86400)
                    freshness = 1.0 / (1.0 + age_days / decay_days)
                except ValueError:
                    freshness = 0.0
            try:
                vector = json.loads(str(item["embedding"] or "[]"))
                vector_embedding = [float(value) for value in vector] if isinstance(vector, list) else []
            except (json.JSONDecodeError, ValueError, TypeError):
                vector_embedding = []
            vector_similarity = self._cosine_similarity(left=query_embedding, right=vector_embedding)
            overlap = len(matched_terms) / max(1, len(query_terms)) if query_terms else 0.0
            if overlap <= 0 and vector_similarity < min_similarity_score:
                continue
            source_type = str(item["source_type"] or "")
            source_weight = float(source_weight_map.get(source_type, 1.0) or 1.0)
            semantic_portion = min(semantic_ratio, max(0.0, 1.0 - freshness_ratio))
            overlap_portion = max(0.0, 1.0 - freshness_ratio - semantic_portion)
            base_score = (
                overlap * overlap_portion
                + vector_similarity * semantic_portion
                + freshness * freshness_ratio
            )
            score = round(base_score * max(0.1, min(source_weight, 2.0)), 6)
            scored.append(
                {
                    "source_type": source_type,
                    "source_id": str(item["source_id"] or ""),
                    "title": str(item["title"] or "")[:80],
                    "snippet": content[:220],
                    "matched_terms": matched_terms[:6],
                    "created_at": created_at,
                    "score": score,
                    "vector_similarity": round(vector_similarity, 6),
                    "retrieval_mode": "vector_hybrid",
                }
            )
        scored.sort(key=lambda row: (float(row.get("score", 0.0)), str(row.get("created_at", ""))), reverse=True)
        return scored[: max(1, min(int(top_k or 3), 8))]

    def add_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        topic: Optional[str] = None,
        confusion_risk: Optional[str] = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO memories (user_id, type, content, topic, confusion_risk, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    memory_type,
                    content,
                    topic,
                    confusion_risk,
                    datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                ),
            )

    def get_focus_topic(self, user_id: str) -> str:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT topic
                FROM memories
                WHERE user_id = ? AND topic IS NOT NULL AND topic <> ''
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return str(row["topic"]) if row and row["topic"] else "未设置学习主题"

    def queue_notification(
        self,
        user_id: str,
        content: str,
        trigger_type: str = "manual",
        nudge_level: str = "gentle",
    ) -> None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._conn() as conn:
            cutoff = (datetime.now(UTC) - timedelta(hours=6)).isoformat().replace("+00:00", "Z")
            duplicated = conn.execute(
                """
                SELECT id
                FROM notifications
                WHERE user_id = ? AND content = ? AND created_at >= ? AND status IN ('pending', 'sent')
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id, content, cutoff),
            ).fetchone()
            if duplicated is not None:
                return
            cursor = conn.execute(
                """
                INSERT INTO notifications (user_id, content, status, created_at)
                VALUES (?, ?, 'pending', ?)
                """,
                (user_id, content, now),
            )
            notification_id = int(cursor.lastrowid or 0)
            conn.execute(
                """
                INSERT INTO nudge_events (
                    user_id, notification_id, trigger_type, nudge_level, content, status, is_reengaged, reengaged_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'pending', NULL, NULL, ?, ?)
                """,
                (
                    user_id,
                    notification_id,
                    str(trigger_type or "manual")[:40],
                    str(nudge_level or "gentle")[:20],
                    content,
                    now,
                    now,
                ),
            )

    def pop_pending_notification(self, user_id: str) -> Optional[dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT id, content, created_at
                FROM notifications
                WHERE user_id = ? AND status = 'pending'
                ORDER BY id ASC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE notifications SET status = 'sent' WHERE id = ?",
                (row["id"],),
            )
            conn.execute(
                "UPDATE nudge_events SET status = 'sent', updated_at = ? WHERE notification_id = ?",
                (datetime.now(UTC).isoformat().replace("+00:00", "Z"), row["id"]),
            )
            return {
                "id": str(row["id"]),
                "content": row["content"],
                "timestamp": row["created_at"],
            }

    def _mark_reengaged_after_user_message(self, conn: sqlite3.Connection, user_id: str, now: str) -> None:
        row = conn.execute(
            """
            SELECT id, created_at
            FROM nudge_events
            WHERE user_id = ? AND status = 'sent' AND is_reengaged IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            return
        created_at = str(row["created_at"] or "")
        try:
            created_dt = datetime.fromisoformat(created_at.replace("Z", ""))
            now_dt = datetime.fromisoformat(now.replace("Z", ""))
        except ValueError:
            return
        if now_dt - created_dt > timedelta(hours=24):
            conn.execute(
                """
                UPDATE nudge_events
                SET is_reengaged = 0, updated_at = ?
                WHERE id = ? AND is_reengaged IS NULL
                """,
                (now, row["id"]),
            )
            return
        conn.execute(
            """
            UPDATE nudge_events
            SET is_reengaged = 1, reengaged_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, row["id"]),
        )

    def get_last_user_activity_ts(self, user_id: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT created_at
                FROM messages
                WHERE user_id = ? AND role = 'user'
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return str(row["created_at"]) if row else None

    def get_last_sent_notification_ts(self, user_id: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT created_at
                FROM notifications
                WHERE user_id = ? AND status = 'sent'
                ORDER BY id DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return str(row["created_at"]) if row else None

    def get_active_user_ids(self) -> list[str]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT user_id FROM messages
                UNION
                SELECT DISTINCT user_id FROM memories
                """
            ).fetchall()
        user_ids = [str(row["user_id"]) for row in rows if row["user_id"]]
        return user_ids or ["default"]

    def get_recent_repeat_mistake_count(self, user_id: str, days: int = 3) -> int:
        now = datetime.now(UTC).date()
        start = (now - timedelta(days=max(1, days) - 1)).isoformat()
        end = now.isoformat()
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM review_records
                WHERE user_id = ?
                  AND is_repeat_mistake = 1
                  AND substr(created_at, 1, 10) >= ?
                  AND substr(created_at, 1, 10) <= ?
                """,
                (user_id, start, end),
            ).fetchone()
        return int(row["count"] or 0) if row else 0

    def get_nudge_feedback_summary(self, user_id: str, days: int = 14) -> dict[str, Any]:
        now = datetime.now(UTC)
        start = (now.date() - timedelta(days=max(1, days) - 1)).isoformat()
        now_text = now.isoformat().replace("+00:00", "Z")
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE nudge_events
                SET is_reengaged = 0, updated_at = ?
                WHERE user_id = ?
                  AND status = 'sent'
                  AND is_reengaged IS NULL
                  AND created_at < ?
                """,
                (now_text, user_id, (now - timedelta(hours=24)).isoformat().replace("+00:00", "Z")),
            )
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS sent_count,
                    COALESCE(SUM(CASE WHEN is_reengaged = 1 THEN 1 ELSE 0 END), 0) AS reengaged_count
                FROM nudge_events
                WHERE user_id = ?
                  AND status = 'sent'
                  AND substr(created_at, 1, 10) >= ?
                """,
                (user_id, start),
            ).fetchone()
        sent_count = int(row["sent_count"] or 0) if row else 0
        reengaged_count = int(row["reengaged_count"] or 0) if row else 0
        reengagement_rate = round(reengaged_count / sent_count, 4) if sent_count else 0.0
        return {
            "window_days": max(1, days),
            "sent_count": sent_count,
            "reengaged_count": reengaged_count,
            "reengagement_rate": reengagement_rate,
        }

    def get_nudge_level_feedback(
        self,
        user_id: str,
        trigger_type: str,
        nudge_level: str,
        days: int = 14,
    ) -> dict[str, Any]:
        window_days = max(1, days)
        self.get_nudge_feedback_summary(user_id=user_id, days=window_days)
        start = (datetime.now(UTC).date() - timedelta(days=window_days - 1)).isoformat()
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS sent_count,
                    COALESCE(SUM(CASE WHEN is_reengaged = 1 THEN 1 ELSE 0 END), 0) AS reengaged_count
                FROM nudge_events
                WHERE user_id = ?
                  AND status = 'sent'
                  AND trigger_type = ?
                  AND nudge_level = ?
                  AND substr(created_at, 1, 10) >= ?
                """,
                (user_id, trigger_type, nudge_level, start),
            ).fetchone()
        sent_count = int(row["sent_count"] or 0) if row else 0
        reengaged_count = int(row["reengaged_count"] or 0) if row else 0
        reengagement_rate = round(reengaged_count / sent_count, 4) if sent_count else 0.0
        return {
            "window_days": window_days,
            "trigger_type": trigger_type,
            "nudge_level": nudge_level,
            "sent_count": sent_count,
            "reengaged_count": reengaged_count,
            "reengagement_rate": reengagement_rate,
        }

    def summarize_nudge_strategy(self, user_id: str, days: int = 14) -> dict[str, Any]:
        summary = self.get_nudge_feedback_summary(user_id=user_id, days=days)
        window_days = int(summary.get("window_days", max(1, days)) or max(1, days))
        start = (datetime.now(UTC).date() - timedelta(days=window_days - 1)).isoformat()
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT
                    trigger_type,
                    nudge_level,
                    COUNT(*) AS sent_count,
                    COALESCE(SUM(CASE WHEN is_reengaged = 1 THEN 1 ELSE 0 END), 0) AS reengaged_count,
                    AVG(CASE
                        WHEN is_reengaged = 1 AND reengaged_at IS NOT NULL
                        THEN (julianday(reengaged_at) - julianday(created_at)) * 24.0
                        ELSE NULL
                    END) AS avg_reengage_hours
                FROM nudge_events
                WHERE user_id = ?
                  AND status = 'sent'
                  AND substr(created_at, 1, 10) >= ?
                GROUP BY trigger_type, nudge_level
                ORDER BY sent_count DESC
                """,
                (user_id, start),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            sent_count = int(row["sent_count"] or 0)
            reengaged_count = int(row["reengaged_count"] or 0)
            rate = round(reengaged_count / sent_count, 4) if sent_count else 0.0
            avg_hours = float(row["avg_reengage_hours"]) if row["avg_reengage_hours"] is not None else None
            items.append(
                {
                    "trigger_type": str(row["trigger_type"] or ""),
                    "nudge_level": str(row["nudge_level"] or ""),
                    "sent_count": sent_count,
                    "reengaged_count": reengaged_count,
                    "reengagement_rate": rate,
                    "avg_reengage_hours": round(avg_hours, 4) if avg_hours is not None else None,
                }
            )
        items.sort(key=lambda x: (-float(x["reengagement_rate"]), -int(x["sent_count"])))
        best = items[0] if items else None
        return {
            "window_days": window_days,
            "overall": summary,
            "best_strategy": best,
            "strategies": items,
        }

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT exam_goal, exam_date, response_style, weak_points, study_schedule, motivation_note, updated_at
                FROM user_profiles
                WHERE user_id = ?
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            return {
                "exam_goal": "",
                "exam_date": "",
                "response_style": "",
                "weak_points": [],
                "study_schedule": "",
                "motivation_note": "",
                "updated_at": "",
            }
        weak_points_raw = str(row["weak_points"] or "").strip()
        weak_points: list[str] = []
        if weak_points_raw:
            try:
                parsed = json.loads(weak_points_raw)
                if isinstance(parsed, list):
                    weak_points = [str(item).strip() for item in parsed if str(item).strip()][:8]
            except json.JSONDecodeError:
                weak_points = []
        return {
            "exam_goal": str(row["exam_goal"] or ""),
            "exam_date": str(row["exam_date"] or ""),
            "response_style": str(row["response_style"] or ""),
            "weak_points": weak_points,
            "study_schedule": str(row["study_schedule"] or ""),
            "motivation_note": str(row["motivation_note"] or ""),
            "updated_at": str(row["updated_at"] or ""),
        }

    def upsert_user_profile(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        exam_goal = str(payload.get("exam_goal", "")).strip()[:80]
        exam_date = str(payload.get("exam_date", "")).strip()[:40]
        response_style = str(payload.get("response_style", "")).strip()[:80]
        study_schedule = str(payload.get("study_schedule", "")).strip()[:120]
        motivation_note = str(payload.get("motivation_note", "")).strip()[:200]
        weak_points_raw = payload.get("weak_points", [])
        weak_points: list[str] = []
        if isinstance(weak_points_raw, list):
            weak_points = [str(item).strip() for item in weak_points_raw if str(item).strip()][:8]
        weak_points_text = json.dumps(weak_points, ensure_ascii=False)
        updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO user_profiles (
                    user_id, exam_goal, exam_date, response_style, weak_points, study_schedule, motivation_note, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    exam_goal = excluded.exam_goal,
                    exam_date = excluded.exam_date,
                    response_style = excluded.response_style,
                    weak_points = excluded.weak_points,
                    study_schedule = excluded.study_schedule,
                    motivation_note = excluded.motivation_note,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    exam_goal,
                    exam_date,
                    response_style,
                    weak_points_text,
                    study_schedule,
                    motivation_note,
                    updated_at,
                ),
            )
        return self.get_user_profile(user_id=user_id)

    def _is_negated_keyword(self, text: str, keyword: str) -> bool:
        lowered = text.lower()
        target = keyword.lower()
        index = lowered.find(target)
        while index >= 0:
            window = lowered[max(0, index - 4) : index]
            if any(token in window for token in ("不", "别", "不是", "不要", "别再")):
                return True
            index = lowered.find(target, index + len(target))
        return False

    def _normalize_date_string(self, year: int, month: int, day: int) -> str:
        mm = min(max(int(month), 1), 12)
        dd = min(max(int(day), 1), 31)
        return f"{int(year):04d}-{mm:02d}-{dd:02d}"

    def _extract_exam_date(self, text: str) -> str:
        now = datetime.now(UTC)
        absolute = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", text)
        if absolute:
            return self._normalize_date_string(
                year=int(absolute.group(1)),
                month=int(absolute.group(2)),
                day=int(absolute.group(3)),
            )
        cn_date = re.search(r"(\d{1,2})月(\d{1,2})[日号]?", text)
        if cn_date:
            return self._normalize_date_string(
                year=now.year,
                month=int(cn_date.group(1)),
                day=int(cn_date.group(2)),
            )
        days_later = re.search(r"(\d{1,3})\s*天后", text)
        if days_later:
            target = now + timedelta(days=max(0, int(days_later.group(1))))
            return target.date().isoformat()
        weeks_later = re.search(r"(\d{1,2})\s*周后", text)
        if weeks_later:
            target = now + timedelta(weeks=max(0, int(weeks_later.group(1))))
            return target.date().isoformat()
        if "明天" in text:
            return (now + timedelta(days=1)).date().isoformat()
        if "后天" in text:
            return (now + timedelta(days=2)).date().isoformat()
        return ""

    def _extract_response_style(self, text: str) -> str:
        style_rules = [
            ("先结论后口诀", "先结论后口诀"),
            ("先结论后细节", "先结论后细节"),
            ("先结论", "先结论后细节"),
            ("步骤", "按步骤讲解"),
            ("详细", "详细拆解"),
            ("简洁", "简洁直接"),
            ("鼓励", "鼓励式讲解"),
        ]
        lowered = text.lower()
        for keyword, style in style_rules:
            if keyword.lower() in lowered and not self._is_negated_keyword(text=lowered, keyword=keyword):
                return style
        return ""

    def _extract_weak_points(self, text: str, seed: list[str]) -> list[str]:
        weak_points = list(seed)
        weak_point_patterns = [
            r"(?:薄弱|不太会|不会|总是错在|容易错在|卡在|老是错在)([^，。；\n]{2,20})",
            r"(?:我最怕|我最不懂|记不牢|老忘|总混)([^，。；\n]{2,20})",
        ]
        for pattern in weak_point_patterns:
            for match in re.finditer(pattern, text):
                item = str(match.group(1)).strip("：:，。；、 ")
                if item and item not in weak_points:
                    weak_points.append(item)
        for token in ("人物识记", "时间分配", "审题", "概念辨析", "教育心理学", "教育学原理"):
            if token in text and token not in weak_points:
                weak_points.append(token)
        return weak_points[:8]

    def log_profile_conflict_event(
        self,
        user_id: str,
        field_name: str,
        old_value: str,
        new_value: str,
        source_text: str,
    ) -> None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        digest = hashlib.sha256(str(source_text).encode("utf-8")).hexdigest()[:16]
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO profile_conflict_events (
                    user_id, field_name, old_value, new_value, source_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    str(field_name).strip()[:32],
                    str(old_value).strip()[:120],
                    str(new_value).strip()[:120],
                    digest,
                    now,
                ),
            )

    def auto_update_profile_from_message(self, user_id: str, message: str) -> dict[str, Any]:
        text = str(message).strip()
        if not text:
            return self.get_user_profile(user_id=user_id)
        current = self.get_user_profile(user_id=user_id)
        patch: dict[str, Any] = {}

        goal_match = re.search(r"(?:目标|冲到|考到|拿到)?\s*(\d{2,3})\s*\+?\s*分", text)
        if goal_match:
            patch["exam_goal"] = f"{goal_match.group(1)}+"

        exam_date = self._extract_exam_date(text=text)
        if exam_date:
            patch["exam_date"] = exam_date

        response_style = self._extract_response_style(text=text)
        if response_style:
            patch["response_style"] = response_style

        weak_points = self._extract_weak_points(text=text, seed=list(current.get("weak_points", [])))
        if weak_points:
            patch["weak_points"] = weak_points

        if "工作日" in text or "每天" in text or "晚间" in text or "周末" in text:
            patch["study_schedule"] = text[:120]

        if "上岸" in text or "坚持" in text or "加油" in text:
            patch["motivation_note"] = text[:120]

        if not patch:
            return current
        for field_name, new_value in patch.items():
            if field_name not in current:
                continue
            old_value = current.get(field_name)
            if isinstance(old_value, list):
                old_text = "、".join(str(item).strip() for item in old_value if str(item).strip())
            else:
                old_text = str(old_value or "").strip()
            if isinstance(new_value, list):
                new_text = "、".join(str(item).strip() for item in new_value if str(item).strip())
            else:
                new_text = str(new_value or "").strip()
            if old_text and new_text and old_text != new_text:
                self.log_profile_conflict_event(
                    user_id=user_id,
                    field_name=field_name,
                    old_value=old_text,
                    new_value=new_text,
                    source_text=text,
                )
        merged = {**current, **patch}
        return self.upsert_user_profile(user_id=user_id, payload=merged)

    def _normalize_card_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = str(payload.get("title", "")).strip()[:80]
        content = str(payload.get("content", "")).strip()[:1000]
        tags_raw = payload.get("tags", [])
        tags: list[str] = []
        if isinstance(tags_raw, list):
            tags = [str(item).strip() for item in tags_raw if str(item).strip()][:8]
        return {"title": title, "content": content, "tags": tags}

    def _card_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        tags_raw = str(row["tags"] or "").strip()
        tags: list[str] = []
        if tags_raw:
            try:
                parsed = json.loads(tags_raw)
                if isinstance(parsed, list):
                    tags = [str(item).strip() for item in parsed if str(item).strip()][:8]
            except json.JSONDecodeError:
                tags = []
        card_type = "definition"
        for tag in tags:
            if tag == "卡片类型:辨析卡":
                card_type = "comparison"
                break
            if tag == "卡片类型:步骤卡":
                card_type = "steps"
                break
            if tag == "卡片类型:错因卡":
                card_type = "mistake"
                break
            if tag == "卡片类型:速记卡":
                card_type = "mnemonic"
                break
            if tag == "卡片类型:定义卡":
                card_type = "definition"
                break
        return {
            "id": str(row["id"]),
            "title": str(row["title"] or ""),
            "content": str(row["content"] or ""),
            "tags": tags,
            "card_type": card_type,
            "status": str(row["status"] or "active"),
            "created_at": str(row["created_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
        }

    def _snapshot_card_version(self, conn: sqlite3.Connection, row: sqlite3.Row) -> None:
        conn.execute(
            """
            INSERT INTO memory_card_versions (card_id, user_id, title, content, tags, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(row["id"]),
                str(row["user_id"]),
                str(row["title"] or ""),
                str(row["content"] or ""),
                str(row["tags"] or "[]"),
                str(row["status"] or "active"),
                datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            ),
        )

    def list_memory_cards(self, user_id: str, include_deleted: bool = False, limit: int = 50) -> list[dict[str, Any]]:
        where_status = "" if include_deleted else "AND status = 'active'"
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT id, title, content, tags, status, created_at, updated_at
                FROM memory_cards
                WHERE user_id = ? {where_status}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (user_id, max(1, min(limit, 200))),
            ).fetchall()
        return [self._card_row_to_dict(row) for row in rows]

    def create_memory_card(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_card_payload(payload=payload)
        if not normalized["title"] or not normalized["content"]:
            raise ValueError("title and content are required")
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        tags_text = json.dumps(normalized["tags"], ensure_ascii=False)
        with self._conn() as conn:
            result = conn.execute(
                """
                INSERT INTO memory_cards (user_id, title, content, tags, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', ?, ?)
                """,
                (user_id, normalized["title"], normalized["content"], tags_text, now, now),
            )
            row = conn.execute(
                """
                SELECT id, user_id, title, content, tags, status, created_at, updated_at
                FROM memory_cards
                WHERE id = ?
                LIMIT 1
                """,
                (int(result.lastrowid),),
            ).fetchone()
            if row is None:
                raise ValueError("create memory card failed")
            self._snapshot_card_version(conn=conn, row=row)
            self._upsert_vector_row(
                conn=conn,
                user_id=user_id,
                source_type="memory_card",
                source_id=str(row["id"]),
                title=f"记忆卡片-{str(row['title'] or '记忆卡片')}",
                content="；".join(
                    item
                    for item in (
                        str(row["title"] or ""),
                        str(row["content"] or ""),
                        str(row["tags"] or ""),
                    )
                    if item
                ),
                created_at=str(row["updated_at"] or now),
            )
            return self._card_row_to_dict(row=row)

    def _sanitize_focus_term(self, raw: str) -> str:
        term = str(raw or "").strip()
        term = re.sub(r"^[#>*\-\d\.\)\(]+", "", term).strip()
        term = re.sub(r"[*_`~]+", "", term).strip()
        term = re.sub(r"^(先看|再看|看|先学|再学|学会|学习|复盘|梳理|理解|掌握|记住|区分|比较|围绕|关于)+", "", term).strip()
        term = re.sub(r"(这个错误写法|的区别|的定义|的概念|的作用|的意义)$", "", term).strip()
        term = re.sub(r"(主要|通常|一般|核心|关键)$", "", term).strip()
        term = term.strip("：:;；，,、。.!！？?()（）【】[]<>《》\"'“”‘’ ")
        term = re.sub(r"\s+", "", term)
        return term

    def _is_valid_focus_term(self, term: str) -> bool:
        candidate = str(term or "").strip()
        if not candidate or len(candidate) < 2 or len(candidate) > 14:
            return False
        if re.search(r"[，,、。.!！？?；;：:\n]", candidate):
            return False
        if not re.search(r"[\u4e00-\u9fffA-Za-z]", candidate):
            return False
        banned_patterns = (
            "进行",
            "以及",
            "这个",
            "那个",
            "我们",
            "你们",
            "他们",
            "不是",
            "可以",
            "应该",
            "需要",
            "为了",
            "通过",
            "如果",
            "因为",
            "所以",
            "然后",
            "首先",
            "其次",
            "最后",
            "自动收集",
            "重点术语",
        )
        if any(pattern in candidate for pattern in banned_patterns):
            return False
        if candidate in {"术语", "概念", "知识点", "方法", "结论", "重点"}:
            return False
        if candidate in {"为什么", "怎么", "如何", "是否", "什么", "哪些", "哪个", "哪里", "多少", "怎么办"}:
            return False
        if candidate.endswith(("吗", "呢", "么")):
            return False
        if candidate.endswith(("主要", "通常", "一般", "核心", "关键")):
            return False
        leading_or_trailing = "的是了着地得和与及并而又在对把被让给"
        if candidate[0] in leading_or_trailing or candidate[-1] in leading_or_trailing:
            return False
        chinese_only = bool(re.fullmatch(r"[\u4e00-\u9fff]+", candidate))
        if chinese_only and len(candidate) > 8:
            return False
        return True

    def _focus_term_quality_score(self, term: str, source_text: str, source_type: str) -> int:
        candidate = str(term or "").strip()
        if not candidate:
            return -10
        score = 0
        if candidate in self.term_whitelist:
            score += 5
        if source_type in {"marked", "bolded", "quoted"}:
            score += 2
        if source_type == "definition":
            score += 3
        if source_type == "enumeration":
            score += 2
        if source_type == "chunk":
            score += 1
        if len(candidate) >= 3:
            score += 1
        if source_text.count(candidate) >= 2:
            score += 1
        if re.search(rf"{re.escape(candidate)}(?:是|指|属于|包括|强调|核心|区别于|不同于|用于)", source_text):
            score += 2
        if re.search(rf"(理论|原则|目标|标准|方法|模型|效应|概念|课程|教学|评价|动机|记忆|学习|发展|课堂|德育|智育|美育|教育)$", candidate):
            score += 1
        if re.search(r"(这个|那个|这样|那样|进行|通过|如果|因为|所以|首先|其次|最后)", candidate):
            score -= 3
        if candidate in {"术语", "概念", "知识点", "重点", "方法", "结论"}:
            score -= 4
        return score

    def _extract_focus_terms(self, text: str, limit: int = 8) -> list[str]:
        source = str(text or "")
        if not source:
            return []
        candidates: dict[str, int] = {}
        cleaned_source = re.sub(r"\s+", " ", source)
        max_limit = min(max(int(limit), 1), 8)

        def add_term(raw: str, source_type: str) -> None:
            term = self._sanitize_focus_term(raw)
            if not self._is_valid_focus_term(term):
                return
            score = self._focus_term_quality_score(term=term, source_text=cleaned_source, source_type=source_type)
            if score < 2:
                return
            previous = candidates.get(term)
            if previous is None or score > previous:
                candidates[term] = score

        for whitelist_term in self.term_whitelist:
            if whitelist_term in source:
                add_term(whitelist_term, "whitelist")
        for marked in re.findall(r"==([^=\n]+)==", source):
            add_term(marked, "marked")
        for bolded in re.findall(r"\*\*([^*\n]+)\*\*", source):
            add_term(bolded, "bolded")
        for quoted in re.findall(r"[“\"《]([^”\"》\n]{2,16})[”\"》]", source):
            add_term(quoted, "quoted")
        for enumeration in re.findall(r"((?:[\u4e00-\u9fffA-Za-z]{2,14}、){1,4}[\u4e00-\u9fffA-Za-z]{2,14})", source):
            for item in enumeration.split("、"):
                add_term(item, "enumeration")

        definition_matches = re.findall(
            r"(?:^|[，。；\s])([\u4e00-\u9fffA-Za-z]{2,14}?)(?:指的是|定义为|定义成|属于|包括|意味着|称为|叫做)",
            source,
        )
        for matched in definition_matches:
            add_term(matched, "definition")

        sentence_parts = [part.strip() for part in re.split(r"[，,、。；;！!？?\n]+", source) if part.strip()]
        connectors = r"(?:不是|并非|以及|和|与|再|先|后|然后|并且|或者|还是|通过|对照|围绕|关于|因为|所以)"
        for part in sentence_parts:
            chunks = [chunk.strip() for chunk in re.split(connectors, part) if chunk.strip()]
            for chunk in chunks:
                add_term(chunk, "chunk")
        if not candidates:
            return []
        ranked = sorted(candidates.items(), key=lambda item: (item[1], len(item[0])), reverse=True)
        selected: list[str] = []
        for term, _score in ranked:
            if any(term in existing and len(existing) >= len(term) + 2 for existing in selected):
                continue
            selected.append(term)
            if len(selected) >= max_limit:
                break
        return selected

    def _extract_term_snippet(self, answer_text: str, term: str) -> str:
        lines = [str(line).strip() for line in str(answer_text or "").splitlines() if str(line).strip()]
        for line in lines:
            if term in line:
                return line[:180]
        compact = " ".join(lines)
        return compact[:180]

    def _normalize_term_snippet(self, snippet: str, term: str) -> str:
        text = str(snippet or "")
        text = re.sub(r"[*_`~#>]+", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(rf"(?:{re.escape(term)}[：:;；]?\s*){{2,}}", f"{term}：", text)
        return text[:180]

    def _is_meaningful_term_snippet(self, snippet: str, term: str) -> bool:
        text = re.sub(r"\s+", " ", str(snippet or "").strip())
        if len(text) < 8:
            return False
        if text == term:
            return False
        if re.fullmatch(rf"{re.escape(term)}[。.!！?？]?", text):
            return False
        normalized = re.sub(r"[：:;；，,、。.!！？?()\[\]{}<>《》\"'“”‘’\s]+", "", text)
        if normalized and normalized.replace(term, "") == "":
            return False
        return bool(re.search(r"[\u4e00-\u9fffA-Za-z]{4,}", text))

    def _card_type_label(self, card_type: str) -> str:
        mapping = {
            "definition": "定义卡",
            "comparison": "辨析卡",
            "steps": "步骤卡",
            "mistake": "错因卡",
            "mnemonic": "速记卡",
        }
        return mapping.get(card_type, "定义卡")

    def _is_low_value_term(self, term: str) -> bool:
        normalized = re.sub(r"\s+", "", str(term or ""))
        if not normalized:
            return True
        blocked_exact = {
            "口诀",
            "速记",
            "记忆",
            "口诀记忆",
            "记忆口诀",
            "口决记忆",
            "这个",
            "那个",
            "这种",
            "那个点",
            "重点",
            "前提",
            "结论",
            "行动建议",
            "依据",
        }
        if normalized in blocked_exact:
            return True
        return bool(re.fullmatch(r"[A-Za-z]{1,2}", normalized))

    def _extract_mnemonic_phrase(self, snippet: str) -> str:
        text = str(snippet or "")
        matched = re.search(
            r"(?:口诀|速记|顺口溜|记忆点|记忆锚点|速记锚点)\s*[：:]\s*([^\n。；;，,]{2,24})",
            text,
        )
        if not matched:
            return ""
        return re.sub(r"\s+", "", str(matched.group(1) or ""))

    def _infer_learning_card_type(self, source_question: str, answer_text: str, term: str, snippet: str) -> str:
        local_context = f"{term} {snippet}"
        merged = f"{source_question} {answer_text} {local_context}"
        if re.search(r"(错题|做错|老错|总错|易错|误区|纠错|复盘)", merged):
            return "mistake"
        if re.search(r"(怎么答|如何答|步骤|模板|先|再|最后|流程)", local_context):
            return "steps"
        if re.search(r"(区别|对比|辨析|不同|A与B|A和B)", local_context):
            return "comparison"
        has_mnemonic_signal = bool(re.search(r"(口诀|速记|记忆|口诀法|顺口溜)", local_context))
        has_mnemonic_marker = bool(
            re.search(
                r"(口诀[:：]|速记[:：]|顺口溜[:：]|记忆点[:：]|记忆锚点[:：]|速记锚点[:：])",
                str(snippet or ""),
            )
        )
        mnemonic_phrase = self._extract_mnemonic_phrase(snippet)
        normalized_term = re.sub(r"\s+", "", str(term or ""))
        if has_mnemonic_signal and has_mnemonic_marker:
            if re.search(r"(口诀|速记|记忆|顺口溜)", normalized_term) or (mnemonic_phrase and normalized_term in mnemonic_phrase):
                return "mnemonic"
        return "definition"

    def _format_learning_card_content(self, card_type: str, term: str, snippet: str, source_question: str) -> str:
        cleaned_snippet = str(snippet or "").strip()
        question = str(source_question or "").strip()
        if card_type == "comparison":
            return "\n".join(
                item
                for item in (
                    f"结论：围绕「{term}」做对照辨析，先明确比较维度再下结论。",
                    "怎么做：先写共同点，再写关键差异，最后给出判定句。",
                    f"行动建议：用「{term}」做一组A/B对比并口述判断依据。",
                    f"依据：{cleaned_snippet}",
                    f"来源问题：{question}" if question else "",
                )
                if item
            )
        if card_type == "steps":
            return "\n".join(
                item
                for item in (
                    f"结论：把「{term}」转成可执行步骤，按顺序作答。",
                    "怎么做：先审题定位关键词，再套步骤模板，最后做自检。",
                    f"行动建议：围绕「{term}」写出3步答题流程并做1题演练。",
                    f"依据：{cleaned_snippet}",
                    f"来源问题：{question}" if question else "",
                )
                if item
            )
        if card_type == "mistake":
            return "\n".join(
                item
                for item in (
                    f"结论：你在「{term}」上属于高频易错点，需要错因-修正闭环。",
                    "为什么：常见原因是概念边界模糊或审题抓点不准。",
                    f"行动建议：先复述「{term}」判断点，再做1道同类题并写依据。",
                    f"依据：{cleaned_snippet}",
                    f"来源问题：{question}" if question else "",
                )
                if item
            )
        if card_type == "mnemonic":
            return "\n".join(
                item
                for item in (
                    f"结论：把「{term}」压缩成速记锚点，临场快速调用。",
                    "怎么记：优先记关键词顺序，再记触发场景。",
                    f"行动建议：用15秒复述「{term}」并说出适用题型。",
                    f"依据：{cleaned_snippet}",
                    f"来源问题：{question}" if question else "",
                )
                if item
            )
        return "\n".join(
            item
            for item in (
                f"结论：「{term}」的核心是先抓定义，再抓判断标准。",
                "怎么用：作答时先给定义句，再补使用场景或边界。",
                f"行动建议：用自己的话复述「{term}」并补1个判断点。",
                f"依据：{cleaned_snippet}",
                f"来源问题：{question}" if question else "",
            )
            if item
        )

    def _is_valid_generated_card_content(
        self,
        content: str,
        term: str,
        snippet: str,
    ) -> bool:
        normalized = str(content or "").strip()
        if len(normalized) < 36 or len(normalized) > 980:
            return False
        required_labels = ("结论：", "行动建议：", "依据：")
        if any(label not in normalized for label in required_labels):
            return False
        if str(term or "").strip() not in normalized:
            return False
        snippet_text = str(snippet or "").strip()
        if snippet_text and len(snippet_text) >= 6 and snippet_text[:6] not in normalized:
            return False
        if re.search(r"(抱歉|无法|不能|作为AI|仅供参考)", normalized):
            return False
        return True

    def _build_learning_card_content_hybrid(
        self,
        card_type: str,
        term: str,
        snippet: str,
        source_question: str,
        llm_service: Optional[Any] = None,
    ) -> tuple[str, str]:
        rule_content = self._format_learning_card_content(
            card_type=card_type,
            term=term,
            snippet=snippet,
            source_question=source_question,
        )
        if llm_service is None or not hasattr(llm_service, "generate_learning_card_copy"):
            return rule_content, "rule"
        try:
            generated = llm_service.generate_learning_card_copy(
                card_type=card_type,
                term=term,
                snippet=snippet,
                source_question=source_question,
            )
        except Exception:
            return rule_content, "rule"
        if not isinstance(generated, dict):
            return rule_content, "rule"
        mode = str(generated.get("mode", "")).strip()
        llm_content = str(generated.get("content", "")).strip()
        if not llm_content:
            return rule_content, "rule"
        if not self._is_valid_generated_card_content(content=llm_content, term=term, snippet=snippet):
            return rule_content, "rule"
        normalized_mode = "llm" if mode.startswith("llm") else "rule"
        return llm_content[:1000], normalized_mode

    def _has_mistake_signal(self, source_question: str, answer_text: str) -> bool:
        merged = f"{source_question} {answer_text}"
        if not merged.strip():
            return False
        return bool(re.search(r"(错题|做错|老错|总错|易错|误区|纠错|复盘)", merged))

    def _has_high_value_learning_structure(self, source_question: str, answer_text: str) -> bool:
        merged = f"{source_question} {answer_text}"
        if not merged.strip():
            return False
        return bool(
            re.search(
                r"(是什么|本质|定义|概念|区别|对比|辨析|怎么答|如何答|步骤|模板|错题|复盘|口诀|速记|"
                r"指的是|定义为|包括|先|再|最后|用于|判断点|检查点)",
                merged,
            )
        )

    def _extract_answer_sentences(self, text: str, limit: int = 3) -> list[str]:
        source = str(text or "")
        if not source:
            return []
        sentences = [
            item.strip()
            for item in re.split(r"[。；;！!？?\n]+", source)
            if item and len(re.sub(r"\s+", "", item)) >= 10
        ]
        if not sentences:
            compact = re.sub(r"\s+", " ", source).strip()
            return [compact[:120]] if compact else []
        unique: list[str] = []
        for sentence in sentences:
            normalized = re.sub(r"\s+", "", sentence)
            if any(normalized == re.sub(r"\s+", "", existing) for existing in unique):
                continue
            unique.append(sentence[:120])
            if len(unique) >= max(1, min(limit, 6)):
                break
        return unique

    def _extract_list_items_from_answer(self, source_question: str, answer_text: str, limit: int = 6) -> list[str]:
        question = str(source_question or "")
        answer = str(answer_text or "")
        if not question or not answer:
            return []
        if not re.search(r"(包括|有哪些|构成|主要内容|包含|有哪些方面)", question):
            return []
        matched = re.search(r"(?:包括|包含|有)([^。；;\n]{4,160})", answer)
        if not matched:
            return []
        raw_segment = str(matched.group(1) or "")
        cleaned_segment = re.sub(r"(等|等方面|等内容)$", "", raw_segment).strip("：:，,。；; ")
        if not cleaned_segment:
            return []
        raw_items = re.split(r"[、,，]|(?:以及|和|与|及)", cleaned_segment)
        items: list[str] = []
        for raw in raw_items:
            item = self._sanitize_focus_term(raw)
            if not item or item in items:
                continue
            if len(item) < 2 or len(item) > 12:
                continue
            if item.endswith(("方面", "内容", "问题")):
                continue
            items.append(item)
            if len(items) >= max(1, min(limit, 8)):
                break
        return items

    def _preferred_term_suffix(self, source_question: str) -> str:
        question = str(source_question or "")
        matched = re.search(r"(目标|任务|原则|步骤|标准|方法|作用|意义|特点|类型|维度)", question)
        if not matched:
            return ""
        return str(matched.group(1) or "")

    def _build_summary_card_content(self, source_question: str, answer_text: str) -> str:
        question = str(source_question or "").strip()
        answer = str(answer_text or "").strip()
        sentences = self._extract_answer_sentences(answer, limit=3)
        list_items = self._extract_list_items_from_answer(question, answer, limit=6)
        core_sentence = sentences[0] if sentences else answer[:120]
        support_sentence = sentences[1] if len(sentences) > 1 else ""
        checklist = "、".join(list_items) if list_items else ""
        return "\n".join(
            item
            for item in (
                f"核心答案：{core_sentence}",
                f"记忆清单：{checklist}" if checklist else "",
                f"补充理解：{support_sentence}" if support_sentence else "",
                "答题动作：先总述核心结论，再分点展开，最后补一句价值或边界。",
                f"自测题：{question}" if question else "自测题：请用自己的话复述这题核心要点。",
            )
            if item
        )

    def _build_export_experience(
        self,
        export_gate: dict[str, Any],
        exported_cards: list[dict[str, Any]],
        term_cards_added: int,
        term_cards_updated: int,
    ) -> dict[str, Any]:
        allow = bool(export_gate.get("allow_term_cards"))
        if not allow:
            reason = str(export_gate.get("reject_message", "")).strip() or "本次回答暂不适合生成术语卡。"
            return {
                "status": "summary_only",
                "message": f"已生成学习主卡。{reason}",
                "next_action": "建议先看主卡，再追问“请拆成可复习的3个术语卡”。",
            }
        if exported_cards:
            lead_title = str(exported_cards[0].get("title", "学习卡片")).strip() or "学习卡片"
            return {
                "status": "cards_ready",
                "message": f"已生成可复习卡片：新增{term_cards_added}，更新{term_cards_updated}。建议先看「{lead_title}」。",
                "next_action": "打开学习资产库，先看主卡，再按顺序看重点卡。",
            }
        return {
            "status": "summary_only",
            "message": "已生成学习主卡，本次术语候选质量不足，未生成重点卡。",
            "next_action": "可继续追问“请给我更结构化的分点答案”。",
        }

    def _learning_export_gate_decision(self, source_question: str, answer_text: str) -> dict[str, Any]:
        text = str(answer_text or "")
        normalized = re.sub(r"\s+", "", text)
        semantic_chunks = re.findall(r"[\u4e00-\u9fffA-Za-z]{2,}", text)
        punctuation_or_symbol = re.findall(r"[^\u4e00-\u9fffA-Za-z0-9]", text)
        noise_ratio = (len(punctuation_or_symbol) / max(1, len(text))) if text else 1.0
        has_structure = self._has_high_value_learning_structure(source_question=source_question, answer_text=answer_text)
        if len(normalized) < 16 and not has_structure:
            return {
                "allow_term_cards": False,
                "reject_reason": "too_short_no_structure",
                "reject_message": "内容过短且缺少可复习结构，已仅保留学习总结卡。",
            }
        if len(semantic_chunks) < 3 and not has_structure:
            return {
                "allow_term_cards": False,
                "reject_reason": "insufficient_information",
                "reject_message": "有效学习信息不足，已仅保留学习总结卡。",
            }
        if noise_ratio >= 0.45 and not has_structure:
            return {
                "allow_term_cards": False,
                "reject_reason": "high_noise_content",
                "reject_message": "内容噪声较高，已仅保留学习总结卡。",
            }
        return {
            "allow_term_cards": True,
            "reject_reason": None,
            "reject_message": "",
        }

    def _term_quality_score(self, term: str, snippet: str, source_question: str, answer_text: str) -> int:
        base = self._focus_term_quality_score(term=term, source_text=answer_text, source_type="definition")
        score = 58 + (base * 5)
        if term and term in str(source_question or ""):
            score += 6
        if re.search(rf"{re.escape(term)}(?:是|指|属于|包括|用于|强调|核心)", str(answer_text or "")):
            score += 8
        if re.search(r"(先|再|最后|步骤|对照|检查|复述|完成|套用)", str(snippet or "")):
            score += 6
        if len(re.sub(r"\s+", "", str(snippet or ""))) < 14:
            score -= 12
        if not self._is_meaningful_term_snippet(snippet=snippet, term=term):
            score -= 18
        return max(0, min(score, 100))

    def export_answer_to_learning_assets(
        self,
        user_id: str,
        source_question: str,
        answer_text: str,
        llm_service: Optional[Any] = None,
    ) -> dict[str, Any]:
        normalized_user_id = str(user_id or "default").strip() or "default"
        normalized_question = str(source_question or "").strip()[:400]
        normalized_answer = str(answer_text or "").strip()[:3000]
        if not normalized_answer:
            raise ValueError("answer_text is required")
        base_title = normalized_question[:20] if normalized_question else "本轮学习总结"
        summary_title = f"学习卡片：{base_title}"
        summary_content = self._build_summary_card_content(
            source_question=normalized_question,
            answer_text=normalized_answer,
        )
        summary_card = self.create_memory_card(
            user_id=normalized_user_id,
            payload={
                "title": summary_title,
                "content": summary_content[:1000],
                "tags": ["学习导出", "聊天回答"],
            },
        )
        export_gate = self._learning_export_gate_decision(
            source_question=normalized_question,
            answer_text=normalized_answer,
        )
        raw_term_limit = str(os.getenv("MINDSHADOW_EXPORT_TERM_LIMIT", "4")).strip()
        raw_supporting_limit = str(os.getenv("MINDSHADOW_EXPORT_SUPPORTING_CARD_LIMIT", "2")).strip()
        try:
            term_limit = int(raw_term_limit)
        except ValueError:
            term_limit = 4
        try:
            supporting_limit = int(raw_supporting_limit)
        except ValueError:
            supporting_limit = 2
        supporting_limit = max(0, min(supporting_limit, 2))
        extract_limit = max(1, min(max(term_limit, supporting_limit), 8))
        terms = self._extract_focus_terms(normalized_answer, limit=extract_limit)
        term_cards_added = 0
        term_cards_updated = 0
        created_reviews: list[dict[str, Any]] = []
        exported_terms: list[str] = []
        quality_scores: list[dict[str, Any]] = []
        has_mistake_signal = self._has_mistake_signal(normalized_question, normalized_answer)
        raw_main_threshold = str(os.getenv("MINDSHADOW_EXPORT_MAIN_SCORE_THRESHOLD", "75")).strip()
        raw_support_threshold = str(os.getenv("MINDSHADOW_EXPORT_SUPPORT_SCORE_THRESHOLD", "68")).strip()
        raw_floor = str(os.getenv("MINDSHADOW_EXPORT_MIN_QUALITY_FLOOR", "60")).strip()
        try:
            main_threshold = int(raw_main_threshold)
        except ValueError:
            main_threshold = 75
        try:
            support_threshold = int(raw_support_threshold)
        except ValueError:
            support_threshold = 68
        try:
            quality_floor = int(raw_floor)
        except ValueError:
            quality_floor = 60
        main_threshold = max(0, min(main_threshold, 100))
        support_threshold = max(0, min(support_threshold, 100))
        quality_floor = max(0, min(quality_floor, 100))
        scored_candidates: list[tuple[str, str, int]] = []
        skipped_candidates: list[dict[str, str]] = []
        preferred_suffix = self._preferred_term_suffix(source_question=normalized_question)
        for term in terms:
            if self._is_low_value_term(term):
                skipped_candidates.append({"term": term, "reason": "low_value_term"})
                continue
            snippet = self._extract_term_snippet(normalized_answer, term)
            snippet = self._normalize_term_snippet(snippet=snippet, term=term)
            if not self._is_meaningful_term_snippet(snippet=snippet, term=term):
                skipped_candidates.append({"term": term, "reason": "weak_snippet"})
                continue
            quality = self._term_quality_score(
                term=term,
                snippet=snippet,
                source_question=normalized_question,
                answer_text=normalized_answer,
            )
            quality_scores.append(
                {
                    "term": term,
                    "quality_score": quality,
                    "passed_floor": quality >= quality_floor,
                }
            )
            if preferred_suffix and not str(term).endswith(preferred_suffix) and quality < 88:
                skipped_candidates.append({"term": term, "reason": "question_suffix_mismatch"})
                continue
            if quality < max(quality_floor, support_threshold):
                skipped_candidates.append({"term": term, "reason": "quality_below_threshold"})
                continue
            scored_candidates.append((term, snippet, quality))
        scored_candidates.sort(key=lambda item: item[2], reverse=True)
        if export_gate["allow_term_cards"] and scored_candidates:
            if scored_candidates[0][2] < main_threshold:
                export_gate = {
                    "allow_term_cards": False,
                    "reject_reason": "low_main_card_quality",
                    "reject_message": "候选卡片质量不足，已仅保留学习总结卡。",
                }
        selected_candidates = scored_candidates[:supporting_limit] if export_gate["allow_term_cards"] else []
        exported_cards: list[dict[str, Any]] = []
        llm_generated_count = 0
        rule_generated_count = 0
        raw_llm_card_limit = str(os.getenv("MINDSHADOW_EXPORT_LLM_CARD_LIMIT", "1")).strip()
        try:
            llm_card_limit = int(raw_llm_card_limit)
        except ValueError:
            llm_card_limit = 1
        llm_card_limit = max(0, min(llm_card_limit, supporting_limit))
        for index, (term, snippet, quality) in enumerate(selected_candidates):
            exported_terms.append(term)
            card_type = self._infer_learning_card_type(
                source_question=normalized_question,
                answer_text=normalized_answer,
                term=term,
                snippet=snippet,
            )
            card_type_label = self._card_type_label(card_type)
            card_title = f"{card_type_label}：{term}"
            next_tags = ["重点术语", "自动收集", "学习卡片", f"卡片类型:{card_type_label}"]
            card_content, generation_mode = self._build_learning_card_content_hybrid(
                card_type=card_type,
                term=term,
                snippet=snippet,
                source_question=normalized_question,
                llm_service=llm_service if index < llm_card_limit else None,
            )
            if generation_mode == "llm":
                llm_generated_count += 1
            else:
                rule_generated_count += 1
            with self._conn() as conn:
                existing = conn.execute(
                    """
                    SELECT id, content
                    FROM memory_cards
                    WHERE user_id = ? AND title = ? AND status = 'active'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (normalized_user_id, card_title),
                ).fetchone()
            if existing is None:
                created_card = self.create_memory_card(
                    user_id=normalized_user_id,
                    payload={
                        "title": card_title,
                        "content": card_content,
                        "tags": next_tags,
                    },
                )
                term_cards_added += 1
                exported_cards.append(
                    {
                        "id": created_card["id"],
                        "title": created_card["title"],
                        "term": term,
                        "quality_score": quality,
                        "card_type": card_type,
                        "is_primary": index == 0,
                        "generation_mode": generation_mode,
                    }
                )
            else:
                existing_content = str(existing["content"] or "")
                merged_content = card_content if not existing_content else f"{card_content}\n{existing_content}"
                if merged_content != existing_content:
                    updated_card = self.update_memory_card(
                        user_id=normalized_user_id,
                        card_id=str(existing["id"]),
                        payload={
                            "content": merged_content[:1000],
                            "tags": next_tags,
                        },
                    )
                    term_cards_updated += 1
                    if updated_card is not None:
                        exported_cards.append(
                            {
                                "id": updated_card["id"],
                                "title": updated_card["title"],
                                "term": term,
                                "quality_score": quality,
                                "card_type": card_type,
                                "is_primary": index == 0,
                                "generation_mode": generation_mode,
                            }
                        )
                else:
                    exported_cards.append(
                        {
                            "id": str(existing["id"]),
                            "title": card_title,
                            "term": term,
                            "quality_score": quality,
                            "card_type": card_type,
                            "is_primary": index == 0,
                            "generation_mode": generation_mode,
                        }
                    )
            if has_mistake_signal and len(created_reviews) < 2:
                created_reviews.append(
                    self.create_review_record(
                        user_id=normalized_user_id,
                        payload={
                            "focus_topic": term[:80],
                            "source_question": normalized_question or f"围绕术语 {term} 的错题复盘",
                            "mistake_type": "概念混淆",
                            "reason": "该术语在错题语境中出现，基础定义需要再稳固。",
                            "fix_action": f"用自己的话复述「{term}」并说出1个判断点。",
                            "next_drill": f"围绕「{term}」完成1道同类题并写依据。",
                        },
                    )
                )
        experience = self._build_export_experience(
            export_gate=export_gate,
            exported_cards=exported_cards,
            term_cards_added=term_cards_added,
            term_cards_updated=term_cards_updated,
        )
        return {
            "summary_card": summary_card,
            "terms": exported_terms,
            "cards": exported_cards,
            "primary_card_type": exported_cards[0]["card_type"] if exported_cards else None,
            "card_types": sorted({str(card["card_type"]) for card in exported_cards}),
            "term_cards_added": term_cards_added,
            "term_cards_updated": term_cards_updated,
            "term_cards_limit": supporting_limit,
            "generation": {
                "strategy": "hybrid_guardrailed",
                "llm_cards": llm_generated_count,
                "rule_cards": rule_generated_count,
                "llm_enabled": llm_service is not None,
                "llm_card_limit": llm_card_limit,
            },
            "quality_scores": quality_scores,
            "candidate_diagnostics": {
                "candidate_count": len(terms),
                "selected_count": len(exported_cards),
                "skipped": skipped_candidates[:8],
            },
            "experience": experience,
            "export_decision": {
                "allow_term_cards": bool(export_gate["allow_term_cards"]),
                "reject_reason": export_gate["reject_reason"],
                "reject_message": export_gate["reject_message"],
                "main_threshold": main_threshold,
                "support_threshold": support_threshold,
                "quality_floor": quality_floor,
            },
            "review_records_created": len(created_reviews),
            "review_records": created_reviews,
        }

    def update_memory_card(self, user_id: str, card_id: str, payload: dict[str, Any]) -> Optional[dict[str, Any]]:
        normalized = self._normalize_card_payload(payload=payload)
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, title, content, tags, status, created_at, updated_at
                FROM memory_cards
                WHERE id = ? AND user_id = ?
                LIMIT 1
                """,
                (card_id, user_id),
            ).fetchone()
            if row is None:
                return None
            next_title = normalized["title"] or str(row["title"] or "")
            next_content = normalized["content"] or str(row["content"] or "")
            if normalized["tags"]:
                next_tags = normalized["tags"]
            else:
                try:
                    parsed_tags = json.loads(str(row["tags"] or "[]"))
                    next_tags = [str(item).strip() for item in parsed_tags if str(item).strip()] if isinstance(parsed_tags, list) else []
                except json.JSONDecodeError:
                    next_tags = []
            next_tags_text = json.dumps(next_tags[:8], ensure_ascii=False)
            self._snapshot_card_version(conn=conn, row=row)
            updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            conn.execute(
                """
                UPDATE memory_cards
                SET title = ?, content = ?, tags = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (next_title, next_content, next_tags_text, updated_at, card_id, user_id),
            )
            updated = conn.execute(
                """
                SELECT id, title, content, tags, status, created_at, updated_at
                FROM memory_cards
                WHERE id = ? AND user_id = ?
                LIMIT 1
                """,
                (card_id, user_id),
            ).fetchone()
            if updated:
                self._upsert_vector_row(
                    conn=conn,
                    user_id=user_id,
                    source_type="memory_card",
                    source_id=str(updated["id"]),
                    title=f"记忆卡片-{str(updated['title'] or '记忆卡片')}",
                    content="；".join(
                        item
                        for item in (
                            str(updated["title"] or ""),
                            str(updated["content"] or ""),
                            str(updated["tags"] or ""),
                        )
                        if item
                    ),
                    created_at=str(updated["updated_at"] or updated_at),
                )
            return self._card_row_to_dict(row=updated) if updated else None

    def delete_memory_card(self, user_id: str, card_id: str) -> Optional[dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, title, content, tags, status, created_at, updated_at
                FROM memory_cards
                WHERE id = ? AND user_id = ?
                LIMIT 1
                """,
                (card_id, user_id),
            ).fetchone()
            if row is None:
                return None
            self._snapshot_card_version(conn=conn, row=row)
            updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            conn.execute(
                """
                UPDATE memory_cards
                SET status = 'deleted', updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (updated_at, card_id, user_id),
            )
            deleted = conn.execute(
                """
                SELECT id, title, content, tags, status, created_at, updated_at
                FROM memory_cards
                WHERE id = ? AND user_id = ?
                LIMIT 1
                """,
                (card_id, user_id),
            ).fetchone()
            self._delete_vector_row(conn=conn, user_id=user_id, source_type="memory_card", source_id=str(card_id))
            return self._card_row_to_dict(row=deleted) if deleted else None

    def rollback_memory_card(self, user_id: str, card_id: str, version_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        with self._conn() as conn:
            current = conn.execute(
                """
                SELECT id, user_id, title, content, tags, status, created_at, updated_at
                FROM memory_cards
                WHERE id = ? AND user_id = ?
                LIMIT 1
                """,
                (card_id, user_id),
            ).fetchone()
            if current is None:
                return None
            if version_id:
                version = conn.execute(
                    """
                    SELECT id, title, content, tags, status
                    FROM memory_card_versions
                    WHERE id = ? AND card_id = ? AND user_id = ?
                    LIMIT 1
                    """,
                    (version_id, card_id, user_id),
                ).fetchone()
            else:
                version = conn.execute(
                    """
                    SELECT id, title, content, tags, status
                    FROM memory_card_versions
                    WHERE card_id = ? AND user_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (card_id, user_id),
                ).fetchone()
            if version is None:
                return None
            self._snapshot_card_version(conn=conn, row=current)
            updated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            conn.execute(
                """
                UPDATE memory_cards
                SET title = ?, content = ?, tags = ?, status = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    str(version["title"] or ""),
                    str(version["content"] or ""),
                    str(version["tags"] or "[]"),
                    str(version["status"] or "active"),
                    updated_at,
                    card_id,
                    user_id,
                ),
            )
            restored = conn.execute(
                """
                SELECT id, title, content, tags, status, created_at, updated_at
                FROM memory_cards
                WHERE id = ? AND user_id = ?
                LIMIT 1
                """,
                (card_id, user_id),
            ).fetchone()
            if restored and str(restored["status"] or "active") == "active":
                self._upsert_vector_row(
                    conn=conn,
                    user_id=user_id,
                    source_type="memory_card",
                    source_id=str(restored["id"]),
                    title=f"记忆卡片-{str(restored['title'] or '记忆卡片')}",
                    content="；".join(
                        item
                        for item in (
                            str(restored["title"] or ""),
                            str(restored["content"] or ""),
                            str(restored["tags"] or ""),
                        )
                        if item
                    ),
                    created_at=str(restored["updated_at"] or updated_at),
                )
            else:
                self._delete_vector_row(conn=conn, user_id=user_id, source_type="memory_card", source_id=str(card_id))
            return self._card_row_to_dict(row=restored) if restored else None

    def get_daily_study_plan(self, user_id: str, plan_date: Optional[str] = None) -> Optional[dict[str, Any]]:
        target_date = str(plan_date or datetime.now(UTC).date().isoformat()).strip()
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT p.plan_date, p.goal, p.tasks, p.duration_minutes, p.checkin_question, p.updated_at,
                       COALESCE(c.completed_tasks, 0) AS completed_tasks,
                       COALESCE(c.note, '') AS checkin_note,
                       COALESCE(c.updated_at, '') AS checkin_updated_at
                FROM daily_study_plans
                p LEFT JOIN daily_plan_checkins c ON p.user_id = c.user_id AND p.plan_date = c.plan_date
                WHERE p.user_id = ? AND p.plan_date = ?
                LIMIT 1
                """,
                (user_id, target_date),
            ).fetchone()
        if row is None:
            return None
        tasks_raw = str(row["tasks"] or "[]")
        try:
            parsed_tasks = json.loads(tasks_raw)
            tasks = [str(item).strip() for item in parsed_tasks if str(item).strip()][:3] if isinstance(parsed_tasks, list) else []
        except json.JSONDecodeError:
            tasks = []
        return {
            "plan_date": str(row["plan_date"] or target_date),
            "goal": str(row["goal"] or ""),
            "tasks": tasks,
            "duration_minutes": int(row["duration_minutes"] or 0),
            "checkin_question": str(row["checkin_question"] or ""),
            "completed_tasks": int(row["completed_tasks"] or 0),
            "task_completion_rate": round(int(row["completed_tasks"] or 0) / 3, 4),
            "checkin_note": str(row["checkin_note"] or ""),
            "checkin_updated_at": str(row["checkin_updated_at"] or ""),
            "updated_at": str(row["updated_at"] or ""),
        }

    def upsert_daily_study_plan(self, user_id: str, plan_payload: dict[str, Any], plan_date: Optional[str] = None) -> dict[str, Any]:
        target_date = str(plan_date or datetime.now(UTC).date().isoformat()).strip()
        goal = str(plan_payload.get("goal", "")).strip()[:120]
        checkin_question = str(plan_payload.get("checkin_question", "")).strip()[:160]
        duration_minutes = int(plan_payload.get("duration_minutes", 0) or 0)
        tasks_raw = plan_payload.get("tasks", [])
        tasks: list[str] = []
        if isinstance(tasks_raw, list):
            tasks = [str(item).strip() for item in tasks_raw if str(item).strip()][:3]
        if not goal:
            raise ValueError("goal is required")
        if len(tasks) != 3:
            raise ValueError("tasks must include 3 items")
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")
        if not checkin_question:
            raise ValueError("checkin_question is required")
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO daily_study_plans (
                    user_id, plan_date, goal, tasks, duration_minutes, checkin_question, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, plan_date) DO UPDATE SET
                    goal = excluded.goal,
                    tasks = excluded.tasks,
                    duration_minutes = excluded.duration_minutes,
                    checkin_question = excluded.checkin_question,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    target_date,
                    goal,
                    json.dumps(tasks, ensure_ascii=False),
                    duration_minutes,
                    checkin_question,
                    now,
                    now,
                ),
            )
        saved = self.get_daily_study_plan(user_id=user_id, plan_date=target_date)
        if saved is None:
            raise ValueError("save study plan failed")
        return saved

    def create_review_record(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        focus_topic = str(payload.get("focus_topic", "")).strip()[:80]
        source_question = str(payload.get("source_question", "")).strip()[:400]
        mistake_type = str(payload.get("mistake_type", "")).strip()[:60]
        reason = str(payload.get("reason", "")).strip()[:220]
        fix_action = str(payload.get("fix_action", "")).strip()[:220]
        next_drill = str(payload.get("next_drill", "")).strip()[:220]
        if not focus_topic:
            raise ValueError("focus_topic is required")
        if not source_question:
            raise ValueError("source_question is required")
        if not mistake_type or not reason or not fix_action or not next_drill:
            raise ValueError("review template fields are required")
        created_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        repeat_raw = payload.get("is_repeat_mistake")
        inferred_repeat = 0
        with self._conn() as conn:
            if repeat_raw is None:
                repeated = conn.execute(
                    """
                    SELECT 1
                    FROM review_records
                    WHERE user_id = ? AND focus_topic = ? AND mistake_type = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (user_id, focus_topic, mistake_type),
                ).fetchone()
                inferred_repeat = 1 if repeated else 0
            else:
                inferred_repeat = 1 if bool(repeat_raw) else 0
            result = conn.execute(
                """
                INSERT INTO review_records (
                    user_id, focus_topic, source_question, mistake_type, reason, fix_action, next_drill, is_repeat_mistake, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    focus_topic,
                    source_question,
                    mistake_type,
                    reason,
                    fix_action,
                    next_drill,
                    inferred_repeat,
                    created_at,
                ),
            )
            row = conn.execute(
                """
                SELECT id, focus_topic, source_question, mistake_type, reason, fix_action, next_drill, is_repeat_mistake, created_at
                FROM review_records
                WHERE id = ?
                LIMIT 1
                """,
                (int(result.lastrowid),),
            ).fetchone()
            if row:
                self._upsert_vector_row(
                    conn=conn,
                    user_id=user_id,
                    source_type="review",
                    source_id=str(row["id"]),
                    title=f"错题复盘-{str(row['focus_topic'] or '复盘记录')}",
                    content="；".join(
                        item
                        for item in (
                            str(row["source_question"] or ""),
                            str(row["reason"] or ""),
                            str(row["fix_action"] or ""),
                        )
                        if item
                    ),
                    created_at=str(row["created_at"] or created_at),
                )
        if row is None:
            raise ValueError("create review record failed")
        return {
            "id": str(row["id"]),
            "focus_topic": str(row["focus_topic"] or ""),
            "source_question": str(row["source_question"] or ""),
            "mistake_type": str(row["mistake_type"] or ""),
            "reason": str(row["reason"] or ""),
            "fix_action": str(row["fix_action"] or ""),
            "next_drill": str(row["next_drill"] or ""),
            "is_repeat_mistake": bool(int(row["is_repeat_mistake"] or 0)),
            "created_at": str(row["created_at"] or ""),
        }

    def list_review_records(self, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, focus_topic, source_question, mistake_type, reason, fix_action, next_drill, is_repeat_mistake, created_at
                FROM review_records
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, max(1, min(limit, 100))),
            ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "focus_topic": str(row["focus_topic"] or ""),
                "source_question": str(row["source_question"] or ""),
                "mistake_type": str(row["mistake_type"] or ""),
                "reason": str(row["reason"] or ""),
                "fix_action": str(row["fix_action"] or ""),
                "next_drill": str(row["next_drill"] or ""),
                "is_repeat_mistake": bool(int(row["is_repeat_mistake"] or 0)),
                "created_at": str(row["created_at"] or ""),
            }
            for row in rows
        ]

    def upsert_daily_plan_checkin(self, user_id: str, plan_date: str, completed_tasks: int, note: str = "") -> dict[str, Any]:
        target_date = str(plan_date).strip()
        completed = max(0, min(int(completed_tasks), 3))
        checkin_note = str(note).strip()[:240]
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO daily_plan_checkins (user_id, plan_date, completed_tasks, note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, plan_date) DO UPDATE SET
                    completed_tasks = excluded.completed_tasks,
                    note = excluded.note,
                    updated_at = excluded.updated_at
                """,
                (user_id, target_date, completed, checkin_note, now, now),
            )
            row = conn.execute(
                """
                SELECT plan_date, completed_tasks, note, updated_at
                FROM daily_plan_checkins
                WHERE user_id = ? AND plan_date = ?
                LIMIT 1
                """,
                (user_id, target_date),
            ).fetchone()
        if row is None:
            raise ValueError("save plan checkin failed")
        return {
            "plan_date": str(row["plan_date"] or target_date),
            "completed_tasks": int(row["completed_tasks"] or 0),
            "task_completion_rate": round(int(row["completed_tasks"] or 0) / 3, 4),
            "note": str(row["note"] or ""),
            "updated_at": str(row["updated_at"] or ""),
        }

    def aggregate_weekly_learning(self, user_id: str, week_start: str, week_end: str) -> dict[str, Any]:
        start = str(week_start).strip()
        end = str(week_end).strip()
        start_date = datetime.fromisoformat(start).date()
        end_date = datetime.fromisoformat(end).date()
        period_days = max(1, (end_date - start_date).days + 1)
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days - 1)
        prev_start_text = prev_start.isoformat()
        prev_end_text = prev_end.isoformat()
        with self._conn() as conn:
            plan_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS plan_days,
                    COALESCE(SUM(duration_minutes), 0) AS total_minutes
                FROM daily_study_plans
                WHERE user_id = ? AND plan_date >= ? AND plan_date <= ?
                """,
                (user_id, start, end),
            ).fetchone()
            checkin_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS checkin_days,
                    COALESCE(SUM(completed_tasks), 0) AS completed_tasks_total
                FROM daily_plan_checkins
                WHERE user_id = ? AND plan_date >= ? AND plan_date <= ?
                """,
                (user_id, start, end),
            ).fetchone()
            review_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS review_count,
                    COALESCE(SUM(is_repeat_mistake), 0) AS repeat_count
                FROM review_records
                WHERE user_id = ? AND substr(created_at, 1, 10) >= ? AND substr(created_at, 1, 10) <= ?
                """,
                (user_id, start, end),
            ).fetchone()
            prev_review_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS review_count,
                    COALESCE(SUM(is_repeat_mistake), 0) AS repeat_count
                FROM review_records
                WHERE user_id = ? AND substr(created_at, 1, 10) >= ? AND substr(created_at, 1, 10) <= ?
                """,
                (user_id, prev_start_text, prev_end_text),
            ).fetchone()
            mistake_rows = conn.execute(
                """
                SELECT mistake_type, COUNT(*) AS count
                FROM review_records
                WHERE user_id = ? AND substr(created_at, 1, 10) >= ? AND substr(created_at, 1, 10) <= ?
                GROUP BY mistake_type
                ORDER BY count DESC
                LIMIT 4
                """,
                (user_id, start, end),
            ).fetchall()
            topic_rows = conn.execute(
                """
                SELECT focus_topic, COUNT(*) AS count
                FROM review_records
                WHERE user_id = ? AND substr(created_at, 1, 10) >= ? AND substr(created_at, 1, 10) <= ?
                GROUP BY focus_topic
                ORDER BY count DESC
                LIMIT 3
                """,
                (user_id, start, end),
            ).fetchall()
        mistake_distribution = {
            str(row["mistake_type"] or ""): int(row["count"] or 0)
            for row in mistake_rows
            if str(row["mistake_type"] or "").strip()
        }
        top_topics = [
            str(row["focus_topic"] or "")
            for row in topic_rows
            if str(row["focus_topic"] or "").strip()
        ]
        plan_days = int(plan_row["plan_days"] or 0) if plan_row else 0
        review_count = int(review_row["review_count"] or 0) if review_row else 0
        repeat_count = int(review_row["repeat_count"] or 0) if review_row else 0
        prev_review_count = int(prev_review_row["review_count"] or 0) if prev_review_row else 0
        prev_repeat_count = int(prev_review_row["repeat_count"] or 0) if prev_review_row else 0
        completed_tasks_total = int(checkin_row["completed_tasks_total"] or 0) if checkin_row else 0
        total_planned_tasks = max(0, plan_days * 3)
        task_completion_rate = round(completed_tasks_total / total_planned_tasks, 4) if total_planned_tasks else 0.0
        repeat_mistake_rate = round(repeat_count / review_count, 4) if review_count else 0.0
        prev_repeat_rate = round(prev_repeat_count / prev_review_count, 4) if prev_review_count else 0.0
        task_completion_target = 0.7
        repeat_mistake_drop_target = 0.2
        repeat_mistake_drop_ratio = (
            round((prev_repeat_rate - repeat_mistake_rate) / prev_repeat_rate, 4) if prev_repeat_rate > 0 else 0.0
        )
        is_task_completion_target_met = task_completion_rate >= task_completion_target
        has_repeat_baseline = prev_repeat_rate > 0
        is_repeat_mistake_target_met = has_repeat_baseline and repeat_mistake_drop_ratio >= repeat_mistake_drop_target
        nudge_feedback = self.get_nudge_feedback_summary(user_id=user_id, days=7)
        return {
            "week_start": start,
            "week_end": end,
            "plan_days": plan_days,
            "total_minutes": int(plan_row["total_minutes"] or 0) if plan_row else 0,
            "checkin_days": int(checkin_row["checkin_days"] or 0) if checkin_row else 0,
            "completed_tasks_total": completed_tasks_total,
            "task_completion_rate": task_completion_rate,
            "review_count": review_count,
            "repeat_mistake_count": repeat_count,
            "repeat_mistake_rate": repeat_mistake_rate,
            "previous_repeat_mistake_rate": prev_repeat_rate,
            "repeat_mistake_rate_change": round(repeat_mistake_rate - prev_repeat_rate, 4),
            "repeat_mistake_drop_ratio": repeat_mistake_drop_ratio,
            "task_completion_target": task_completion_target,
            "repeat_mistake_drop_target": repeat_mistake_drop_target,
            "has_repeat_baseline": has_repeat_baseline,
            "is_task_completion_target_met": is_task_completion_target_met,
            "is_repeat_mistake_target_met": is_repeat_mistake_target_met,
            "is_weekly_goal_met": is_task_completion_target_met and is_repeat_mistake_target_met,
            "nudge_sent_count_7d": int(nudge_feedback.get("sent_count", 0) or 0),
            "nudge_reengaged_count_7d": int(nudge_feedback.get("reengaged_count", 0) or 0),
            "nudge_reengagement_rate_7d": float(nudge_feedback.get("reengagement_rate", 0.0) or 0.0),
            "mistake_distribution": mistake_distribution,
            "top_topics": top_topics,
        }

    def get_weekly_report(self, user_id: str, week_start: str, week_end: str) -> Optional[dict[str, Any]]:
        start = str(week_start).strip()
        end = str(week_end).strip()
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT week_start, week_end, summary, highlights, next_week_focus, coach_message, stats_snapshot, updated_at
                FROM weekly_reports
                WHERE user_id = ? AND week_start = ? AND week_end = ?
                LIMIT 1
                """,
                (user_id, start, end),
            ).fetchone()
        if row is None:
            return None
        highlights_raw = str(row["highlights"] or "[]")
        next_focus_raw = str(row["next_week_focus"] or "[]")
        stats_raw = str(row["stats_snapshot"] or "{}")
        try:
            highlights = json.loads(highlights_raw)
        except json.JSONDecodeError:
            highlights = []
        try:
            next_week_focus = json.loads(next_focus_raw)
        except json.JSONDecodeError:
            next_week_focus = []
        try:
            stats_snapshot = json.loads(stats_raw)
        except json.JSONDecodeError:
            stats_snapshot = {}
        return {
            "week_start": str(row["week_start"] or start),
            "week_end": str(row["week_end"] or end),
            "summary": str(row["summary"] or ""),
            "highlights": [str(item).strip() for item in highlights if str(item).strip()] if isinstance(highlights, list) else [],
            "next_week_focus": [str(item).strip() for item in next_week_focus if str(item).strip()] if isinstance(next_week_focus, list) else [],
            "coach_message": str(row["coach_message"] or ""),
            "stats_snapshot": stats_snapshot if isinstance(stats_snapshot, dict) else {},
            "updated_at": str(row["updated_at"] or ""),
        }

    def upsert_weekly_report(
        self,
        user_id: str,
        week_start: str,
        week_end: str,
        payload: dict[str, Any],
        stats_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        start = str(week_start).strip()
        end = str(week_end).strip()
        summary = str(payload.get("summary", "")).strip()[:240]
        coach_message = str(payload.get("coach_message", "")).strip()[:220]
        highlights_raw = payload.get("highlights", [])
        next_focus_raw = payload.get("next_week_focus", [])
        highlights = [str(item).strip() for item in highlights_raw if str(item).strip()][:3] if isinstance(highlights_raw, list) else []
        next_week_focus = [str(item).strip() for item in next_focus_raw if str(item).strip()][:3] if isinstance(next_focus_raw, list) else []
        if not summary:
            raise ValueError("summary is required")
        if len(highlights) != 3:
            raise ValueError("highlights must include 3 items")
        if len(next_week_focus) != 3:
            raise ValueError("next_week_focus must include 3 items")
        if not coach_message:
            raise ValueError("coach_message is required")
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO weekly_reports (
                    user_id, week_start, week_end, summary, highlights, next_week_focus,
                    coach_message, stats_snapshot, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, week_start, week_end) DO UPDATE SET
                    summary = excluded.summary,
                    highlights = excluded.highlights,
                    next_week_focus = excluded.next_week_focus,
                    coach_message = excluded.coach_message,
                    stats_snapshot = excluded.stats_snapshot,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    start,
                    end,
                    summary,
                    json.dumps(highlights, ensure_ascii=False),
                    json.dumps(next_week_focus, ensure_ascii=False),
                    coach_message,
                    json.dumps(stats_snapshot, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        saved = self.get_weekly_report(user_id=user_id, week_start=start, week_end=end)
        if saved is None:
            raise ValueError("save weekly report failed")
        return saved

    def _seed_evaluation_cases(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT COUNT(1) AS count FROM evaluation_cases").fetchone()
        existing = int(row["count"]) if row else 0
        if existing >= 30:
            return
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        topics = [
            ("教育学原理", "先结论后口诀"),
            ("教育心理学", "先结论后例题"),
            ("课程与教学论", "先框架后步骤"),
            ("德育与班级管理", "先原则后策略"),
            ("教育法律法规", "先法条后应用"),
            ("中外教育史", "先时间线后人物"),
            ("教学设计", "先目标后活动"),
            ("课堂评价", "先标准后案例"),
            ("教师职业道德", "先规范后情境"),
            ("教育研究方法", "先定义后对比"),
        ]
        case_templates = [
            ("基础概念题", "请用口语化方式解释{topic}的核心概念，并给一个易记钩子"),
            ("题后复盘题", "这道{topic}题我又错了，帮我做三步复盘并给下次操作清单"),
            ("限时策略题", "考场上遇到{topic}综合题，怎样在3分钟内拿到基础分"),
        ]
        index = 0
        for topic, style in topics:
            for difficulty, question_template in case_templates:
                index += 1
                question = question_template.format(topic=topic)
                reference_points = [
                    f"先点明{topic}核心结论",
                    "给出可执行步骤或复盘动作",
                    "包含记忆钩子或易错提醒",
                ]
                conn.execute(
                    """
                    INSERT OR IGNORE INTO evaluation_cases (
                        case_code, focus_topic, question, reference_points, expected_style, difficulty, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"CASE-{index:03d}",
                        topic,
                        question,
                        json.dumps(reference_points, ensure_ascii=False),
                        style,
                        difficulty,
                        now,
                    ),
                )

    def list_evaluation_cases(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT id, case_code, focus_topic, question, reference_points, expected_style, difficulty
                FROM evaluation_cases
                ORDER BY id ASC
                LIMIT ?
                """,
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "case_code": str(row["case_code"] or ""),
                "focus_topic": str(row["focus_topic"] or ""),
                "question": str(row["question"] or ""),
                "reference_points": json.loads(str(row["reference_points"] or "[]")),
                "expected_style": str(row["expected_style"] or ""),
                "difficulty": str(row["difficulty"] or ""),
            }
            for row in rows
        ]

    def get_evaluation_case(self, case_id: str) -> Optional[dict[str, Any]]:
        case_id_int = int(case_id)
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT id, case_code, focus_topic, question, reference_points, expected_style, difficulty
                FROM evaluation_cases
                WHERE id = ?
                LIMIT 1
                """,
                (case_id_int,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": str(row["id"]),
            "case_code": str(row["case_code"] or ""),
            "focus_topic": str(row["focus_topic"] or ""),
            "question": str(row["question"] or ""),
            "reference_points": json.loads(str(row["reference_points"] or "[]")),
            "expected_style": str(row["expected_style"] or ""),
            "difficulty": str(row["difficulty"] or ""),
        }

    def create_evaluation_run(
        self,
        user_id: str,
        case_id: str,
        variant_label: str,
        answer: str,
        score_detail: dict[str, Any],
        total_score: float,
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        clean_label = str(variant_label or "default").strip()[:40] or "default"
        clean_answer = str(answer).strip()[:3000]
        if not clean_answer:
            raise ValueError("answer is required")
        case_id_int = int(case_id)
        with self._conn() as conn:
            result = conn.execute(
                """
                INSERT INTO evaluation_runs (
                    user_id, case_id, variant_label, answer, score_detail, total_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    case_id_int,
                    clean_label,
                    clean_answer,
                    json.dumps(score_detail, ensure_ascii=False),
                    float(total_score),
                    now,
                ),
            )
            run_row = conn.execute(
                """
                SELECT id, user_id, case_id, variant_label, answer, score_detail, total_score, created_at
                FROM evaluation_runs
                WHERE id = ?
                LIMIT 1
                """,
                (int(result.lastrowid),),
            ).fetchone()
        if run_row is None:
            raise ValueError("save evaluation run failed")
        return {
            "id": str(run_row["id"]),
            "user_id": str(run_row["user_id"] or ""),
            "case_id": str(run_row["case_id"] or ""),
            "variant_label": str(run_row["variant_label"] or ""),
            "answer": str(run_row["answer"] or ""),
            "score_detail": json.loads(str(run_row["score_detail"] or "{}")),
            "total_score": float(run_row["total_score"] or 0.0),
            "created_at": str(run_row["created_at"] or ""),
        }

    def summarize_evaluation_runs(self, user_id: str, limit: int = 200) -> dict[str, Any]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT variant_label, total_score, created_at
                FROM evaluation_runs
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, max(1, min(limit, 500))),
            ).fetchall()
        by_variant: dict[str, dict[str, Any]] = {}
        recent_runs: list[dict[str, Any]] = []
        for row in rows:
            label = str(row["variant_label"] or "default")
            score = float(row["total_score"] or 0.0)
            created_at = str(row["created_at"] or "")
            if label not in by_variant:
                by_variant[label] = {
                    "variant_label": label,
                    "run_count": 0,
                    "avg_score": 0.0,
                    "best_score": 0.0,
                    "latest_score": score,
                }
            item = by_variant[label]
            item["run_count"] = int(item["run_count"]) + 1
            item["avg_score"] = float(item["avg_score"]) + score
            item["best_score"] = max(float(item["best_score"]), score)
            recent_runs.append({"variant_label": label, "total_score": score, "created_at": created_at})
        variants: list[dict[str, Any]] = []
        for item in by_variant.values():
            run_count = int(item["run_count"] or 1)
            avg_score = round(float(item["avg_score"]) / run_count, 4)
            variants.append(
                {
                    "variant_label": str(item["variant_label"]),
                    "run_count": run_count,
                    "avg_score": avg_score,
                    "best_score": round(float(item["best_score"]), 4),
                    "latest_score": round(float(item["latest_score"]), 4),
                }
            )
        variants.sort(key=lambda x: (-float(x["avg_score"]), -int(x["run_count"])))
        best_variant = variants[0]["variant_label"] if variants else "N/A"
        return {
            "total_runs": len(rows),
            "best_variant": best_variant,
            "variants": variants,
            "recent_runs": recent_runs[:20],
        }
