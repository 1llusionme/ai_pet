import json
import os
import random
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterator, Optional

from server.services.persona_config import PersonaConfigService


class LLMService:
    def __init__(self) -> None:
        self.provider = os.getenv("MINDSHADOW_LLM_PROVIDER", "mock").strip().lower()
        self.model_name = os.getenv("MINDSHADOW_LLM_MODEL", "gpt-4o-mini")
        self.api_key = os.getenv("MINDSHADOW_LLM_API_KEY", "").strip()
        self.base_url = os.getenv("MINDSHADOW_LLM_BASE_URL", "https://api.openai.com/v1/chat/completions").strip()
        self.timeout_seconds = int(os.getenv("MINDSHADOW_LLM_TIMEOUT_SECONDS", "30"))
        self.verify_ssl = os.getenv("MINDSHADOW_LLM_VERIFY_SSL", "true").strip().lower() != "false"
        self.chat_max_tokens = int(os.getenv("MINDSHADOW_LLM_CHAT_MAX_TOKENS", "680"))
        self.last_error = ""
        self.last_response_source = "mock"
        self.persona_config_service = PersonaConfigService()

    def _format_learning_reply(self, conclusion: str, reason: str, actions: list[str]) -> str:
        normalized_actions = [str(item).strip() for item in actions if str(item).strip()][:3]
        if not normalized_actions:
            normalized_actions = ["先把题干里的关键词圈出来，再说你最不确定的一步。"]
        lines: list[str] = [
            "### 结论",
            conclusion.strip() or "先把核心考点抓住，再推进到做题。",
            "",
            "### 为什么",
            reason.strip() or "先确认依据，后面才不会越学越乱。",
            "",
            "### 怎么做",
        ]
        for action in normalized_actions:
            lines.append(f"- {action}")
        return "\n".join(lines)

    def chat(
        self,
        recent_messages: list[dict[str, Any]],
        focus_topic: str,
        web_context: Optional[list[dict[str, str]]] = None,
        kb_context: Optional[list[dict[str, str]]] = None,
        semantic_context: Optional[list[dict[str, str]]] = None,
        user_profile: Optional[dict[str, Any]] = None,
    ) -> str:
        normalized_topic = self._normalize_focus_topic(focus_topic=focus_topic, recent_messages=recent_messages)
        if self._remote_enabled():
            remote = self._remote_chat_reply(
                recent_messages=recent_messages,
                focus_topic=normalized_topic,
                web_context=web_context or [],
                kb_context=kb_context or [],
                semantic_context=semantic_context or [],
                user_profile=user_profile or {},
            )
            if remote:
                self.last_response_source = "remote"
                return remote
        self.last_response_source = "mock"
        latest_user_text = ""
        for message in reversed(recent_messages):
            if message["role"] == "user":
                latest_user_text = message["content"]
                break
        if not latest_user_text:
            profile = user_profile or {}
            style = str(profile.get("response_style", "")).strip()
            exam_goal = str(profile.get("exam_goal", "")).strip()
            style_hint = f"我会按「{style}」来讲。" if style else "我会先给结论，再带你一步步过。"
            goal_hint = f"咱们朝着{exam_goal}继续冲。" if exam_goal else "今天继续拿下教编高频考点。"
            return self._format_learning_reply(
                conclusion=f"我在这儿，{goal_hint}",
                reason=style_hint,
                actions=["告诉我你现在最卡的题型，我直接给你可执行拆解。"],
            )
        lower = latest_user_text.lower()
        if "不懂" in latest_user_text or "卡住" in latest_user_text or "难" in latest_user_text:
            return self._format_learning_reply(
                conclusion=f"这块确实是「{normalized_topic}」的高频卡点，但可以快速拆开。",
                reason="先拆最小步骤再做题，正确率会更稳定。",
                actions=["先说你最容易卡住的那一句题干。", "我给你30秒记忆钩子。", "再做1道同类题验证。"],
            )
        if "谢谢" in latest_user_text or "懂了" in latest_user_text or "明白" in latest_user_text:
            return self._format_learning_reply(
                conclusion=f"很棒，「{normalized_topic}」你已经稳住一大半了。",
                reason="趁记忆窗口还在，立刻做一次小测最容易巩固。",
                actions=["我现在出1道同类题给你。", "你先口头说出判断依据。"],
            )
        if "hi" in lower or "hello" in lower or "你好" in latest_user_text:
            return self._format_learning_reply(
                conclusion=f"在的，我们继续冲「{normalized_topic}」。",
                reason="先对齐你当前卡点，学习效率会高很多。",
                actions=["告诉我你要突破概念、审题还是解题步骤。"],
            )
        if kb_context:
            first = kb_context[0]
            source = first.get("title", "教编知识库")
            page = first.get("page", "")
            page_hint = f"第{page}页" if page else "对应章节"
            style = str((user_profile or {}).get("response_style", "")).strip()
            style_hint = f"我会按你偏好的「{style}」来讲。" if style else "我会按先结论后步骤来讲。"
            return self._format_learning_reply(
                conclusion=f"我已定位到「{source}」的{page_hint}，先用这条依据帮你定考点。",
                reason=style_hint,
                actions=["先听速记口诀版。", "再做一道同类题巩固。"],
            )
        if semantic_context:
            first = semantic_context[0]
            source = first.get("title", "历史记忆")
            return self._format_learning_reply(
                conclusion=f"我先回看了你的历史记录，当前和「{source}」最相关。",
                reason=f"沿用你之前在「{normalized_topic}」有效的方法，复习速度会更快。",
                actions=["先来30秒口述版。", "再用1道题做验证。"],
            )
        if web_context:
            first = web_context[0]
            source = first.get("title", "联网资料")
            return self._format_learning_reply(
                conclusion=f"我补充了联网信息，当前关键线索来自「{source}」。",
                reason=f"先拿到「{normalized_topic}」结论，再做推导不容易走偏。",
                actions=["先听考点结论版。", "再看解题推导版。"],
            )
        return self._format_learning_reply(
            conclusion=f"收到，我们就从「{normalized_topic}」开始。",
            reason="先结论后练题，最适合现在快速提分。",
            actions=["我先给你核心结论。", "你用自己的话复述一遍。", "我再给你一道同类题。"],
        )

    def chat_stream(
        self,
        recent_messages: list[dict[str, Any]],
        focus_topic: str,
        web_context: Optional[list[dict[str, str]]] = None,
        kb_context: Optional[list[dict[str, str]]] = None,
        semantic_context: Optional[list[dict[str, str]]] = None,
        user_profile: Optional[dict[str, Any]] = None,
    ) -> tuple[str, Iterator[str]]:
        normalized_topic = self._normalize_focus_topic(focus_topic=focus_topic, recent_messages=recent_messages)
        web_items = web_context or []
        kb_items = kb_context or []
        profile = user_profile or {}
        if self._remote_enabled():
            messages = self._build_remote_chat_messages(
                recent_messages=recent_messages,
                focus_topic=normalized_topic,
                web_context=web_items,
                kb_context=kb_items,
                semantic_context=semantic_context or [],
                user_profile=profile,
            )
            remote_stream = self._post_chat_completion_stream(
                messages=messages,
                temperature=0.7,
                max_tokens=self.chat_max_tokens,
            )
            if remote_stream is not None:
                self.last_response_source = "remote"
                return "remote", remote_stream
        fallback = self.chat(
            recent_messages=recent_messages,
            focus_topic=normalized_topic,
            web_context=web_items,
            kb_context=kb_items,
            semantic_context=semantic_context or [],
            user_profile=profile,
        )
        return self.last_response_source, self._chunk_text(fallback)

    def answer_with_image(
        self,
        question: str,
        image_url: str,
        web_context: Optional[list[dict[str, str]]] = None,
        kb_context: Optional[list[dict[str, str]]] = None,
        user_profile: Optional[dict[str, Any]] = None,
    ) -> str:
        if self._remote_enabled():
            remote = self._remote_vision_reply(
                question=question,
                image_url=image_url,
                web_context=web_context or [],
                kb_context=kb_context or [],
                user_profile=user_profile or {},
            )
            if remote:
                self.last_response_source = "remote"
                return remote
        self.last_response_source = "mock"
        if kb_context:
            first = kb_context[0]
            source = first.get("title", "教编知识库")
            return self._format_learning_reply(
                conclusion=f"我已收到图片，结合「{source}」可以先定位考点和题型。",
                reason="先判定题型再拆步骤，最能避免无效刷题。",
                actions=["告诉我你最卡在审题、回忆还是解题步骤。"],
            )
        return self._format_learning_reply(
            conclusion=f"我已收到图片，先围绕你的问题「{question}」定位关键考点。",
            reason="把你最不确定的步骤先说出来，我能更快精准纠偏。",
            actions=["先说题干里你最不确定的一句。", "我按步骤带你拆解。"],
        )

    def search_web_context(self, question: str) -> list[dict[str, str]]:
        trimmed = question.strip()
        if not trimmed:
            return []
        if not self._should_search_web(trimmed):
            return []
        query = urllib.parse.quote(trimmed[:120])
        endpoint = f"https://api.duckduckgo.com/?q={query}&format=json&no_html=1&skip_disambig=1"
        try:
            with urllib.request.urlopen(endpoint, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
            sources: list[dict[str, str]] = []
            abstract = str(payload.get("AbstractText", "")).strip()
            abstract_url = str(payload.get("AbstractURL", "")).strip()
            heading = str(payload.get("Heading", "")).strip() or "DuckDuckGo 摘要"
            if abstract:
                sources.append({"title": heading, "url": abstract_url, "snippet": abstract[:220]})
            related = payload.get("RelatedTopics", [])
            for topic in related:
                if not isinstance(topic, dict):
                    continue
                text = str(topic.get("Text", "")).strip()
                url = str(topic.get("FirstURL", "")).strip()
                if text:
                    sources.append({"title": text[:32], "url": url, "snippet": text[:220]})
                if len(sources) >= 3:
                    break
            return sources[:3]
        except Exception:
            return []

    def summarize_learning_text(self, content: str) -> dict[str, Any]:
        if self._remote_enabled():
            remote = self._remote_summarize(content=content)
            if remote:
                self.last_response_source = "remote"
                return remote
        self.last_response_source = "mock"
        clean = " ".join(content.replace("\n", " ").split())
        topic_seed = clean[:30] if clean else "未命名主题"
        topic = topic_seed if len(topic_seed) < 24 else topic_seed[:24] + "..."
        concepts: list[str] = []
        segments = [seg.strip() for seg in content.split("\n") if seg.strip()]
        for seg in segments:
            normalized = seg[:48]
            if normalized and normalized not in concepts:
                concepts.append(normalized)
            if len(concepts) == 3:
                break
        while len(concepts) < 3:
            concepts.append(f"{topic} - 关键点{len(concepts)+1}")
        confusion_risk = "High" if len(content) < 120 else "Medium"
        return {"topic": topic, "concepts": concepts, "confusion_risk": confusion_risk}

    def ingest_ack(self, topic: str, concepts: list[str]) -> str:
        first = concepts[0] if concepts else topic
        return f"我吸收完了。你这次重点是「{topic}」，先从「{first}」开始巩固，晚点我会抽查你。"

    def generate_hook(
        self,
        focus_topic: str,
        user_profile: Optional[dict[str, Any]] = None,
        nudge_level: str = "gentle",
    ) -> str:
        normalized_topic = self._normalize_focus_topic(focus_topic=focus_topic, recent_messages=[])
        profile = user_profile or {}
        if self._remote_enabled():
            remote = self._remote_hook(focus_topic=normalized_topic, user_profile=profile, nudge_level=nudge_level)
            if remote:
                self.last_response_source = "remote"
                return remote
        self.last_response_source = "mock"
        goal = str(profile.get("exam_goal", "")).strip()
        weak_points_raw = profile.get("weak_points", [])
        weak_points = [str(item).strip() for item in weak_points_raw if str(item).strip()] if isinstance(weak_points_raw, list) else []
        level_text_map = {
            "gentle": "轻量复盘",
            "focus": "集中突破",
            "urgent": "优先补齐",
        }
        level_hint = level_text_map.get(nudge_level, "轻量复盘")
        target_hint = f"冲刺{goal}，" if goal else ""
        weak_hint = f"先拿下「{weak_points[0]}」，" if weak_points else ""
        hooks = [
            f"{target_hint}{weak_hint}{level_hint}：关于「{normalized_topic}」，如果把前提反过来，会发生什么？",
            f"{target_hint}{weak_hint}{level_hint}：给你个快问快答，{normalized_topic}里最容易忽略的一步是什么？",
            f"{target_hint}{weak_hint}{level_hint}：你最近在练「{normalized_topic}」，来个30秒小挑战？",
        ]
        return random.choice(hooks)

    def generate_daily_plan(self, focus_topic: str, user_profile: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        normalized_topic = self._normalize_focus_topic(focus_topic=focus_topic, recent_messages=[])
        profile = user_profile or {}
        if self._remote_enabled():
            remote = self._remote_daily_plan(focus_topic=normalized_topic, user_profile=profile)
            if remote:
                self.last_response_source = "remote"
                return remote
        self.last_response_source = "mock"
        weak_points_raw = profile.get("weak_points", [])
        weak_points = [str(item).strip() for item in weak_points_raw if str(item).strip()] if isinstance(weak_points_raw, list) else []
        first_weak = weak_points[0] if weak_points else normalized_topic
        study_schedule = str(profile.get("study_schedule", "")).strip()
        exam_goal = str(profile.get("exam_goal", "")).strip()
        goal_prefix = f"冲刺{exam_goal}，" if exam_goal else ""
        schedule_hint = "按你的节奏推进" if not study_schedule else f"结合你「{study_schedule}」的节奏推进"
        return {
            "goal": f"{goal_prefix}今天把「{normalized_topic}」做成可复述可做题",
            "tasks": [
                f"先用8分钟速记「{normalized_topic}」核心框架",
                f"再用12分钟定向突破「{first_weak}」",
                f"最后做1道同类题并口头复盘错因",
            ],
            "duration_minutes": 30,
            "checkin_question": f"{schedule_hint}后，你现在最怕丢分的是哪一步？",
        }

    def generate_review_template(
        self,
        focus_topic: str,
        source_question: str,
        user_profile: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        normalized_topic = self._normalize_focus_topic(focus_topic=focus_topic, recent_messages=[])
        question = str(source_question).strip()
        profile = user_profile or {}
        if self._remote_enabled():
            remote = self._remote_review_template(
                focus_topic=normalized_topic,
                source_question=question,
                user_profile=profile,
            )
            if remote:
                self.last_response_source = "remote"
                return remote
        self.last_response_source = "mock"
        style = str(profile.get("response_style", "")).strip()
        lower = question.lower()
        if "时间" in question or "来不及" in question:
            mistake_type = "时间分配"
            reason = "前两步停留太久，后面关键步骤被压缩"
            fix_action = "限定每步用时，先拿基础分再攻难点"
            next_drill = f"用同主题「{normalized_topic}」做1题限时演练，记录每步耗时"
        elif "审题" in question or "题干" in question:
            mistake_type = "审题失误"
            reason = "没有先圈定题眼，导致解题方向偏移"
            fix_action = "先划题眼再作答，先说考点再动笔"
            next_drill = f"选3道「{normalized_topic}」题，只做题眼定位训练"
        elif "混淆" in question or "记不住" in question or "人物" in question or "口诀" in question:
            mistake_type = "记忆混淆"
            reason = "相近概念未建立对比锚点，回忆时互相干扰"
            fix_action = "做一张对比卡：概念定义+关键词+反例"
            next_drill = f"围绕「{normalized_topic}」做一次30秒快答，连续3轮"
        elif "不会" in question or "不懂" in question or "why" in lower:
            mistake_type = "概念不清"
            reason = "关键定义未吃透，导致后续推理断层"
            fix_action = "先复述定义，再用一个例子验证是否真正理解"
            next_drill = f"把「{normalized_topic}」核心定义讲给自己听并录音回放"
        else:
            mistake_type = "概念不清"
            reason = "题目映射到知识点的链路不稳定"
            fix_action = "按“题干关键词→知识点→步骤”三段法重做"
            next_drill = f"再做1道同主题「{normalized_topic}」题并写3句复盘"
        if style:
            fix_action = f"{fix_action}，按你偏好的「{style}」方式输出。"
        return {
            "mistake_type": mistake_type,
            "reason": reason,
            "fix_action": fix_action,
            "next_drill": next_drill,
        }

    def generate_weekly_report(
        self,
        focus_topic: str,
        weekly_stats: dict[str, Any],
        user_profile: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        normalized_topic = self._normalize_focus_topic(focus_topic=focus_topic, recent_messages=[])
        profile = user_profile or {}
        if self._remote_enabled():
            remote = self._remote_weekly_report(
                focus_topic=normalized_topic,
                weekly_stats=weekly_stats,
                user_profile=profile,
            )
            if remote:
                self.last_response_source = "remote"
                return remote
        self.last_response_source = "mock"
        plan_days = int(weekly_stats.get("plan_days", 0) or 0)
        total_minutes = int(weekly_stats.get("total_minutes", 0) or 0)
        review_count = int(weekly_stats.get("review_count", 0) or 0)
        task_completion_rate = float(weekly_stats.get("task_completion_rate", 0.0) or 0.0)
        repeat_rate = float(weekly_stats.get("repeat_mistake_rate", 0.0) or 0.0)
        repeat_rate_change = float(weekly_stats.get("repeat_mistake_rate_change", 0.0) or 0.0)
        repeat_drop_ratio = float(weekly_stats.get("repeat_mistake_drop_ratio", 0.0) or 0.0)
        has_repeat_baseline = bool(weekly_stats.get("has_repeat_baseline", False))
        is_task_target_met = bool(weekly_stats.get("is_task_completion_target_met", False))
        is_repeat_target_met = bool(weekly_stats.get("is_repeat_mistake_target_met", False))
        is_weekly_goal_met = bool(weekly_stats.get("is_weekly_goal_met", False))
        nudge_reengagement_rate = float(weekly_stats.get("nudge_reengagement_rate_7d", 0.0) or 0.0)
        top_topics_raw = weekly_stats.get("top_topics", [])
        top_topics = [str(item).strip() for item in top_topics_raw if str(item).strip()] if isinstance(top_topics_raw, list) else []
        mistake_distribution = weekly_stats.get("mistake_distribution", {})
        top_mistake = "概念不清"
        if isinstance(mistake_distribution, dict) and mistake_distribution:
            top_mistake = max(
                (
                    (str(key).strip(), int(value or 0))
                    for key, value in mistake_distribution.items()
                    if str(key).strip()
                ),
                key=lambda item: item[1],
            )[0]
        exam_goal = str(profile.get("exam_goal", "")).strip()
        goal_hint = f"朝着{exam_goal}推进" if exam_goal else "整体节奏在推进"
        topic_hint = top_topics[0] if top_topics else normalized_topic
        completion_text = f"{round(task_completion_rate * 100, 1)}%"
        repeat_text = f"{round(repeat_rate * 100, 1)}%"
        repeat_trend_text = "下降" if repeat_rate_change < 0 else "上升"
        repeat_change_text = f"{round(abs(repeat_rate_change) * 100, 1)}%"
        repeat_drop_text = f"{round(repeat_drop_ratio * 100, 1)}%"
        nudge_reengagement_text = f"{round(nudge_reengagement_rate * 100, 1)}%"
        task_signal = "✅" if is_task_target_met else "❌"
        repeat_signal = "✅" if is_repeat_target_met else "❌"
        overall_signal = "✅达标" if is_weekly_goal_met else "⚠️未达标"
        repeat_target_text = "环比下降至少20%"
        repeat_status_text = (
            f"复错率相对上周下降{repeat_drop_text}（目标{repeat_target_text}）"
            if has_repeat_baseline
            else "复错率目标暂无法判断（缺少上周基线）"
        )
        highlights = [
            f"本周完成{plan_days}天学习计划，累计{total_minutes}分钟，任务完成率{completion_text} {task_signal}",
            f"围绕「{topic_hint}」完成{review_count}次题后复盘",
            f"重复犯错率{repeat_text}，较上周{repeat_trend_text}{repeat_change_text}，{repeat_status_text} {repeat_signal}",
        ]
        next_week_focus = [
            f"每天先用10分钟复述「{topic_hint}」核心框架",
            f"针对「{top_mistake}」做2次定向限时训练",
            "每次做题后写3句复盘，确保能落地改错",
        ]
        return {
            "summary": f"{goal_hint}，当前重点考点是「{top_mistake}」。本周核心目标判定：{overall_signal}，轻推后回归率{nudge_reengagement_text}。",
            "highlights": highlights,
            "next_week_focus": next_week_focus,
            "coach_message": "你不是学不会，而是训练回路还不够短。下周我们按“做题-复盘-再做”快速迭代。",
        }

    def score_answer(
        self,
        question: str,
        answer: str,
        reference_points: list[str],
        expected_style: str,
        user_profile: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        question_text = str(question).strip()
        answer_text = str(answer).strip()
        refs = [str(item).strip() for item in reference_points if str(item).strip()]
        style = str(expected_style).strip()
        profile = user_profile or {}
        answer_len = len(answer_text)
        hit_count = 0
        for ref in refs:
            tokens = [token for token in re.split(r"[，。；、\s]+", ref) if token]
            if not tokens:
                continue
            if any(token in answer_text for token in tokens[:3]):
                hit_count += 1
        correctness = 0.0 if not refs else min(1.0, hit_count / len(refs))
        action_signals = ["先", "再", "最后", "步骤", "例如", "复盘", "练习", "限时", "提醒"]
        action_hit = sum(1 for token in action_signals if token in answer_text)
        actionability = min(1.0, action_hit / 4)
        style_tokens = [token for token in re.split(r"[后先与、\s]+", style) if token]
        style_hit = sum(1 for token in style_tokens if token and token in answer_text)
        style_consistency = min(1.0, style_hit / max(1, len(style_tokens)))
        memory_signals: list[str] = []
        exam_goal = str(profile.get("exam_goal", "")).strip()
        if exam_goal:
            memory_signals.append(exam_goal)
        weak_points_raw = profile.get("weak_points", [])
        if isinstance(weak_points_raw, list):
            for item in weak_points_raw[:3]:
                normalized = str(item).strip()
                if normalized:
                    memory_signals.append(normalized)
        memory_hit = sum(1 for token in memory_signals if token in answer_text)
        memory_utilization = 0.0 if not memory_signals else min(1.0, memory_hit / len(memory_signals))
        brevity = 1.0 if 40 <= answer_len <= 350 else 0.6 if 20 <= answer_len <= 450 else 0.3
        total_score = round(
            correctness * 0.4
            + actionability * 0.25
            + style_consistency * 0.2
            + memory_utilization * 0.1
            + brevity * 0.05,
            4,
        )
        return {
            "question": question_text,
            "correctness": round(correctness, 4),
            "actionability": round(actionability, 4),
            "style_consistency": round(style_consistency, 4),
            "memory_utilization": round(memory_utilization, 4),
            "brevity": round(brevity, 4),
            "total_score": total_score,
        }

    def status(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model_name,
            "remote_ready": self._remote_enabled(),
            "needs_api_key": self.provider != "mock" and not bool(self.api_key),
            "verify_ssl": self.verify_ssl,
            "last_error": self.last_error,
            "last_response_source": self.last_response_source,
        }

    def debug_state(self) -> str:
        return json.dumps(self.status(), ensure_ascii=False)

    def persona_config_status(self) -> dict[str, Any]:
        return self.persona_config_service.status()

    def update_persona_config(self, patch: dict[str, Any]) -> dict[str, Any]:
        return self.persona_config_service.update_config(patch)

    def _remote_enabled(self) -> bool:
        return self.provider in {"openai", "openai_compatible"} and bool(self.api_key)

    def _remote_chat_reply(
        self,
        recent_messages: list[dict[str, Any]],
        focus_topic: str,
        web_context: list[dict[str, str]],
        kb_context: list[dict[str, str]],
        semantic_context: list[dict[str, str]],
        user_profile: dict[str, Any],
    ) -> str:
        messages = self._build_remote_chat_messages(
            recent_messages=recent_messages,
            focus_topic=focus_topic,
            web_context=web_context,
            kb_context=kb_context,
            semantic_context=semantic_context,
            user_profile=user_profile,
        )
        content = self._post_chat_completion(messages=messages, temperature=0.7, max_tokens=self.chat_max_tokens)
        return content or ""

    def _build_remote_chat_messages(
        self,
        recent_messages: list[dict[str, Any]],
        focus_topic: str,
        web_context: list[dict[str, str]],
        kb_context: list[dict[str, str]],
        semantic_context: list[dict[str, str]],
        user_profile: dict[str, Any],
    ) -> list[dict[str, str]]:
        search_context = ""
        if web_context:
            serialized = []
            for index, source in enumerate(web_context[:3], start=1):
                title = source.get("title", "资料")
                url = source.get("url", "")
                snippet = source.get("snippet", "")
                serialized.append(f"[{index}] {title} {url} {snippet}")
            search_context = " 可用联网信息：" + " | ".join(serialized)
        kb_serialized = ""
        if kb_context:
            items = []
            for index, source in enumerate(kb_context[:3], start=1):
                title = source.get("title", "教编知识")
                page = source.get("page", "")
                snippet = source.get("snippet", "")
                page_hint = f"(第{page}页)" if page else ""
                items.append(f"[{index}] {title}{page_hint} {snippet}")
            kb_serialized = " 可用内置教编知识库：" + " | ".join(items)
        semantic_serialized = ""
        if semantic_context:
            items = []
            for index, source in enumerate(semantic_context[:2], start=1):
                title = source.get("title", "历史记忆")
                snippet = source.get("snippet", "")
                source_type = source.get("source_type", "")
                source_hint = f"({source_type})" if source_type else ""
                items.append(f"[{index}] {title}{source_hint} {snippet}")
            semantic_serialized = " 可用历史语义记忆：" + " | ".join(items)
        profile_context = self._serialize_user_profile(user_profile=user_profile)
        system_prompt = self.persona_config_service.build_chat_system_prompt(
            focus_topic=focus_topic,
            profile_context=profile_context,
            kb_context=kb_serialized,
            semantic_context=semantic_serialized,
            search_context=search_context,
        )
        messages = [{"role": "system", "content": system_prompt}]
        for item in recent_messages[-10:]:
            role = "assistant" if item["role"] == "ai" else ("user" if item["role"] == "user" else "system")
            messages.append({"role": role, "content": item["content"]})
        return messages

    def _remote_vision_reply(
        self,
        question: str,
        image_url: str,
        web_context: list[dict[str, str]],
        kb_context: list[dict[str, str]],
        user_profile: dict[str, Any],
    ) -> str:
        sources_text = ""
        if web_context:
            chunks = [f"{item.get('title', '资料')}: {item.get('snippet', '')}" for item in web_context[:2]]
            sources_text = " 可参考联网信息：" + "；".join(chunks)
        kb_text = ""
        if kb_context:
            chunks = [f"{item.get('title', '教编知识')}: {item.get('snippet', '')}" for item in kb_context[:2]]
            kb_text = " 可参考内置教编知识库：" + "；".join(chunks)
        profile_text = self._serialize_user_profile(user_profile=user_profile)
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": self.persona_config_service.build_vision_system_prompt(
                    profile_text=profile_text,
                    kb_text=kb_text,
                    sources_text=sources_text,
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ]
        content = self._post_chat_completion(messages=messages, temperature=0.4, max_tokens=300)
        return content or ""

    def _remote_summarize(self, content: str) -> Optional[dict[str, Any]]:
        prompt = (
            "把学习文本总结为 JSON，格式严格如下："
            '{"topic":"字符串","concepts":["字符串1","字符串2","字符串3"],"confusion_risk":"High/Medium/Low"}。'
            "只输出 JSON，不要输出其他内容。"
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content[:5000]},
        ]
        raw = self._post_chat_completion(messages=messages, temperature=0.2, max_tokens=260)
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            topic = str(parsed.get("topic", "")).strip() or "未命名主题"
            concepts_raw = parsed.get("concepts", [])
            concepts = [str(x).strip() for x in concepts_raw if str(x).strip()][:3]
            while len(concepts) < 3:
                concepts.append(f"{topic} - 关键点{len(concepts)+1}")
            risk = str(parsed.get("confusion_risk", "Medium"))
            if risk not in {"High", "Medium", "Low"}:
                risk = "Medium"
            return {"topic": topic, "concepts": concepts, "confusion_risk": risk}
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def _remote_hook(self, focus_topic: str, user_profile: dict[str, Any], nudge_level: str) -> str:
        profile_context = self._serialize_user_profile(user_profile=user_profile)
        prompt = (
            "写一条教编学习轻推通知。要求：15词以内，友好、有好奇心、带一点备考紧迫感，不要出现“提醒你学习”。"
            f"学习主题：{focus_topic}。轻推强度：{nudge_level}。{profile_context}"
        )
        messages = [{"role": "user", "content": prompt}]
        content = self._post_chat_completion(messages=messages, temperature=0.9, max_tokens=64)
        return content or ""

    def _remote_daily_plan(self, focus_topic: str, user_profile: dict[str, Any]) -> Optional[dict[str, Any]]:
        prompt = (
            "输出学习计划JSON，字段必须是goal,tasks,duration_minutes,checkin_question。"
            "其中tasks必须是3条字符串，duration_minutes是整数。"
            f"学习主题：{focus_topic}。{self._serialize_user_profile(user_profile=user_profile)}"
        )
        messages = [{"role": "user", "content": prompt}]
        raw = self._post_chat_completion(messages=messages, temperature=0.5, max_tokens=220)
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            goal = str(parsed.get("goal", "")).strip()
            tasks_raw = parsed.get("tasks", [])
            tasks = [str(item).strip() for item in tasks_raw if str(item).strip()][:3] if isinstance(tasks_raw, list) else []
            duration_minutes = int(parsed.get("duration_minutes", 0) or 0)
            checkin_question = str(parsed.get("checkin_question", "")).strip()
            if goal and len(tasks) == 3 and duration_minutes > 0 and checkin_question:
                return {
                    "goal": goal[:120],
                    "tasks": tasks,
                    "duration_minutes": duration_minutes,
                    "checkin_question": checkin_question[:160],
                }
            return None
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def _remote_review_template(
        self,
        focus_topic: str,
        source_question: str,
        user_profile: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        prompt = (
            "输出错题复盘JSON，字段必须是mistake_type,reason,fix_action,next_drill。"
            "mistake_type只能是：概念不清、审题失误、记忆混淆、时间分配之一。"
            f"学习主题：{focus_topic}。题目场景：{source_question[:300]}。{self._serialize_user_profile(user_profile=user_profile)}"
        )
        messages = [{"role": "user", "content": prompt}]
        raw = self._post_chat_completion(messages=messages, temperature=0.5, max_tokens=240)
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            mistake_type = str(parsed.get("mistake_type", "")).strip()
            reason = str(parsed.get("reason", "")).strip()
            fix_action = str(parsed.get("fix_action", "")).strip()
            next_drill = str(parsed.get("next_drill", "")).strip()
            allowed = {"概念不清", "审题失误", "记忆混淆", "时间分配"}
            if mistake_type in allowed and reason and fix_action and next_drill:
                return {
                    "mistake_type": mistake_type,
                    "reason": reason[:220],
                    "fix_action": fix_action[:220],
                    "next_drill": next_drill[:220],
                }
            return None
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def _remote_weekly_report(
        self,
        focus_topic: str,
        weekly_stats: dict[str, Any],
        user_profile: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        prompt = (
            "输出学习周报JSON，字段必须是summary,highlights,next_week_focus,coach_message。"
            "highlights和next_week_focus都必须是3条字符串数组。"
            f"学习主题：{focus_topic}。本周统计：{json.dumps(weekly_stats, ensure_ascii=False)}。"
            f"{self._serialize_user_profile(user_profile=user_profile)}"
        )
        messages = [{"role": "user", "content": prompt}]
        raw = self._post_chat_completion(messages=messages, temperature=0.5, max_tokens=300)
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            summary = str(parsed.get("summary", "")).strip()
            coach_message = str(parsed.get("coach_message", "")).strip()
            highlights_raw = parsed.get("highlights", [])
            next_focus_raw = parsed.get("next_week_focus", [])
            highlights = [str(item).strip() for item in highlights_raw if str(item).strip()][:3] if isinstance(highlights_raw, list) else []
            next_week_focus = [str(item).strip() for item in next_focus_raw if str(item).strip()][:3] if isinstance(next_focus_raw, list) else []
            if summary and coach_message and len(highlights) == 3 and len(next_week_focus) == 3:
                return {
                    "summary": summary[:240],
                    "highlights": highlights,
                    "next_week_focus": next_week_focus,
                    "coach_message": coach_message[:220],
                }
            return None
        except (json.JSONDecodeError, TypeError, ValueError):
            return None

    def _post_chat_completion(self, messages: list[dict[str, Any]], temperature: float, max_tokens: int) -> str:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        context = None
        if not self.verify_ssl:
            context = ssl._create_unverified_context()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds, context=context) as response:
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw)
                choices = parsed.get("choices", [])
                if not choices:
                    self.last_error = "LLM 响应缺少 choices"
                    return ""
                message = choices[0].get("message", {})
                content = str(message.get("content", "")).strip()
                self.last_error = ""
                return content
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="ignore")
            self.last_error = f"HTTP {error.code}: {body[:200]}"
            return ""
        except urllib.error.URLError as error:
            self.last_error = f"URL 错误: {str(error.reason)[:200]}"
            return ""
        except TimeoutError:
            self.last_error = "请求超时"
            return ""
        except json.JSONDecodeError:
            self.last_error = "LLM 返回非 JSON"
            return ""
        except Exception as error:
            self.last_error = f"未知错误: {str(error)[:200]}"
            return ""

    def _post_chat_completion_stream(
        self, messages: list[dict[str, Any]], temperature: float, max_tokens: int
    ) -> Optional[Iterator[str]]:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        context = None
        if not self.verify_ssl:
            context = ssl._create_unverified_context()
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout_seconds, context=context)
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="ignore")
            self.last_error = f"HTTP {error.code}: {body[:200]}"
            return None
        except urllib.error.URLError as error:
            self.last_error = f"URL 错误: {str(error.reason)[:200]}"
            return None
        except TimeoutError:
            self.last_error = "请求超时"
            return None
        except Exception as error:
            self.last_error = f"未知错误: {str(error)[:200]}"
            return None

        def iterator() -> Iterator[str]:
            def extract_text_chunks(parsed: dict[str, Any]) -> list[str]:
                chunks: list[str] = []
                choices = parsed.get("choices", [])
                if isinstance(choices, list) and choices:
                    first = choices[0]
                    if isinstance(first, dict):
                        delta = first.get("delta", {})
                        if isinstance(delta, dict):
                            delta_content = delta.get("content", "")
                            if isinstance(delta_content, str) and delta_content:
                                chunks.append(delta_content)
                        message = first.get("message", {})
                        if isinstance(message, dict):
                            message_content = message.get("content", "")
                            if isinstance(message_content, str) and message_content:
                                chunks.extend(list(self._chunk_text(message_content, 10)))
                output_text = parsed.get("output_text", "")
                if isinstance(output_text, str) and output_text:
                    chunks.extend(list(self._chunk_text(output_text, 10)))
                return chunks

            with response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    data = line
                    if line.startswith("data:"):
                        data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    chunks = extract_text_chunks(parsed)
                    for chunk in chunks:
                        yield chunk
            self.last_error = ""

        return iterator()

    def _chunk_text(self, text: str, chunk_size: int = 18) -> Iterator[str]:
        content = str(text or "")
        if not content:
            return iter(())
        def iterator() -> Iterator[str]:
            for index in range(0, len(content), chunk_size):
                yield content[index : index + chunk_size]
        return iterator()

    def _normalize_focus_topic(self, focus_topic: str, recent_messages: list[dict[str, Any]]) -> str:
        topic = str(focus_topic or "").strip()
        if topic and topic != "未设置学习主题":
            return topic
        latest_user_text = ""
        for message in reversed(recent_messages):
            if message.get("role") == "user":
                latest_user_text = str(message.get("content", "")).strip()
                break
        if latest_user_text:
            candidate = latest_user_text.replace("\n", " ").strip()
            return candidate[:20] + ("..." if len(candidate) > 20 else "")
        return "当前学习内容"

    def _should_search_web(self, question: str) -> bool:
        if os.getenv("MINDSHADOW_ENABLE_WEB_SEARCH", "true").strip().lower() == "false":
            return False
        keywords = ["最新", "新闻", "来源", "证据", "论文", "为什么", "怎么证明", "对比", "数据", "统计"]
        return any(keyword in question for keyword in keywords) or len(question) >= 18

    def _serialize_user_profile(self, user_profile: dict[str, Any]) -> str:
        if not user_profile:
            return ""
        pieces: list[str] = []
        exam_goal = str(user_profile.get("exam_goal", "")).strip()
        response_style = str(user_profile.get("response_style", "")).strip()
        study_schedule = str(user_profile.get("study_schedule", "")).strip()
        motivation_note = str(user_profile.get("motivation_note", "")).strip()
        exam_date = str(user_profile.get("exam_date", "")).strip()
        weak_points_raw = user_profile.get("weak_points", [])
        weak_points: list[str] = []
        if isinstance(weak_points_raw, list):
            weak_points = [str(item).strip() for item in weak_points_raw if str(item).strip()][:4]
        if exam_date:
            pieces.append(f"考试日期:{exam_date}")
        if exam_goal:
            pieces.append(f"目标:{exam_goal}")
        if study_schedule:
            pieces.append(f"学习节奏:{study_schedule}")
        if response_style:
            pieces.append(f"讲解偏好:{response_style}")
        if weak_points:
            pieces.append(f"薄弱点:{'、'.join(weak_points)}")
        if motivation_note:
            pieces.append(f"激励语:{motivation_note}")
        if not pieces:
            return ""
        return " 用户长期画像：" + "；".join(pieces) + "。"
