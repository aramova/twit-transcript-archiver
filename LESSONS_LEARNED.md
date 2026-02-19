# Lessons Learned: TWiT Transcript Standardization

Date: February 19, 2026

During the process of standardizing timestamps across historical TWiT and TWiG transcripts, we identified several edge cases and key principles for robust transcript parsing. This document serves to highlight these principles for future reference.

## 1. Variability of Formatting Over Time

Transcript formats often mutate dynamically over years. Relying on strict line structures is fragile.

* **The Problem:** While later transcripts cleanly formatted timestamps like `0:08:43 - Speaker`, earlier years (e.g., 2021-2022) had diverse variations such as `Speaker [0:08:43]:`, `Speaker (HH:MM:SS):`, or simply `(HH:MM:SS):` preceding the text.
* **The Solution:** We required an arsenal of regex patterns applied sequentially. When parsing semi-structured text acquired over a decade, assume the structure will deviate and build a cascading pattern-matching mechanism.

## 2. Granular Text Merging Strategies

Parsing HTML into markdown isn't just about stripping tags. Line breaks carry semantic meaning, or sometimes, *lack* thereof due to manual formatting limitations at the source.

* **The Problem:** Transcripts often presented the speaker and timestamp on one line, and the actual dialog on the next. A naïve parse resulted in disconnected data chunks. The RAG systems depend on contextual continuity (Speaker + Text).
* **The Solution:** Implemented "look-ahead" or delayed line writing. When a timestamp line is encountered, it is buffered. Subsequent lines that are *not* timestamps are merged forcefully into the buffered line before finally writing out. This ensures every final markdown line contains the `EP`, `Date`, `TS`, `Speaker`, and `Text` as a unified string.

## 3. Residual "Hanging" Characters

Format differences leave artifacts.

* **The Problem:** Some patterns stripped the speaker name but left stray colons (`:`) attached to the text block (e.g., `: You're listening to TWiT.`). While minor to a human reader, to a strict ingestion pipeline or RAG vectorizer, this represents dirty data.
* **The Solution:** Aggressive left-side stripping (`lstrip(": ")` in Python, `strings.TrimLeft(": ")` in Go) is necessary specifically on the `text` matches extracted from the regex groups, not just the whole string.

## 4. Multi-Language Codebase Parity is Critical

The project relies on both a rapid-development Python prototype script and a performant Go binary for bulk processing.

* **The Problem:** Fixing the Python script alone left the primary fast-path (Go) broken for older episodes. Test suites between the two also needed to remain synchronized.
* **The Solution:** Ensure that core structural logic (like the timestamp regex cascades and line-merging buffering logic) is implemented identically in both languages. Test suites must cover the exact same edge cases (e.g., Pattern 1 vs. Pattern 4 line merging).

## 5. Metadata Propagation as a Standard

Rather than expecting the LLM to understand what document it is embedded in, inject the metadata into every line.

* **The Standard:** Every single dialogue line in our corpus now strictly follows:
    `EP:[Number] Date:[YY-MM-DD] TS:[HH:MM:SS] - [Text]`
    This completely eliminates contextual loss during chunking inside vector databases.

## 6. Keep Build Artifacts Out

Always ignore internal logic docs, local brain logs, IDE tools (`.vscode`), and binaries (`.exe`, `go/bin`). The user is strictly keeping the source tracked.
