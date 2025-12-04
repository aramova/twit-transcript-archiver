# TWiT Transcript Archiver (Go Implementation)

This directory contains the high-performance Go implementation of the TWiT Transcript Archiver. It provides the same functionality as the Python version but leverages Go's strong typing, concurrency capabilities (future proofing), and single-binary deployment.

## Features

*   **Robust Scraping:** Resilient `DownloadPage` logic with retries and exponential backoff.
*   **Smart Caching:** `GetListPageWithCacheStatus` intelligently caches deep archive pages while refreshing recent ones (pages 1-5) to catch new episodes.
*   **Resume Capability:** Skips existing transcript files to save bandwidth.
*   **Summary Reporting:** Provides a detailed statistical summary (pages scanned, cached, transcripts downloaded/skipped) at the end of execution.
*   **Unit Tests:** Comprehensive test suite for core scraper logic.

## Directory Structure

*   `cmd/fetch-transcripts/`: Entry point for the downloader.
*   `cmd/process-transcripts/`: Entry point for the Markdown processor (if implemented).
*   `internal/scraper/`: Core scraping logic (`scraper.go`).
*   `internal/config/`: Configuration (URLs, Show Maps).
*   `internal/utils/`: File system utilities.

## Requirements

*   **Go 1.19** or higher.

## Installation

1.  Navigate to this directory:
    ```bash
    cd go
    ```
2.  Download dependencies:
    ```bash
    go mod tidy
    ```

## Build

To compile the binaries for production use:

```bash
# Build the fetcher binary
go build -o fetch-transcripts cmd/fetch-transcripts/main.go

# Build the processor binary
go build -o process-transcripts cmd/process-transcripts/main.go
```

## Usage

### Fetch Transcripts

Once built, you can run the `fetch-transcripts` binary directly:

```bash
# Download default shows (IM, TWIG)
./fetch-transcripts

# Download ALL supported shows
./fetch-transcripts --all

# Download specific shows (by name or code)
./fetch-transcripts --shows "Security Now" "Windows Weekly"
```

**Flags:**

*   `--all`: Download transcripts for all known shows defined in `internal/config`.
*   `--pages N`: Number of index pages to scan (default: 200).
*   `--refresh-list`: Force re-download of index pages, ignoring the cache.

### Process Transcripts

(If implemented)
```bash
./process-transcripts
```

## Key Functions

### `internal/scraper`

*   **`GetListPageWithCacheStatus(pageNum, dir, force) (content, cached, error)`**
    *   Retrieves the list page HTML.
    *   Returns `cached=true` if the file existed and was used (skipping network).
    *   Automatically refreshes pages 1-5 to ensure recent episodes are found.

*   **`DownloadTranscriptWithStatus(url, title, prefix, dir) (skipped, error)`**
    *   Downloads a specific episode transcript.
    *   Returns `skipped=true` if the file already exists locally.
    *   Handles file naming `PREFIX_EPNUM.html`.

*   **`ExtractItems(html) []Item`**
    *   Parses the raw HTML of a list page to extract transcript URLs and titles using Regex.

## Testing

To run the unit tests:

```bash
go test ./...
```

Expected output:
```text
ok      github.com/aramova/twit-transcript-archiver/go/internal/converter       0.005s
ok      github.com/aramova/twit-transcript-archiver/go/internal/scraper         7.009s
```
