# Phase 9: Entity & Relationship Extraction Service - Research

**Researched:** 2026-04-12
**Domain:** spaCy NLP (NER + dependency parsing), entity deduplication
**Confidence:** HIGH

## Summary

This phase builds an NLP extraction service (`entity_extraction.py`) that uses spaCy to extract named entities and subject-verb-object relationships from document chunk text. The codebase already has the exact pattern to follow in `embedding.py`: module-level singleton with double-checked locking via `threading.Lock`, all sync calls wrapped in `run_in_executor` for async compatibility. The `EntityType` enum in `models/graph.py` defines 8 types (person, organization, location, date, event, product, concept, other) that spaCy's 18 NER labels must map to. Entity deduplication uses `difflib.SequenceMatcher` from the standard library -- no new dependencies beyond spaCy itself.

The config already has `spacy_model` (default: `en_core_web_lg`), `entity_confidence_threshold` (0.7), and `max_entities_per_chunk` (50) settings in `config.py`. spaCy is NOT currently installed -- it must be added to `pyproject.toml` dependencies.

**Primary recommendation:** Follow the `embedding.py` lazy-load + lock pattern exactly. Use spaCy's dependency tree directly for SVO extraction (not textacy) to avoid an extra dependency. Map spaCy NER labels to EntityType via a simple dict lookup with `OTHER` as fallback.

## Standard Stack

### Core (new dependency)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| spacy | 3.8.14 (latest stable) | NER + dependency parsing | Industry standard NLP; project already has config fields for it |
| en_core_web_lg | 3.8.0 | Large English pipeline model | Best accuracy for NER (85.4 F1) + dependency parsing in non-transformer tier |
| en_core_web_sm | 3.8.0 | Small English pipeline model | Testing/CI (12MB vs 788MB); NER nearly as good (85.9 F1) |

### Supporting (already available, no install needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| difflib (stdlib) | N/A | Fuzzy entity matching via SequenceMatcher | Entity deduplication in resolve_entity() |
| threading (stdlib) | N/A | Lock for thread-safe model access | Same pattern as embedding.py |
| structlog | 24.4+ | Logging | Already in project |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| spaCy dep parse for SVO | textacy 0.13 | textacy adds a dependency for ~50 lines of SVO logic we can write ourselves |
| difflib.SequenceMatcher | rapidfuzz / fuzzywuzzy | SequenceMatcher is stdlib, no install; sufficient for entity name matching |
| en_core_web_lg | en_core_web_trf | Transformer model is more accurate but much slower, requires GPU for perf |

**Installation:**
```bash
pip install "spacy>=3.7,<4"
python -m spacy download en_core_web_lg
python -m spacy download en_core_web_sm  # for testing
```

**Version verification:**
- spacy latest stable: 3.8.14 (verified via pip index)
- pyproject.toml constraint `>=3.7,<4` covers this

## Architecture Patterns

### Project Structure (additions only)
```
src/docingest/
├── services/
│   ├── embedding.py          # EXISTING - pattern to follow
│   └── entity_extraction.py  # NEW - spaCy NER + SVO + dedup
└── models/
    └── graph.py              # EXISTING - EntityType enum to map to
```

### Pattern 1: Lazy-Loaded Singleton with Double-Checked Locking
**What:** Module-level `_model` variable, `threading.Lock`, double-checked locking in `_get_model()`.
**When to use:** Any expensive model that should load once and be shared across threads.
**Example (from embedding.py, the exact pattern to replicate):**
```python
import threading
import spacy
import structlog
from docingest.config import settings

log = structlog.get_logger()

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
```

### Pattern 2: run_in_executor for CPU-Bound Work
**What:** All spaCy calls are sync/CPU-bound. Wrap in `loop.run_in_executor(None, ...)`.
**When to use:** Any function calling spaCy's `nlp()`, which does tokenization + NER + parsing.
**Example (following CLAUDE.md convention):**
```python
import asyncio

async def extract_entities_async(text: str) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, extract_entities, text)
```

### Pattern 3: SpaCy Label to EntityType Mapping
**What:** Dict-based mapping from spaCy's 18 NER labels to our 8 EntityType values.
**When to use:** In `_map_spacy_label()`.
**Example:**
```python
from docingest.models.graph import EntityType

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
    # Mapped to CONCEPT (abstract/categorical)
    "NORP": EntityType.CONCEPT,       # nationalities, religious/political groups
    "LAW": EntityType.CONCEPT,
    "LANGUAGE": EntityType.CONCEPT,
    "WORK_OF_ART": EntityType.CONCEPT,
    # Numeric types -> OTHER (low value for graph)
    "CARDINAL": EntityType.OTHER,
    "ORDINAL": EntityType.OTHER,
    "MONEY": EntityType.OTHER,
    "PERCENT": EntityType.OTHER,
    "QUANTITY": EntityType.OTHER,
}


def _map_spacy_label(label: str) -> EntityType:
    return _SPACY_LABEL_MAP.get(label, EntityType.OTHER)
```

### Anti-Patterns to Avoid
- **Loading spaCy model per call:** Model loading takes 2-5 seconds. MUST use singleton pattern.
- **Calling nlp() on the async event loop:** spaCy is CPU-bound. Always use `run_in_executor`.
- **Using textacy for SVO:** Adds a dependency for something achievable with ~40 lines of dependency tree traversal.
- **Class-based service:** The codebase uses module-level functions (see embedding.py). Do not create an `EntityExtractor` class.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Named entity recognition | Regex/keyword patterns | spaCy NER pipeline | Handles context, coreference, 18 entity types |
| Tokenization + POS tagging | Custom tokenizer | spaCy tokenizer + tagger | Handles edge cases (contractions, URLs, etc.) |
| Dependency parsing | Custom parser | spaCy dep parser | Pre-trained on OntoNotes, 90+ UAS |
| String similarity | Levenshtein from scratch | difflib.SequenceMatcher | Stdlib, well-tested Ratcliff/Obershelp algorithm |

**Key insight:** spaCy bundles tokenization, NER, POS tagging, and dependency parsing in a single `nlp()` call. Do not split these into separate passes -- one call gives you everything.

## Common Pitfalls

### Pitfall 1: spaCy Model Not Downloaded
**What goes wrong:** `OSError: [E050] Can't find model 'en_core_web_lg'` at runtime.
**Why it happens:** `pip install spacy` does NOT install model data. Models must be downloaded separately.
**How to avoid:** Add model download to Docker build: `RUN python -m spacy download en_core_web_lg`. For dev, document in README. For tests, use `en_core_web_sm`.
**Warning signs:** Import succeeds but `spacy.load()` fails.

### Pitfall 2: spaCy nlp() Has a Default max_length of 1,000,000 Characters
**What goes wrong:** `ValueError` on very large texts.
**Why it happens:** spaCy's default `nlp.max_length` is 1M characters. Document chunks should be well under this, but it's a guardrail to know about.
**How to avoid:** Chunks from the chunker are typically <2000 tokens (~8000 chars). No action needed, but add a safety check.
**Warning signs:** ValueError mentioning max_length.

### Pitfall 3: Empty Entity List When Processing Short/Generic Text
**What goes wrong:** `extract_entities` returns empty list for text like "The system processes data efficiently."
**Why it happens:** spaCy NER only extracts named entities. Generic nouns are not entities.
**How to avoid:** This is expected behavior, not a bug. Do not lower confidence thresholds to force extraction. Document that entity extraction works best on information-rich text.
**Warning signs:** Low entity counts on technical/generic documentation.

### Pitfall 4: SVO Extraction Missing Passive Voice
**What goes wrong:** "The contract was signed by Microsoft" yields no SVO triple.
**Why it happens:** Passive constructions use `nsubjpass` instead of `nsubj`, and the agent is in a `prep` + `pobj` chain, not `dobj`.
**How to avoid:** Handle both `nsubj` and `nsubjpass` dependency labels. For passive voice, look for `agent` prep phrase to find the logical subject.
**Warning signs:** Missing relationships for passive-voice sentences.

### Pitfall 5: Fuzzy Match Threshold Too Low Causes False Merges
**What goes wrong:** "Apple Inc" matches "Apple" (the fruit) during dedup.
**Why it happens:** SequenceMatcher ratio for "Apple" vs "Apple Inc" is ~0.77, which passes a 0.7 threshold.
**How to avoid:** Use the `entity_confidence_threshold` (0.7) AND require same `entity_type` for matching. The type check prevents cross-type false merges. Consider a higher threshold (~0.85) for short entity names.
**Warning signs:** Unrelated entities being merged.

### Pitfall 6: Thread Safety During Model Inference
**What goes wrong:** Corrupted results when multiple threads call `nlp()` simultaneously.
**Why it happens:** spaCy's `Language` object is not thread-safe for `nlp()` calls.
**How to avoid:** Use `_nlp_lock` around all `nlp()` calls, same as embedding.py uses lock around `model.embed()`.
**Warning signs:** Intermittent garbled results or segfaults under load.

## Code Examples

### extract_entities Implementation
```python
def extract_entities(text: str) -> list[dict]:
    """Extract named entities from text using spaCy NER.

    Returns list of dicts with keys: name, entity_type, start_char, end_char.
    """
    nlp = _get_nlp()
    with _nlp_lock:
        doc = nlp(text)

    entities = []
    for ent in doc.ents:
        entity_type = _map_spacy_label(ent.label_)
        entities.append({
            "name": ent.text.strip(),
            "entity_type": entity_type,
            "start_char": ent.start_char,
            "end_char": ent.end_char,
        })

    # Respect max_entities_per_chunk config
    return entities[: settings.max_entities_per_chunk]
```

### extract_relationships (SVO from Dependency Parse)
```python
def extract_relationships(text: str, entities: list[dict]) -> list[dict]:
    """Extract SVO triples from dependency parse, filtered to known entities.

    Returns list of dicts with keys: subject, predicate, object,
    subject_char, object_char.
    """
    nlp = _get_nlp()
    with _nlp_lock:
        doc = nlp(text)

    # Build entity name set for filtering
    entity_names = {e["name"].lower() for e in entities}

    relationships = []
    for token in doc:
        # Find verbs that are ROOT or have subjects
        if token.pos_ != "VERB":
            continue

        subjects = []
        objects = []

        for child in token.children:
            if child.dep_ in ("nsubj", "nsubjpass"):
                # Expand to include compound modifiers
                subject_text = _get_span_text(child)
                subjects.append((subject_text, child.idx))
            elif child.dep_ in ("dobj", "attr"):
                object_text = _get_span_text(child)
                objects.append((object_text, child.idx))
            elif child.dep_ == "prep":
                # Handle prepositional objects (e.g., passive "signed by X")
                for grandchild in child.children:
                    if grandchild.dep_ == "pobj":
                        obj_text = _get_span_text(grandchild)
                        objects.append((obj_text, grandchild.idx))

        # Create relationship for each subject-object pair
        for subj_text, subj_idx in subjects:
            for obj_text, obj_idx in objects:
                # Filter: at least one side should be a known entity
                subj_match = subj_text.lower() in entity_names
                obj_match = obj_text.lower() in entity_names
                if subj_match or obj_match:
                    relationships.append({
                        "subject": subj_text,
                        "predicate": token.lemma_,
                        "object": obj_text,
                        "subject_char": subj_idx,
                        "object_char": obj_idx,
                    })

    return relationships


def _get_span_text(token) -> str:
    """Expand a token to include its compound modifiers."""
    parts = []
    for child in token.lefts:
        if child.dep_ in ("compound", "amod"):
            parts.append(child.text)
    parts.append(token.text)
    return " ".join(parts)
```

### resolve_entity (Fuzzy Dedup)
```python
from difflib import SequenceMatcher


def resolve_entity(
    name: str,
    entity_type: str,
    existing: list[dict],
    threshold: float | None = None,
) -> str | None:
    """Find existing entity that fuzzy-matches name + type.

    Returns the matched entity's name if found, None otherwise.
    Uses difflib.SequenceMatcher for string similarity.
    """
    if threshold is None:
        threshold = settings.entity_confidence_threshold

    name_lower = name.lower().strip()

    best_match: str | None = None
    best_ratio: float = 0.0

    for entity in existing:
        # Must be same type to match
        if entity.get("entity_type") != entity_type:
            continue

        existing_name = entity["name"].lower().strip()
        ratio = SequenceMatcher(None, name_lower, existing_name).ratio()

        if ratio >= threshold and ratio > best_ratio:
            best_ratio = ratio
            best_match = entity["name"]

    return best_match
```

## SpaCy NER Label to EntityType Mapping (Complete)

| spaCy Label | Description | EntityType | Rationale |
|-------------|-------------|------------|-----------|
| PERSON | People, including fictional | PERSON | Direct match |
| ORG | Companies, agencies, institutions | ORGANIZATION | Direct match |
| GPE | Countries, cities, states | LOCATION | Geopolitical = location |
| LOC | Non-GPE locations (mountains, rivers) | LOCATION | Direct match |
| FAC | Buildings, airports, highways | LOCATION | Facilities are locations |
| DATE | Absolute or relative dates | DATE | Direct match |
| TIME | Times smaller than a day | DATE | Time is a date subtype |
| EVENT | Named hurricanes, battles, sports events | EVENT | Direct match |
| PRODUCT | Vehicles, weapons, foods (not services) | PRODUCT | Direct match |
| NORP | Nationalities, religious/political groups | CONCEPT | Abstract grouping |
| LAW | Named documents made into laws | CONCEPT | Legal concept |
| LANGUAGE | Any named language | CONCEPT | Abstract concept |
| WORK_OF_ART | Titles of books, songs, etc. | CONCEPT | Creative work as concept |
| CARDINAL | Numerals not in other types | OTHER | Low graph value |
| ORDINAL | "first", "second", etc. | OTHER | Low graph value |
| MONEY | Monetary values including unit | OTHER | Low graph value |
| PERCENT | Percentage values | OTHER | Low graph value |
| QUANTITY | Measurements | OTHER | Low graph value |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| spaCy 2.x with separate model steps | spaCy 3.x with unified pipeline config | spaCy 3.0 (2021) | `spacy.load()` returns full pipeline; no separate steps |
| textacy for SVO extraction | spaCy DependencyMatcher or manual dep traversal | spaCy 3.0+ | DependencyMatcher built into spaCy; textacy still works but is optional |
| fuzzywuzzy for string matching | rapidfuzz (or stdlib difflib) | 2022+ | fuzzywuzzy deprecated; rapidfuzz is faster; difflib is stdlib |
| spaCy 3.7 models | spaCy 3.8 models | 2025 | Latest models have same NER labels; minor accuracy improvements |

**Deprecated/outdated:**
- spaCy 2.x API (Language.factories, nlp.create_pipe) -- replaced by config system in 3.x
- textacy < 0.11 SVO extraction -- API changed significantly
- fuzzywuzzy -- deprecated in favor of rapidfuzz; but difflib is sufficient here

## Open Questions

1. **Should we filter out OTHER-type entities before graph storage?**
   - What we know: CARDINAL, ORDINAL, MONEY, PERCENT, QUANTITY map to OTHER. These are typically noise for knowledge graphs (e.g., "42", "first", "$1.5M").
   - What's unclear: Whether any use case benefits from storing numeric entities.
   - Recommendation: Filter out OTHER-type entities by default. This reduces noise and storage. Can be made configurable later.

2. **en_core_web_lg model download in Docker**
   - What we know: The model is ~788MB. Must be downloaded separately from pip install.
   - What's unclear: Best caching strategy for Docker builds.
   - Recommendation: Add `RUN python -m spacy download en_core_web_lg` to Dockerfile. Use Docker layer caching (place after pip install but before COPY src). For CI, cache the model in a volume.

3. **Should extract_relationships also return triples where NEITHER side is a known entity?**
   - What we know: The phase spec says to extract SVO triples. Filtering to entity-connected triples reduces noise but may miss useful relationships.
   - Recommendation: Default to filtering (at least one side must be a known entity). This keeps relationship count manageable and graph-relevant.

4. **Thread lock granularity: per-call vs per-batch?**
   - What we know: embedding.py locks per batch call. spaCy is not thread-safe.
   - Recommendation: Lock around each `nlp()` call (same as embedding.py locks around `model.embed()`). If batch processing is needed later, lock the whole batch.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.25.x |
| Config file | pyproject.toml [tool.pytest.ini_options] |
| Quick run command | `pytest tests/test_entity_extraction.py -x -q` |
| Full suite command | `pytest tests/` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EE-01 | extract_entities returns entity dicts with name, type, start/end chars | unit | `pytest tests/test_entity_extraction.py::test_extract_entities -x` | No - Wave 0 |
| EE-02 | _map_spacy_label maps all 18 labels correctly | unit | `pytest tests/test_entity_extraction.py::test_label_mapping -x` | No - Wave 0 |
| EE-03 | extract_relationships finds SVO triples | unit | `pytest tests/test_entity_extraction.py::test_extract_relationships -x` | No - Wave 0 |
| EE-04 | resolve_entity finds fuzzy matches above threshold | unit | `pytest tests/test_entity_extraction.py::test_resolve_entity -x` | No - Wave 0 |
| EE-05 | resolve_entity returns None below threshold | unit | `pytest tests/test_entity_extraction.py::test_resolve_entity_no_match -x` | No - Wave 0 |
| EE-06 | resolve_entity requires same entity_type | unit | `pytest tests/test_entity_extraction.py::test_resolve_entity_type_mismatch -x` | No - Wave 0 |
| EE-07 | Lazy model loading with thread safety | unit | `pytest tests/test_entity_extraction.py::test_lazy_load -x` | No - Wave 0 |
| EE-08 | max_entities_per_chunk config respected | unit | `pytest tests/test_entity_extraction.py::test_max_entities -x` | No - Wave 0 |

### Testing Strategy: Mock vs Real spaCy
- For unit tests, use `en_core_web_sm` (12MB) -- fast to download in CI, same API as `en_core_web_lg`
- NER accuracy difference is negligible (85.9 vs 85.4 F1) and does not affect functional testing
- Override `settings.spacy_model` in test fixtures to use `en_core_web_sm`
- For `_map_spacy_label` and `resolve_entity` tests, no spaCy model needed at all (pure logic)

### Wave 0 Gaps
- [ ] `tests/test_entity_extraction.py` -- covers EE-01 through EE-08
- [ ] spaCy en_core_web_sm model download for test environment

## Sources

### Primary (HIGH confidence)
- `src/docingest/services/embedding.py` -- lazy-load + lock pattern (lines 1-27)
- `src/docingest/models/graph.py` -- EntityType enum (8 values: person, organization, location, date, event, product, concept, other)
- `src/docingest/config.py` -- existing config fields: spacy_model, entity_confidence_threshold, max_entities_per_chunk
- [spaCy en_core_web_lg on HuggingFace](https://huggingface.co/spacy/en_core_web_lg) -- 18 NER labels, accuracy scores (NER F1: 85.43)
- [spaCy Linguistic Features](https://spacy.io/usage/linguistic-features) -- dependency labels (nsubj, nsubjpass, dobj, pobj)
- pip index: spacy 3.8.14 (latest stable)

### Secondary (MEDIUM confidence)
- [spaCy Discussion #6280](https://github.com/explosion/spaCy/discussions/6280) -- SVO extraction approaches
- [textacy extract.triples source](https://github.com/chartbeat-labs/textacy/blob/main/src/textacy/extract/triples.py) -- SVO algorithm: nsubj/nsubjpass for subjects, dobj/attr/pobj for objects, compound expansion
- [Python difflib docs](https://docs.python.org/3/library/difflib.html) -- SequenceMatcher.ratio() uses Ratcliff/Obershelp, returns 0-1 float

### Tertiary (LOW confidence)
- Fuzzy match threshold 0.85 for short names -- based on community practice, not rigorous evaluation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- spaCy is the established choice; config already prepared for it
- Architecture: HIGH -- directly replicating existing embedding.py pattern
- NER label mapping: HIGH -- 18 labels verified from HuggingFace model card
- SVO extraction: MEDIUM -- manual dep tree traversal is well-documented but edge cases (passive voice, relative clauses, coordination) need testing
- Fuzzy dedup threshold: MEDIUM -- 0.7 default from config; may need tuning in practice

**Research date:** 2026-04-12
**Valid until:** 2026-05-12 (spaCy 3.x is stable; NER labels unchanged across 3.7-3.8)
