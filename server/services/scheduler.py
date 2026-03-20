import os
from datetime import datetime, timedelta, timezone
from typing import Optional

UTC = timezone.utc

from apscheduler.schedulers.background import BackgroundScheduler

from server.services.llm import LLMService
from server.services.memory import MemoryService


class ProactiveScheduler:
    def __init__(self, memory_service: MemoryService, llm_service: LLMService) -> None:
        self.memory_service = memory_service
        self.llm_service = llm_service
        self.scheduler = BackgroundScheduler()
        self.interval_minutes = int(os.getenv("MINDSHADOW_NUDGE_INTERVAL_MINUTES", "60"))
        self.dnd_start = 23
        self.dnd_end = 8

    def start(self) -> None:
        if self.scheduler.running:
            return
        self.scheduler.add_job(self._nudge_job, "interval", minutes=max(1, self.interval_minutes), id="mindshadow_nudge")
        self.scheduler.start()

    def _in_dnd(self, now: datetime) -> bool:
        hour = now.hour
        return hour >= self.dnd_start or hour < self.dnd_end

    def _parse_ts(self, value: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _nudge_level(self, now: datetime, last_activity_dt: datetime) -> str:
        idle_hours = (now - last_activity_dt).total_seconds() / 3600
        if idle_hours >= 48:
            return "urgent"
        if idle_hours >= 24:
            return "focus"
        return "gentle"

    def _can_nudge(self, user_id: str, now: datetime) -> bool:
        if self._in_dnd(now):
            return False
        last_sent = self.memory_service.get_last_sent_notification_ts(user_id)
        if not last_sent:
            return True
        last_sent_dt = self._parse_ts(last_sent)
        return now - last_sent_dt >= timedelta(hours=6)

    def _resolve_trigger_context(self, user_id: str, now: datetime) -> Optional[dict[str, str]]:
        last_activity = self.memory_service.get_last_user_activity_ts(user_id=user_id)
        if not last_activity:
            return None
        last_activity_dt = self._parse_ts(last_activity)
        user_profile = self.memory_service.get_user_profile(user_id=user_id)
        raw_exam_date = str(user_profile.get("exam_date", "")).strip()
        if raw_exam_date:
            try:
                exam_date = datetime.fromisoformat(raw_exam_date).date()
                days_left = (exam_date - now.date()).days
                if 0 <= days_left <= 14:
                    if days_left <= 3:
                        nudge_level = "urgent"
                    elif days_left <= 7:
                        nudge_level = "focus"
                    else:
                        nudge_level = "gentle"
                    return {"trigger_type": "exam_window", "nudge_level": nudge_level}
            except ValueError:
                pass
        repeat_count = self.memory_service.get_recent_repeat_mistake_count(user_id=user_id, days=3)
        if repeat_count >= 2:
            nudge_level = "urgent" if repeat_count >= 4 else "focus"
            return {"trigger_type": "repeat_mistake", "nudge_level": nudge_level}
        if now - last_activity_dt >= timedelta(hours=12):
            return {"trigger_type": "inactivity", "nudge_level": self._nudge_level(now=now, last_activity_dt=last_activity_dt)}
        return None

    def _apply_feedback_loop(self, user_id: str, trigger_type: str, nudge_level: str) -> str:
        summary = self.memory_service.get_nudge_feedback_summary(user_id=user_id, days=14)
        strategy = self.memory_service.get_nudge_level_feedback(
            user_id=user_id,
            trigger_type=trigger_type,
            nudge_level=nudge_level,
            days=14,
        )
        sent_count = int(summary.get("sent_count", 0) or 0)
        strategy_sent = int(strategy.get("sent_count", 0) or 0)
        reengagement_rate = float(summary.get("reengagement_rate", 0.0) or 0.0)
        strategy_rate = float(strategy.get("reengagement_rate", 0.0) or 0.0)
        if sent_count < 3:
            return nudge_level
        level_rank = {"gentle": 0, "focus": 1, "urgent": 2}
        rank_level = {0: "gentle", 1: "focus", 2: "urgent"}
        current_rank = level_rank.get(nudge_level, 1)
        effective_rate = strategy_rate if strategy_sent >= 2 else reengagement_rate
        min_rank = 1 if trigger_type == "exam_window" else 0
        if effective_rate < 0.3:
            return rank_level.get(min(2, current_rank + 1), "urgent")
        if effective_rate > 0.7:
            return rank_level.get(max(min_rank, current_rank - 1), "gentle")
        return nudge_level

    def _nudge_job(self) -> None:
        now = datetime.now(UTC)
        trigger_prefix = {
            "exam_window": "【考前窗口提醒】",
            "repeat_mistake": "【错题反复预警】",
            "inactivity": "【学习节奏提醒】",
        }
        for user_id in self.memory_service.get_active_user_ids():
            if not self._can_nudge(user_id=user_id, now=now):
                continue
            context = self._resolve_trigger_context(user_id=user_id, now=now)
            if context is None:
                continue
            trigger_type = context["trigger_type"]
            nudge_level = self._apply_feedback_loop(
                user_id=user_id,
                trigger_type=trigger_type,
                nudge_level=context["nudge_level"],
            )
            focus_topic = self.memory_service.get_focus_topic(user_id)
            user_profile = self.memory_service.get_user_profile(user_id=user_id)
            recent_messages = self.memory_service.get_recent_messages(user_id=user_id, limit=8)
            hook = self.llm_service.generate_hook(
                focus_topic=focus_topic,
                user_profile=user_profile,
                nudge_level=nudge_level,
                recent_messages=recent_messages,
            )
            content = f"{trigger_prefix.get(trigger_type, '【学习提醒】')}{hook}"
            self.memory_service.queue_notification(
                user_id=user_id,
                content=content,
                trigger_type=trigger_type,
                nudge_level=nudge_level,
            )
