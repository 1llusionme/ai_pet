import json
import os
from pathlib import Path
from typing import Any


class PersonaConfigService:
    def __init__(self) -> None:
        default_path = Path(__file__).resolve().parent.parent / "config" / "persona.json"
        self.config_path = Path(os.getenv("MINDSHADOW_PERSONA_CONFIG_PATH", str(default_path))).resolve()
        self.default_config: dict[str, Any] = {
            "assistant_name": "教编考试学习搭子",
            "mission": "帮助用户提分上岸",
            "tone": "口语化、直接、可执行",
            "response_sections": ["结论", "为什么", "怎么做"],
            "list_limit": 3,
            "markdown_features": ["### 标题", "- 列表", "**重点**", "> 引用", "==重点词=="],
            "table_policy": "需要做对比或矩阵时优先使用 Markdown 表格",
            "uncertainty_policy": "只能引用当前上下文里可验证的信息；证据不足或记忆不确定时要明确说“不确定”并给通用思路",
            "vision_mode": "先判断考点，再给解题步骤；看不清图片时明确请求补充",
        }

    def status(self) -> dict[str, Any]:
        payload = self.get_config()
        return {
            "path": str(self.config_path),
            "exists": self.config_path.exists(),
            "config": payload,
        }

    def get_config(self) -> dict[str, Any]:
        payload = dict(self.default_config)
        loaded = self._read_file()
        if isinstance(loaded, dict):
            payload.update(self._sanitize_patch(loaded))
        return payload

    def update_config(self, patch: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(patch, dict):
            raise ValueError("config must be an object")
        current = self.get_config()
        current.update(self._sanitize_patch(patch))
        self._write_file(current)
        return current

    def build_chat_system_prompt(
        self,
        focus_topic: str,
        profile_context: str,
        kb_context: str,
        semantic_context: str,
        search_context: str,
    ) -> str:
        config = self.get_config()
        sections = "、".join(config.get("response_sections", []))
        markdown_rules = "、".join(config.get("markdown_features", []))
        return (
            f"你是「{config.get('assistant_name')}」。目标是{config.get('mission')}。"
            "回答必须先遵守硬约束，再结合最近对话，再参考知识库和联网信息。"
            f"{config.get('uncertainty_policy')}，不要编造。"
            f"回答风格要求：{config.get('tone')}，使用轻量结构化文本。结构固定为：{sections}。"
            f"允许使用 Markdown 子集：{markdown_rules}。"
            f"{config.get('table_policy')}。列表最多{int(config.get('list_limit', 3))}条，避免冗长。"
            f" 当前学习主题：{focus_topic}。{profile_context}{kb_context}{semantic_context}{search_context}"
        )

    def build_vision_system_prompt(self, profile_text: str, kb_text: str, sources_text: str) -> str:
        config = self.get_config()
        sections = "、".join(config.get("response_sections", []))
        markdown_rules = "、".join(config.get("markdown_features", []))
        return (
            f"你是「{config.get('assistant_name')}」，擅长讲题。{config.get('vision_mode')}。"
            f"用口语化中文，按“{sections}”输出。"
            f"允许使用 Markdown 子集：{markdown_rules}。"
            f"{config.get('table_policy')}。"
            f"列表最多{int(config.get('list_limit', 3))}条。"
            + profile_text
            + kb_text
            + sources_text
        )

    def _read_file(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            raw = self.config_path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
        return {}

    def _write_file(self, payload: dict[str, Any]) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _sanitize_patch(self, patch: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        string_fields = [
            "assistant_name",
            "mission",
            "tone",
            "table_policy",
            "uncertainty_policy",
            "vision_mode",
        ]
        for field in string_fields:
            value = patch.get(field)
            if isinstance(value, str) and value.strip():
                sanitized[field] = value.strip()[:300]
        sections = patch.get("response_sections")
        if isinstance(sections, list):
            normalized_sections = [str(item).strip()[:24] for item in sections if str(item).strip()][:6]
            if normalized_sections:
                sanitized["response_sections"] = normalized_sections
        markdown_features = patch.get("markdown_features")
        if isinstance(markdown_features, list):
            normalized_md = [str(item).strip()[:40] for item in markdown_features if str(item).strip()][:8]
            if normalized_md:
                sanitized["markdown_features"] = normalized_md
        list_limit = patch.get("list_limit")
        if list_limit is not None:
            try:
                parsed = int(list_limit)
                sanitized["list_limit"] = min(max(parsed, 1), 6)
            except (TypeError, ValueError):
                pass
        return sanitized
