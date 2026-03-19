import json
import re
from pathlib import Path
from typing import Any


class KnowledgeBaseService:
    def __init__(self, kb_path: str) -> None:
        self.kb_path = Path(kb_path)
        self.documents: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.kb_path.exists():
            self.documents = []
            return
        raw = self.kb_path.read_text(encoding="utf-8")
        payload = json.loads(raw)
        docs = payload.get("documents", [])
        self.documents = [doc for doc in docs if isinstance(doc, dict) and doc.get("content")]

    def search(self, query: str, top_k: int = 3) -> list[dict[str, str]]:
        normalized_query = query.strip()
        if not normalized_query or not self.documents:
            return []
        query_tokens = self._tokenize(normalized_query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for doc in self.documents:
            content = str(doc.get("content", ""))
            source = str(doc.get("source", "内置知识库"))
            title = str(doc.get("title", source))
            page = str(doc.get("page", ""))
            content_tokens = self._tokenize(content)
            if not content_tokens:
                continue
            overlap = len(query_tokens.intersection(content_tokens))
            contains_bonus = 0.0
            if normalized_query in content:
                contains_bonus = 3.0
            keyword_bonus = self._keyword_bonus(query_tokens=query_tokens, doc=doc)
            score = overlap * 1.2 + contains_bonus + keyword_bonus
            if score <= 0:
                continue
            scored.append(
                (
                    score,
                    {
                        "title": title,
                        "source": source,
                        "page": page,
                        "snippet": content[:220],
                    },
                )
            )
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[: max(1, min(top_k, 5))]]

    def _keyword_bonus(self, query_tokens: set[str], doc: dict[str, Any]) -> float:
        raw_keywords = doc.get("keywords", [])
        if not isinstance(raw_keywords, list):
            return 0.0
        keywords = {str(item).strip() for item in raw_keywords if str(item).strip()}
        if not keywords:
            return 0.0
        return float(len(query_tokens.intersection(keywords))) * 1.5

    def _tokenize(self, text: str) -> set[str]:
        normalized = re.sub(r"\s+", " ", text.strip().lower())
        if not normalized:
            return set()
        words = set(re.findall(r"[a-z0-9]{2,}|[\u4e00-\u9fff]", normalized))
        if len(normalized) >= 2:
            for idx in range(len(normalized) - 1):
                bigram = normalized[idx : idx + 2].strip()
                if bigram and " " not in bigram:
                    words.add(bigram)
        return words
