import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


STOPWORDS = {
    "我们",
    "你们",
    "他们",
    "以及",
    "因为",
    "所以",
    "可以",
    "这个",
    "那个",
    "一个",
    "进行",
    "就是",
    "如果",
    "需要",
    "通过",
    "其中",
    "学习",
    "教育",
    "教师",
    "考试",
    "知识",
    "内容",
    "重点",
    "方法",
}


@dataclass
class Chunk:
    source: str
    title: str
    page: str
    content: str
    keywords: list[str]


def clean_text(text: str) -> str:
    compact = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", text)
    compact = re.sub(r"[ \t]+", " ", compact)
    compact = compact.replace("·", " ")
    compact = compact.replace("•", " ")
    lines = [line.strip() for line in compact.splitlines()]
    cleaned_lines: list[str] = []
    for line in lines:
        if not line:
            continue
        if re.fullmatch(r"\d{1,4}", line):
            continue
        if re.search(r"[.。·•]{6,}", line):
            continue
        if len(line) <= 2:
            continue
        cleaned_lines.append(line)
    merged = "\n".join(cleaned_lines)
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    return merged.strip()


def split_chunks(text: str, max_chars: int = 380, overlap: int = 80) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    chunks: list[str] = []
    buffer = ""
    for para in paragraphs:
        if len(buffer) + len(para) + 1 <= max_chars:
            buffer = f"{buffer}\n{para}".strip()
            continue
        if buffer:
            chunks.append(buffer)
        if len(para) <= max_chars:
            buffer = para
            continue
        start = 0
        while start < len(para):
            piece = para[start : start + max_chars]
            if piece.strip():
                chunks.append(piece.strip())
            if start + max_chars >= len(para):
                break
            start += max(1, max_chars - overlap)
        buffer = ""
    if buffer:
        chunks.append(buffer)
    return chunks


def extract_keywords(text: str, top_n: int = 8) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9]{2,}|[\u4e00-\u9fff]{2,4}", text.lower())
    freq = Counter(
        token
        for token in tokens
        if token not in STOPWORDS and not token.isdigit() and len(token.strip()) >= 2
    )
    return [item for item, _ in freq.most_common(top_n)]


def build_kb(input_dir: Path) -> dict:
    pdf_files = sorted(input_dir.glob("*.pdf"))
    documents: list[dict] = []
    for pdf_file in pdf_files:
        reader = PdfReader(str(pdf_file))
        title = pdf_file.stem.strip()
        for index, page in enumerate(reader.pages, start=1):
            raw = page.extract_text() or ""
            text = clean_text(raw)
            if len(text) < 40:
                continue
            if _looks_like_toc(text):
                continue
            page_chunks = split_chunks(text=text, max_chars=380, overlap=80)
            for chunk in page_chunks:
                keywords = extract_keywords(chunk, top_n=8)
                item = Chunk(
                    source=pdf_file.name,
                    title=title,
                    page=str(index),
                    content=chunk,
                    keywords=keywords,
                )
                documents.append(item.__dict__)
    return {
        "metadata": {
            "topic": "教编考试学习搭子内置知识库",
            "version": "v1",
            "document_count": len(documents),
        },
        "documents": documents,
    }


def _looks_like_toc(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True
    normalized_lines = [re.sub(r"\s+", "", line) for line in lines]
    chapter_hits = sum(1 for line in normalized_lines if ("第" in line and "章" in line) or ("第" in line and "节" in line))
    toc_pattern_hits = sum(1 for line in normalized_lines if re.search(r"第[一二三四五六七八九十百0-9]+[章节篇节].*\d{1,3}$", line))
    short_lines = sum(1 for line in normalized_lines if len(line) <= 18)
    return toc_pattern_hits >= 5 or (chapter_hits >= 6 and short_lines >= len(lines) * 0.45)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build teaching exam knowledge base from PDF files.")
    parser.add_argument("--input-dir", required=True, help="PDF directory path")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_kb(input_dir=input_dir)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Knowledge base built: {output_path}")
    print(f"Chunks: {payload['metadata']['document_count']}")


if __name__ == "__main__":
    main()
