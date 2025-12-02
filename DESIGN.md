# Design Document: TWiT Transcript Toolset

## Overview
The goal of this project is to create a reliable pipeline for acquiring transcript data from the TWiT.tv network and preparing it for ingestion into Large Language Models (LLMs), specifically Google NotebookLM. The primary constraints are file size limits (500k words) and the need for clean, structured text.

## Components

### 1. Fetcher (`fetch_transcripts.py`)

**Architecture:**
*   **Source:** Scrapes the paginated list at `https://twit.tv/posts/transcripts`.
*   **Identification:** Uses a `SHOW_MAP` dictionary to map show titles (e.g., "This Week in Google") to internal prefixes (e.g., "TWIG").
*   **Logic:**
    *   Iterates through pages 1 to `N`.
    *   Downloads list pages to `data/transcripts_page_{N}.html` (caching strategy: refresh recent pages, cache older ones).
    *   Parses HTML using regex (dependency-free) to find transcript links.
    *   Checks if the transcript title matches a requested show.
    *   Checks if the target file `data/{PREFIX}_{EP_NUM}.html` already exists.
    *   Downloads missing files.

**Design Decisions:**
*   **Regex vs BeautifulSoup:** Regex was chosen to avoid external dependencies (`pip install`), making the script portable and easy to run in restricted environments.
*   **Episode Number Parsing:** Critical for sorting. Extracted from the title (`re.search(r'(\d+)', title)`).
*   **Error Handling:** Implements retries for network requests to handle intermittent failures.

### 2. Processor (`process_transcripts.py`)

**Architecture:**
*   **Input:** Scans `data/` for files matching `{PREFIX}_*.html`.
*   **Parsing:**
    *   Extracts metadata: Title (`<h1>`), Date (`<p class="byline">`), and Body (`<div class="body textual">`).
    *   **HTML to Markdown:** A custom parser converts HTML tags (`<p>`, `<b>`, `<a>`) to Markdown equivalents to preserve structure without the HTML overhead.
*   **Chunking Strategy:**
    *   Sorts episodes numerically.
    *   Accumulates text into a buffer.
    *   Checks word count (approx. by splitting on whitespace) and byte size before adding an episode.
    *   **Hard Limit:** 450,000 words (safely under the 500k NotebookLM limit).
    *   **File Naming:** `data/{PREFIX}_Transcripts_{START_EP}-{END_EP}.md`.

**Why Chunking?**
*   LLM context windows and RAG (Retrieval-Augmented Generation) systems often have per-file limits.
*   Combining files reduces the number of "sources" used in NotebookLM (limit 50), allowing for years of content to be uploaded in just a few slots.

## Data Flow

1.  `fetch_transcripts.py` -> Downloads HTML -> `data/IM_847.html`
2.  `process_transcripts.py` -> Reads HTML -> Cleans & Formats -> Chunks -> `data/IM_Transcripts_847-847.md`
3.  User -> Uploads `.md` files to NotebookLM.

## Limitations
*   **Archive Depth:** The TWiT.tv transcript index seems to stop around 2014. Episodes prior to this are not accessible via this specific list scraping method.
*   **Formatting:** The HTML to Markdown conversion is heuristic-based. Complex tables or unusual HTML structures might be simplified.
