Docingest Expansion Plan: Legislative Support
=============================================

To support the complex requirements of legislative ingestion (as seen in Legiscan data), Docingest must move beyond simple semantic chunking to **Structural and Context-Aware Ingestion**.

1. Database Schema Changes (MongoDB)

------------------------------------

The current metadata store needs to support the hierarchical and state-specific nature of bills.

### `documents` Collection Enhancements

* `jurisdiction`: (String) e.g., "VA", "CA", "US_FED".

* `bill_metadata`: (Object)
  
  * `bill_number`: (String) e.g., "HB 1234".
  
  * `session`: (String) e.g., "2024 Regular Session".
  
  * `status`: (String) e.g., "Introduced", "Passed".
  
  * `last_action_date`: (ISODate).

* `structure_map`: (Array of Objects) A map of identified sections to help the agent navigate:
  
  * `section_type`: (Enum) `FINDINGS`, `DEFINITIONS`, `ENACTING_CLAUSE`, `AMENDMENT`.
  
  * `markdown_heading`: (String).
  
  * `page_range`: (Tuple).

* `summary_v1`: (String) The "Golden Summary" generated during ingestion for token-efficient retrieval.

### `chunks` (Qdrant Payload) Enhancements

* Add `section_context`: The heading/title of the parent section to prevent "lost context" during RAG.

* Add `chunk_type`: `NARRATIVE` vs `STATUTORY_CODE` (very important for legislative analysis).
2. API Endpoint Additions

-------------------------

To support an agentic consumer like Abacus AI, the API must move from "Search" to "Discovery."

| **Method** | **Path**                      | **Description**                                                                     |
| ---------- | ----------------------------- | ----------------------------------------------------------------------------------- |
| `POST`     | `/v1/search/hybrid`           | Combined vector search + metadata filtering (e.g., "Search for solar bills in VA"). |
| `GET`      | `/v1/documents/{id}/summary`  | Returns the pre-computed high-fidelity summary.                                     |
| `GET`      | `/v1/documents/{id}/sections` | Returns the structural map for agentic navigation.                                  |
| `POST`     | `/v1/classify`                | Trigger an LLM-based classification of an ingested bill into legal categories.      |
| `GET`      | `/v1/jurisdictions/stats`     | Aggregated view of bill volume by state/year.                                       |

3. Pipeline & Logic Enhancements

--------------------------------

### A. The "Legislative Docling" Pipeline

Modify the `converter-worker` to include specialized regex or LLM-based "Segmenters":

1. **Header Stripping**: Use `Docling`'s layout detection to aggressively remove recurring page headers/footers found in state bills.

2. **Section Isolation**: Identify the "Enacting Clause." Content before this is usually "Findings" (high semantic value); content after is "Code" (high precision value).

### B. Two-Pass Ingestion (ARQ Workflow)

1. **Pass 1 (Convert & Extract)**: Docling to Markdown + Metadata extraction.

2. **Pass 2 (Synthesize)**: Trigger a "Synthesis Job" that uses a small LLM (e.g., Gemini Flash) to create a 500-word summary and tag the bill with 3–5 primary categories. This summary is stored in MongoDB and indexed in Qdrant as a single "Super-Chunk."

4. Additional Libraries & Infrastructure

----------------------------------------

To support these features, the following should be added to `requirements.txt`:

1. **`pydantic-settings`**: To manage more complex environment configurations for different jurisdictions.

2. **`instructor` or `outlines`**: For guaranteed JSON schema output when the pipeline performs "Pass 2" (Summary/Classification).

3. **`langchain-text-splitters`**: Specifically the `MarkdownHeaderTextSplitter` to ensure chunks never break in the middle of a legal definition.

4. **`sumy` (Optional)**: For fast, non-LLM extractive summarization as a fallback.

5. Agentic Integration (The "Deep Agent" Hook)

----------------------------------------------

The Deep Agent requires a specific output format to be effective. We should add a `Context Formatter` service to Docingest that returns search results as:
    {
      "context": "[Bill VA-HB10] Section 2: Definitions. 'Renewable energy' means...",
      "source_metadata": {
        "jurisdiction": "VA",
        "bill_link": "[https://legiscan.com/](https://legiscan.com/)...",
        "confidence_score": 0.94
      }
    }

This ensures the Abacus AI Agent can cite the exact bill and section in its final reasoning.
