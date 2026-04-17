"""Entity and relationship extraction using spaCy NLP.

Provides NER-based entity extraction, dependency-parse SVO relationship
extraction, and fuzzy entity deduplication via difflib.  Follows the
exact lazy-load + threading.Lock pattern from ``embedding.py``.
"""

from __future__ import annotations

import asyncio
import threading
from difflib import SequenceMatcher

import spacy
import spacy.language
import structlog

from docingest.config import settings
from docingest.models.graph import EntityType

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Lazy-loaded spaCy singleton (mirrors embedding.py _model / _model_lock)
# ---------------------------------------------------------------------------

_nlp: spacy.language.Language | None = None
_nlp_lock = threading.Lock()


def _get_nlp() -> spacy.language.Language:
    """Lazy-init the spaCy model. Thread-safe double-checked locking."""
    global _nlp
    if _nlp is None:
        with _nlp_lock:
            if _nlp is None:
                log.info("loading spacy model", model=settings.spacy_model)
                _nlp = spacy.load(settings.spacy_model)
                log.info("spacy model loaded", model=settings.spacy_model)
    return _nlp


# ---------------------------------------------------------------------------
# SpaCy NER label -> EntityType mapping
# ---------------------------------------------------------------------------

_SPACY_LABEL_MAP: dict[str, EntityType] = {
    # Direct mappings
    "PERSON": EntityType.PERSON,
    "ORG": EntityType.ORGANIZATION,
    "GPE": EntityType.LOCATION,
    "LOC": EntityType.LOCATION,
    "FAC": EntityType.LOCATION,
    "DATE": EntityType.DATE,
    "TIME": EntityType.DATE,
    "EVENT": EntityType.EVENT,
    "PRODUCT": EntityType.PRODUCT,
    # Abstract / categorical -> CONCEPT
    "NORP": EntityType.CONCEPT,
    "LAW": EntityType.CONCEPT,
    "LANGUAGE": EntityType.CONCEPT,
    "WORK_OF_ART": EntityType.CONCEPT,
    # Numeric types -> OTHER (low value for knowledge graph)
    "CARDINAL": EntityType.OTHER,
    "ORDINAL": EntityType.OTHER,
    "MONEY": EntityType.OTHER,
    "PERCENT": EntityType.OTHER,
    "QUANTITY": EntityType.OTHER,
}


def _map_spacy_label(label: str) -> EntityType:
    """Map a spaCy NER label to our EntityType enum."""
    return _SPACY_LABEL_MAP.get(label, EntityType.OTHER)


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


def extract_entities(text: str) -> list[dict]:
    """Extract named entities from text using spaCy NER.

    Returns list of dicts with keys: name, entity_type, start_char, end_char.
    Entities mapped to ``EntityType.OTHER`` are filtered out to reduce noise.
    Results are capped at ``settings.max_entities_per_chunk``.
    """
    nlp = _get_nlp()
    with _nlp_lock:
        doc = nlp(text)

    entities: list[dict] = []
    for ent in doc.ents:
        entity_type = _map_spacy_label(ent.label_)
        if entity_type == EntityType.OTHER:
            continue
        entities.append(
            {
                "name": ent.text.strip(),
                "entity_type": entity_type,
                "start_char": ent.start_char,
                "end_char": ent.end_char,
            }
        )

    return entities[: settings.max_entities_per_chunk]


# ---------------------------------------------------------------------------
# Relationship extraction (SVO from dependency parse)
# ---------------------------------------------------------------------------


def _get_span_text(token) -> str:  # noqa: ANN001
    """Expand a token to include its left compound/amod modifiers."""
    parts: list[str] = []
    for child in token.lefts:
        if child.dep_ in ("compound", "amod"):
            parts.append(child.text)
    parts.append(token.text)
    return " ".join(parts)


def extract_relationships(text: str, entities: list[dict]) -> list[dict]:
    """Extract SVO triples from dependency parse, filtered to known entities.

    Only includes relationships where **both** source and target match an
    entity name from *entities*.

    Returns list of dicts with keys: source, target, relation_type, description.
    """
    nlp = _get_nlp()
    with _nlp_lock:
        doc = nlp(text)

    entity_names: set[str] = {e["name"].lower() for e in entities}

    relationships: list[dict] = []
    for token in doc:
        if token.pos_ != "VERB":
            continue

        subjects: list[str] = []
        objects: list[str] = []

        for child in token.children:
            if child.dep_ in ("nsubj", "nsubjpass"):
                subjects.append(_get_span_text(child))
            elif child.dep_ in ("dobj", "attr"):
                objects.append(_get_span_text(child))
            elif child.dep_ == "prep":
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        objects.append(_get_span_text(grandchild))

        for subj_text in subjects:
            for obj_text in objects:
                if subj_text.lower() in entity_names and obj_text.lower() in entity_names:
                    relationships.append(
                        {
                            "source": subj_text,
                            "target": obj_text,
                            "relation_type": token.lemma_,
                            "description": f"{subj_text} {token.lemma_} {obj_text}",
                        }
                    )

    return relationships


# ---------------------------------------------------------------------------
# Entity resolution (fuzzy dedup)
# ---------------------------------------------------------------------------


def resolve_entity(
    name: str,
    entity_type: str,
    existing: list[dict],
    threshold: float | None = None,
) -> str | None:
    """Find an existing entity that fuzzy-matches *name* + *entity_type*.

    Returns the matched entity's ``name`` if found, ``None`` otherwise.
    Uses ``difflib.SequenceMatcher`` for string similarity.
    """
    if threshold is None:
        threshold = settings.entity_confidence_threshold

    name_lower = name.lower().strip()

    best_match: str | None = None
    best_ratio: float = 0.0

    for entity in existing:
        if entity.get("entity_type") != entity_type:
            continue

        existing_name = entity["name"].lower().strip()
        ratio = SequenceMatcher(None, name_lower, existing_name).ratio()

        if ratio >= threshold and ratio > best_ratio:
            best_ratio = ratio
            best_match = entity["name"]

    return best_match


# ---------------------------------------------------------------------------
# Async wrappers (CPU-bound offloading via run_in_executor)
# ---------------------------------------------------------------------------


async def extract_entities_async(text: str) -> list[dict]:
    """Async wrapper for :func:`extract_entities`."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, extract_entities, text)


async def extract_relationships_async(text: str, entities: list[dict]) -> list[dict]:
    """Async wrapper for :func:`extract_relationships`."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, extract_relationships, text, entities)
