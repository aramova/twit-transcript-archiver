package converter

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

// Constants
const (
	// NotebookLM Limits (as of early 2026)
	// Word Limit: 500,000 words per source
	// File Size Limit: 200MB per file
	// We use slightly lower operational limits to ensure compatibility.
	MaxWords = 490000
	MaxBytes = 190 * 1024 * 1024
)

// Pre-compiled regular expressions for performance
var (
	// General regexes
	yearCaptureRegex    = regexp.MustCompile(`(\d{4})`)
	episodeNumberRegex  = regexp.MustCompile(`_(\d+)\.html`)

	// HTML parsing regexes
	scriptTagRegex      = regexp.MustCompile(`(?s)<script.*?</script>`)
	styleTagRegex       = regexp.MustCompile(`(?s)<style.*?</style>`)
	h1TagRegex          = regexp.MustCompile(`(?s)<h1[^>]*>(.*?)</h1>`)
	h2TagRegex          = regexp.MustCompile(`(?s)<h2[^>]*>(.*?)</h2>`)
	h3TagRegex          = regexp.MustCompile(`(?s)<h3[^>]*>(.*?)</h3>`)
	pTagRegex           = regexp.MustCompile(`(?s)<p[^>]*>(.*?)</p>`)
	brTagRegex          = regexp.MustCompile(`(?i)<br\s*/?>`)
	boldTagRegex        = regexp.MustCompile(`(?s)<b[^>]*>(.*?)</b>`)
	strongTagRegex      = regexp.MustCompile(`(?s)<strong[^>]*>(.*?)</strong>`)
	italicTagRegex      = regexp.MustCompile(`(?s)<i[^>]*>(.*?)</i>`)
	emTagRegex          = regexp.MustCompile(`(?s)<em[^>]*>(.*?)</em>`)
	anchorTagRegex      = regexp.MustCompile(`(?s)<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>`)
	ulTagRegex          = regexp.MustCompile(`(?i)<ul[^>]*>`)
	ulEndTagRegex       = regexp.MustCompile(`(?i)</ul>`)
	liTagRegex          = regexp.MustCompile(`(?s)<li[^>]*>(.*?)</li>`)
	anyTagRegex         = regexp.MustCompile(`<[^>]+>`)
	
	// Metadata parsing regexes
	postTitleRegex = regexp.MustCompile(`<h1 class="post-title">(.*?)</h1>`)
	bylineRegex    = regexp.MustCompile(`(?s)<p class="byline">(.*?)</p>`)
	bodyContentRegex = regexp.MustCompile(`(?s)<div class="body textual">(.*?)</div>`)
)

// extractYear pulls a 4-digit year from a date string
func extractYear(dateStr string) int {
	matches := yearCaptureRegex.FindStringSubmatch(dateStr)
	if len(matches) > 1 {
		val, _ := strconv.Atoi(matches[1])
		return val
	}
	return 0
}

// HTMLToMarkdown converts raw HTML transcript content to Markdown
func HTMLToMarkdown(html string) string {
	if html == "" {
		return ""
	}
	
	text := html
	// Remove script/style
	text = scriptTagRegex.ReplaceAllString(text, "")
	text = styleTagRegex.ReplaceAllString(text, "")
	
	// Headers
	text = h1TagRegex.ReplaceAllString(text, "# $1\n\n")
	text = h2TagRegex.ReplaceAllString(text, "## $1\n\n")
	text = h3TagRegex.ReplaceAllString(text, "### $1\n\n")
	
	// Paragraphs
	text = pTagRegex.ReplaceAllString(text, "$1\n\n")
	
	// Breaks
	text = brTagRegex.ReplaceAllString(text, "\n")
	
	// Bold
	text = boldTagRegex.ReplaceAllString(text, "**$1**")
	text = strongTagRegex.ReplaceAllString(text, "**$1**")
	
	// Italic
	text = italicTagRegex.ReplaceAllString(text, "*$1*")
	text = emTagRegex.ReplaceAllString(text, "*$1*")
	
	// Links
	text = anchorTagRegex.ReplaceAllStringFunc(text, func(match string) string {
		sub := anchorTagRegex.FindStringSubmatch(match)
		if len(sub) < 3 {
			return "" // Should not happen given the match
		}
		url := sub[1]
		content := sub[2]
		
		// Security: Only allow http(s) or relative paths
		if strings.HasPrefix(url, "/") || strings.HasPrefix(url, "http://") || strings.HasPrefix(url, "https://") {
			return fmt.Sprintf("[%s](%s)", content, url)
		}
		return content
	})
	
	// Lists
	text = ulTagRegex.ReplaceAllString(text, "")
	text = ulEndTagRegex.ReplaceAllString(text, "\n")
	text = liTagRegex.ReplaceAllString(text, "* $1\n")
	
	// Tags cleanup
	text = anyTagRegex.ReplaceAllString(text, "")
	
	// Decode entities
	r := strings.NewReplacer(
		"&nbsp;", " ",
		"&amp;", "&",
		"&lt;", "<",
		"&gt;", ">",
		"&quot;", "\"",
		"&#39;", "'",
	)
	text = r.Replace(text)
	
	// Cleanup whitespace
	var lines []string
	for _, line := range strings.Split(text, "\n") {
		trimmed := strings.TrimSpace(line)
		if trimmed != "" {
			lines = append(lines, trimmed)
		} else if len(lines) > 0 && lines[len(lines)-1] != "" {
			lines = append(lines, "")
		}
	}
	
	return strings.TrimSpace(strings.Join(lines, "\n"))
}

// ParseTranscriptFile extracts title, date, year and body from a file
func ParseTranscriptFile(path string) (string, string, int, string, error) {
	contentBytes, err := os.ReadFile(path)
	if err != nil {
		return "", "", 0, "", err
	}
	html := string(contentBytes)
	
	title := "Unknown Episode"
	if matches := postTitleRegex.FindStringSubmatch(html); len(matches) > 1 {
		title = strings.TrimSpace(matches[1])
	}
	
dateStr := "Unknown Date"
	if matches := bylineRegex.FindStringSubmatch(html); len(matches) > 1 {
		dateStr = strings.TrimSpace(matches[1])
		// normalize whitespace
		dateStr = strings.Join(strings.Fields(dateStr), " ")
	}
	year := extractYear(dateStr)
	
	rawBody := ""
	if matches := bodyContentRegex.FindStringSubmatch(html); len(matches) > 1 {
		rawBody = matches[1]
	}
	
	return title, dateStr, year, HTMLToMarkdown(rawBody), nil
}

func GetEpNum(filename string) int {
	matches := episodeNumberRegex.FindStringSubmatch(filename)
	if len(matches) > 1 {
		val, _ := strconv.Atoi(matches[1])
		return val
	}
	return 0
}

func ProcessPrefix(prefix, dataDir, outputBase string, byYear bool) error {
	files, err := filepath.Glob(filepath.Join(dataDir, fmt.Sprintf("%s_*.html", prefix)))
	if err != nil {
		return err
	}
	
	if len(files) == 0 {
		fmt.Printf("No files found for prefix: %s\n", prefix)
		return nil
	}
	
	// Sort by episode number
	sort.Slice(files, func(i, j int) bool {
		return GetEpNum(files[i]) < GetEpNum(files[j])
	})
	
	fmt.Printf("Processing %d files for %s (By Year: %v)...
", len(files), prefix, byYear)
	
	currentWordCount := 0
	currentByteCount := 0
	var currentChunk []string
	var chunkStartEp, chunkEndEp int
	currentChunkYear := -1
	firstInChunk := true
	
	for _, fpath := range files {
		epNum := GetEpNum(fpath)
		title, dateStr, epYear, content, err := ParseTranscriptFile(fpath)
		if err != nil {
			fmt.Printf("Error processing %s: %v. Skipping.\n", fpath, err)
			continue
		}
		
		epText := fmt.Sprintf("# Episode: %s\n**Date:** %s\n\n%s\n\n---\n\n", title, dateStr, content)
		epWords := len(strings.Fields(content))
		epBytes := len([]byte(epText))

		// Check if we need to split the chunk
		splitNeeded := false
		if (currentWordCount+epWords > MaxWords) || (currentByteCount+epBytes > MaxBytes) {
			splitNeeded = true
		} else if byYear && currentChunkYear != -1 && epYear != currentChunkYear {
			splitNeeded = true
		}

		if splitNeeded && !firstInChunk {
			writeChunk(outputBase, prefix, chunkStartEp, chunkEndEp, currentChunkYear, currentChunk, byYear)
			
			// Reset
			currentChunk = []string{}
			currentWordCount = 0
			currentByteCount = 0
			firstInChunk = true
		}
		
		if firstInChunk {
			chunkStartEp = epNum
			currentChunkYear = epYear
			firstInChunk = false
		}
		
		currentChunk = append(currentChunk, epText)
		currentWordCount += epWords
		currentByteCount += epBytes
		chunkEndEp = epNum
	}
	
	if len(currentChunk) > 0 {
		writeChunk(outputBase, prefix, chunkStartEp, chunkEndEp, currentChunkYear, currentChunk, byYear)
	}
	
	return nil
}

func writeChunk(base, prefix string, start, end, year int, content []string, byYear bool) {
	var filename string
	if byYear && year > 0 {
		filename = filepath.Join(base, fmt.Sprintf("%s_Transcripts_%d_%d_%d.md", prefix, year, start, end))
	} else {
		filename = filepath.Join(base, fmt.Sprintf("%s_Transcripts_%d-%d.md", prefix, start, end))
	}
	
f, err := os.Create(filename)
	if err != nil {
		fmt.Printf("Error creating %s: %v\n", filename, err)
		return
	}
	defer f.Close()
	
	fullText := strings.Join(content, "")
	f.WriteString(fullText)
	fmt.Printf("Written %s (Words: approx %d, Bytes: %d)\n", filename, len(strings.Fields(fullText)), len([]byte(fullText)))
}
