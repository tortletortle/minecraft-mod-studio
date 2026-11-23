"""Deterministic, explainable retrieval for live Minecraft command catalogs.

This module ranks candidates; it does not infer command safety or execute commands.
Scores are relative ranking signals, not calibrated probabilities.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any


_TOKEN_RE = re.compile(r"[a-z0-9_.:-]+|[\u4e00-\u9fff]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")
_ENGLISH_STOP_WORDS = {
    "a", "an", "the", "to", "for", "with", "and", "or", "please",
    "can", "you", "all", "of", "in", "on", "at", "it", "is", "are",
    "be", "this", "that", "my", "me",
}
_CHINESE_STOP_PHRASES = (
    "请帮我", "帮我", "请", "一下", "所有", "全部", "这个", "那个", "把", "将", "的",
)
_FIELD_WEIGHTS = {
    "name": 3.0,
    "manifest_keywords": 2.5,
    "manifest_description": 1.8,
    "curated_hints": 1.2,
}
_BM25_K1 = 1.2
_BM25_B = 0.75
_MANIFEST_TRUST = "untrusted_mod_supplied_metadata"


def _tokenize(value: Any) -> list[str]:
    if not isinstance(value, str):
        return []
    text = value.casefold()
    for phrase in _CHINESE_STOP_PHRASES:
        text = text.replace(phrase, " ")

    tokens: list[str] = []
    for part in _TOKEN_RE.findall(text):
        if _CJK_RE.fullmatch(part):
            # Keep the full phrase for exact retrieval and overlapping bigrams
            # for partial Chinese matches without an external tokenizer.
            tokens.append(part)
            if len(part) > 1:
                tokens.extend(part[index:index + 2] for index in range(len(part) - 1))
        elif part and part not in _ENGLISH_STOP_WORDS:
            tokens.append(part)
    return tokens


def rank_command_candidates(
    query: str,
    commands: list[dict[str, Any]],
    curated_hints: dict[str, str],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Rank live command roots with field-weighted BM25 and exact-phrase boosts.

    Only manifest summaries carrying the explicit untrusted-data label are used
    as retrieval text. That label does not make the metadata trusted.
    """
    if not isinstance(query, str) or not query.strip():
        return []
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("limit must be an integer between 1 and 20")

    folded_query = query.casefold().strip()
    query_terms = list(dict.fromkeys(_tokenize(folded_query)))
    if not query_terms:
        return []

    documents: list[tuple[dict[str, Any], dict[str, list[str]], dict[str, Any] | None]] = []
    for entry in commands:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            continue
        name = entry["name"]
        summary = entry.get("manifest_summary")
        accepted_summary = (
            summary
            if isinstance(summary, dict) and summary.get("trust") == _MANIFEST_TRUST
            else None
        )
        keywords = accepted_summary.get("keywords", []) if accepted_summary else []
        if not isinstance(keywords, list):
            keywords = []
        description = accepted_summary.get("description", "") if accepted_summary else ""
        if not isinstance(description, str):
            description = ""

        fields = {
            "name": _tokenize(name),
            "manifest_keywords": _tokenize(" ".join(
                value for value in keywords if isinstance(value, str)
            )),
            "manifest_description": _tokenize(description[:80]),
            "curated_hints": _tokenize(curated_hints.get(name.casefold(), "")),
        }
        documents.append((entry, fields, accepted_summary))

    if not documents:
        return []

    document_terms = [
        {term for field_tokens in fields.values() for term in field_tokens}
        for _, fields, _ in documents
    ]
    document_count = len(documents)
    document_frequency = Counter(
        term for terms in document_terms for term in terms
    )
    average_lengths: dict[str, float] = {}
    for field_name in _FIELD_WEIGHTS:
        lengths = [len(fields[field_name]) for _, fields, _ in documents]
        average_lengths[field_name] = sum(lengths) / document_count

    query_set = set(query_terms)
    ranked: list[dict[str, Any]] = []

    for (entry, fields, accepted_summary), _all_terms in zip(documents, document_terms):
        score = 0.0
        matched_terms: set[str] = set()
        matched_fields: set[str] = set()

        for field_name, field_weight in _FIELD_WEIGHTS.items():
            field_tokens = fields[field_name]
            if not field_tokens:
                continue
            frequencies = Counter(field_tokens)
            average_length = average_lengths[field_name] or 1.0
            length_norm = (
                1.0 - _BM25_B
                + _BM25_B * len(field_tokens) / average_length
            )
            for term in query_set:
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                inverse_document_frequency = math.log(
                    1.0
                    + (document_count - document_frequency[term] + 0.5)
                    / (document_frequency[term] + 0.5)
                )
                denominator = frequency + _BM25_K1 * length_norm
                score += (
                    field_weight
                    * inverse_document_frequency
                    * frequency
                    * (_BM25_K1 + 1.0)
                    / denominator
                )
                matched_terms.add(term)
                matched_fields.add(field_name)

        name_text = entry["name"].casefold()
        manifest_keyword_text = " ".join(
            value for value in (accepted_summary or {}).get("keywords", [])
            if isinstance(value, str)
        ).casefold()
        manifest_description_text = str(
            (accepted_summary or {}).get("description", "")
        ).casefold()
        curated_text = curated_hints.get(entry["name"].casefold(), "").casefold()

        phrase_sources: list[str] = []
        for source_name, source_text in (
            ("command_name", name_text),
            ("mod_manifest_keyword", manifest_keyword_text),
            ("mod_manifest_description", manifest_description_text),
            ("curated_keyword_hint", curated_text),
        ):
            if folded_query in source_text:
                phrase_sources.append(source_name)

        phrase_weights = {
            "command_name": 8.0,
            "mod_manifest_keyword": 5.0,
            "mod_manifest_description": 3.5,
            "curated_keyword_hint": 2.5,
        }
        score += sum(phrase_weights[source] for source in phrase_sources)

        if score <= 0:
            continue

        basis_order = (
            ("name", "command_name"),
            ("manifest_keywords", "mod_manifest_keyword"),
            ("manifest_description", "mod_manifest_description"),
            ("curated_hints", "curated_keyword_hint"),
        )
        match_basis = [
            label for field_name, label in basis_order
            if field_name in matched_fields
        ]
        if "mod_manifest_keyword" in phrase_sources and "mod_manifest_exact_phrase" not in match_basis:
            match_basis.append("mod_manifest_exact_phrase")
        if "mod_manifest_description" in phrase_sources and "mod_manifest_description_exact_phrase" not in match_basis:
            match_basis.append("mod_manifest_description_exact_phrase")
        if "command_name" in phrase_sources and "command_name_exact_phrase" not in match_basis:
            match_basis.append("command_name_exact_phrase")
        if "curated_keyword_hint" in phrase_sources and "curated_hint_exact_phrase" not in match_basis:
            match_basis.append("curated_hint_exact_phrase")

        ranked.append({
            "name": entry["name"],
            "score": round(score, 4),
            "coverage": round(len(matched_terms) / len(query_set), 4),
            "matched_terms": sorted(matched_terms),
            "match_basis": match_basis,
            "executable_at_root": entry.get("executable_at_root") is True,
            "child_count": entry.get("child_count", 0),
            "redirect": entry.get("redirect") is True,
            "manifest_summary": accepted_summary,
            "manifest_trust": (
                _MANIFEST_TRUST if accepted_summary is not None else "no_manifest"
            ),
        })

    ranked.sort(key=lambda item: (-item["score"], item["name"]))
    return ranked[:limit]
