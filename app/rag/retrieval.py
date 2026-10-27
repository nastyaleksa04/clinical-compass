"""Local citation-first retrieval for the normalized doctor knowledge base."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KB_PATH = PROJECT_ROOT / "data" / "knowledge" / "kb_v2_2_complete_doctor"
PATIENT_KB_PATH = PROJECT_ROOT / "data" / "knowledge" / "kb_v2_3_patient"
WORD_RE = re.compile(r"[a-zа-я0-9]+", re.IGNORECASE)
RU_SUFFIXES = tuple(sorted({
    "иями", "ями", "ами", "его", "ого", "ему", "ому", "ыми", "ими",
    "ий", "ый", "ой", "ая", "яя", "ое", "ее", "ые", "ие",
    "ов", "ев", "ам", "ям", "ах", "ях", "ом", "ем",
    "ами", "ями", "ить", "ать", "ять", "ение", "ения",
    "а", "я", "ы", "и", "у", "ю", "е", "о",
}, key=len, reverse=True))


def normalize_text(value: str) -> str:
    return value.casefold().replace("ё", "е")


def stem(token: str) -> str:
    if not re.search(r"[а-я]", token) or len(token) < 6:
        return token
    for suffix in RU_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[:-len(suffix)]
    return token


def tokenize(value: str) -> list[str]:
    return [stem(token) for token in WORD_RE.findall(normalize_text(value)) if len(token) > 1]


def char_ngrams(value: str, size: int = 3) -> set[str]:
    compact = " ".join(WORD_RE.findall(normalize_text(value)))
    return {compact[index:index + size] for index in range(max(0, len(compact) - size + 1))}


QUERY_ALIASES = {
    "авиандр": "маритупирдин маритупердин",
    "гтр": "генерализованное тревожное расстройство",
    "дэ": "депрессивный эпизод депрессия",
    "hars": "шкала гамильтона тревога",
    "hdrs": "шкала гамильтона депрессия",
    "madrs": "шкала монтгомери асберг депрессия",
    "phq-9": "phq9 депрессия",
    "gad-7": "gad7 тревога",
}


def expand_query(value: str) -> str:
    normalized = normalize_text(value)
    additions = [
        expansion for marker, expansion in QUERY_ALIASES.items()
        if marker in normalized
    ]
    return value + (" " + " ".join(additions) if additions else "")


def _domain_intent_boost(query: str, chunk: dict[str, Any]) -> float:
    query_text = normalize_text(query)
    source_id = normalize_text(chunk.get("source_id", ""))
    metadata = normalize_text(" ".join(chunk.get("entity_ids", [])))
    boost = 0.0
    gad_intent = any(term in query_text for term in ("гтр", "генерализованн", "gad-7", "gad7", "hars"))
    depression_intent = any(term in query_text for term in ("депресс", "дэ", "phq-9", "phq9", "hdrs", "madrs"))
    if gad_intent and ("gad" in source_id or "gad" in metadata):
        boost += 3.5
    if depression_intent and ("depression" in source_id or "depression" in metadata):
        boost += 3.5
    for marker in ("hars", "hdrs", "madrs", "phq9", "gad7"):
        if marker in query_text and marker in metadata:
            boost += 12.0
    if "авиандр" in query_text and any(term in (source_id + " " + metadata) for term in ("maritup", "маритуп")):
        boost += 10.0
    if "доз" in query_text and ("__m" in metadata or "card:" in metadata):
        boost += 6.0
    return boost


def _is_safety_chunk(chunk: dict[str, Any]) -> bool:
    return any(
        entity_id.startswith(("safety:", "alert:", "route:"))
        for entity_id in chunk.get("entity_ids", [])
    )


def _clinical_intent_boost(query: str, chunk: dict[str, Any]) -> float:
    """Promote short safety records when a case contains an explicit risk cue.

    This lexical reranker only uses words already present in the query and the
    indexed record. It does not execute a medical rule or infer a diagnosis.
    """
    if not _is_safety_chunk(chunk):
        return 0.0

    query_text = normalize_text(query)
    chunk_text = normalize_text(chunk.get("text", ""))
    boost = 0.0

    if "суицид" in query_text and "суицид" in chunk_text:
        boost += 5.0
        if any(term in query_text for term in ("план", "намерен")) and any(
            term in chunk_text for term in ("стационар", "госпитал")
        ):
            boost += 5.0

    if "гипоман" in query_text and (
        "гипоман" in chunk_text or "смешанн" in chunk_text
    ):
        boost += 14.0

    therapy_change = any(
        term in query_text
        for term in ("сразу начать", "добавлен", "добавить", "комбинац", "совместн")
    )
    if therapy_change:
        boost += 10.0

    return boost


class KnowledgeIndex:
    def __init__(self, root: str | Path = DEFAULT_KB_PATH, audience: str = "doctor"):
        self.root = Path(root)
        self.audience = audience
        self.manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        self.sources = {
            row["source_id"]: row
            for row in self._read_jsonl("sources.jsonl")
        }
        self.chunks = [
            row for row in self._read_jsonl("entities/chunks.jsonl")
            if row.get("retrieval_eligible") and audience in (row.get("audience") or [])
        ]
        self.term_counts: list[Counter[str]] = []
        self.doc_lengths: list[int] = []
        self.doc_ngrams: list[set[str]] = []
        document_frequency: Counter[str] = Counter()
        for chunk in self.chunks:
            searchable = " ".join([
                chunk.get("text", ""),
                chunk.get("source_id", ""),
                " ".join(chunk.get("entity_ids", [])),
                " ".join(chunk.get("section_path", [])),
            ])
            counts = Counter(tokenize(searchable))
            self.term_counts.append(counts)
            self.doc_lengths.append(sum(counts.values()))
            self.doc_ngrams.append(char_ngrams(searchable))
            document_frequency.update(counts.keys())
        count = max(len(self.chunks), 1)
        self.avg_length = sum(self.doc_lengths) / count
        self.idf = {
            term: math.log(1 + (count - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def _read_jsonl(self, relative: str) -> list[dict[str, Any]]:
        path = self.root / relative
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _score(self, query: str, index: int) -> float:
        query_terms = tokenize(query)
        if not query_terms:
            return 0.0
        counts = self.term_counts[index]
        length = self.doc_lengths[index]
        k1, b = 1.5, 0.75
        bm25 = 0.0
        for term in query_terms:
            frequency = counts.get(term, 0)
            if not frequency:
                continue
            denominator = frequency + k1 * (1 - b + b * length / max(self.avg_length, 1))
            bm25 += self.idf.get(term, 0.0) * frequency * (k1 + 1) / denominator

        query_ngrams = char_ngrams(query)
        overlap = len(query_ngrams & self.doc_ngrams[index]) / max(len(query_ngrams), 1)
        chunk = self.chunks[index]
        text = normalize_text(chunk.get("text", ""))
        exact_boost = 1.5 if len(query) >= 8 and normalize_text(query) in text else 0.0
        metadata = normalize_text(" ".join(chunk.get("entity_ids", [])))
        metadata_boost = 8.0 if any(len(term) >= 4 and term in metadata for term in set(query_terms)) else 0.0
        return (
            bm25
            + overlap * 3.0
            + exact_boost
            + metadata_boost
            + _clinical_intent_boost(query, chunk)
            + _domain_intent_boost(query, chunk)
        )

    def search(self, query: str, limit: int = 5) -> dict[str, Any]:
        query = query.strip()
        scoring_query = expand_query(query)
        ranked = sorted(
            ((self._score(scoring_query, index), index) for index in range(len(self.chunks))),
            reverse=True,
        )
        results = []
        for score, index in ranked:
            if score <= 0 or len(results) >= limit:
                break
            chunk = self.chunks[index]
            source = self.sources.get(chunk["source_id"], {})
            results.append({
                "rank": len(results) + 1,
                "score": round(score, 6),
                "chunk_id": chunk["chunk_id"],
                "entity_ids": chunk.get("entity_ids", []),
                "section_path": chunk.get("section_path", []),
                "text": chunk["text"],
                "evidence": chunk.get("evidence", {}),
                "source": {
                    "source_id": chunk["source_id"],
                    "title": source.get("title", chunk["source_id"]),
                    "organization": source.get("organization"),
                    "version": source.get("version"),
                    "url": source.get("url"),
                },
            })
        return {
            "query": query,
            "audience": self.audience,
            "index_release": self.manifest.get("release"),
            "total_chunks": len(self.chunks),
            "results": results,
            "disclaimer": (
                "Экспериментальный поиск по врачебному корпусу. Найденные фрагменты не являются назначением."
                if self.audience == "doctor"
                else "Справочная информация не устанавливает диагноз и не заменяет консультацию врача."
            ),
        }


@lru_cache(maxsize=1)
def doctor_index() -> KnowledgeIndex:
    return KnowledgeIndex(DEFAULT_KB_PATH, "doctor")


@lru_cache(maxsize=1)
def patient_index() -> KnowledgeIndex:
    return KnowledgeIndex(PATIENT_KB_PATH, "patient")
