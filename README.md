# TWiT Transcript Archiver

This toolset allows you to download transcripts from the [TWiT.tv](https://twit.tv/) network and process them into clean, structured Markdown files optimized for Large Language Model (LLM) context windows, specifically Google NotebookLM.

It handles fetching, cleaning, and chunking transcripts to stay within token and file size limits.

## Features

* **Multi-Show Support:** Download transcripts for any major TWiT network show (e.g., *Intelligent Machines*, *This Week in Google*, *Windows Weekly*, *Security Now*).
* **Smart Caching:** Caches list pages to minimize server load while refreshing recent pages to catch new episodes.
* **Resume Capability:** Skips already downloaded transcript files to save bandwidth.
* **NotebookLM Ready:** Converts HTML to Markdown and chunks output files to stay under **500,000 words** / **200MB** limits.
* **Year-Based Splitting:** Option to split transcript chunks by calendar year for better organization.
* **Robust Logging:** Includes a `--debug` flag to trace scraping logic.
* **Security:** Enforces strict relative URL validation and sanitizes Markdown links.
* **Dual Implementation:** Available in both **Python** (dependency-free) and **Go** (performant).

## Directory Structure

* `data/`: Stores downloaded HTML files and generated Markdown output.
* `fetch_transcripts.py`: Python scraper script.
* `process_transcripts.py`: Python processing/chunking script.
* `go/`: Go implementation source tree.
* `tests/`: Python unit tests.

## Usage (Python)

The Python implementation relies on standard libraries only (`urllib`, `re`, `argparse`, `glob`). No `pip install` required.

### 1. Fetch Transcripts

Download raw HTML transcripts from TWiT.tv.

```bash
# Download specific shows (e.g., Intelligent Machines, This Week in Google)
python3 fetch_transcripts.py --shows "Intelligent Machines" "This Week in Google"

# Use show codes for brevity
python3 fetch_transcripts.py --shows IM TWIG

# Download ALL supported shows
python3 fetch_transcripts.py --all

# Refresh list pages (force re-download index)
python3 fetch_transcripts.py --refresh-list
```

### 2. Process Transcripts

Convert HTML files to Markdown and chunk them.

```bash
# Process specific shows
python3 process_transcripts.py --prefixes IM TWIG

# Process ALL downloaded shows
python3 process_transcripts.py --all

# Split by year (useful for large archives) as well as size limits
python3 process_transcripts.py --all --by-year
```

Output files will be saved in `data/`, e.g., `IM_Transcripts_2024_100_150.md`.

## Usage (Go)

The Go implementation offers the same functionality with improved performance. Requires Go 1.19+.

### 1. Build

```bash
cd go
go build -o fetch-transcripts ./cmd/fetch-transcripts
go build -o process-transcripts ./cmd/process-transcripts
```

### 2. Run

```bash
# Fetch
./fetch-transcripts IM TWIG
./fetch-transcripts --all

# Process
./process-transcripts --by-year IM
./process-transcripts --all
```

## Testing

### Python

Run the standard `unittest` suite:

```bash
python3 -m unittest discover tests
```

### Go

Run the Go test suite:

```bash
cd go
go test ./...
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository.
2. Create your feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4. Push to the branch (`git push origin feature/AmazingFeature`).
5. Open a Pull Request.

Please ensure all tests pass before submitting.
