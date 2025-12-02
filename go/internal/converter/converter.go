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
	MaxWords = 450000
	MaxBytes = 180 * 1024 * 1024
)

// HTMLToMarkdown converts raw HTML transcript content to Markdown
func HTMLToMarkdown(html string) string {
	if html == "" {
		return ""
	}
	
	text := html
	// Remove script/style
	reScript := regexp.MustCompile(`(?s)<script.*?</script>`)
	text = reScript.ReplaceAllString(text, "")
	reStyle := regexp.MustCompile(`(?s)<style.*?</style>`)
	text = reStyle.ReplaceAllString(text, "")
	
	// Headers
	reH1 := regexp.MustCompile(`(?s)<h1[^>]*>(.*?)</h1>`)
	text = reH1.ReplaceAllString(text, "# $1\n\n")
	
	reH2 := regexp.MustCompile(`(?s)<h2[^>]*>(.*?)</h2>`)
	text = reH2.ReplaceAllString(text, "## $1\n\n")
	
	reH3 := regexp.MustCompile(`(?s)<h3[^>]*>(.*?)</h3>`)
	text = reH3.ReplaceAllString(text, "### $1\n\n")
	
	// Paragraphs
	reP := regexp.MustCompile(`(?s)<p[^>]*>(.*?)</p>`)
	text = reP.ReplaceAllString(text, "$1\n\n")
	
	// Breaks
	reBr := regexp.MustCompile(`(?i)<br\s*/?>`)
	text = reBr.ReplaceAllString(text, "\n")
	
	// Bold
	reBold := regexp.MustCompile(`(?s)<b[^>]*>(.*?)</b>`)
	text = reBold.ReplaceAllString(text, "**$1**")
	reStrong := regexp.MustCompile(`(?s)<strong[^>]*>(.*?)</strong>`)
	text = reStrong.ReplaceAllString(text, "**$1**")
	
	// Italic
	reItalic := regexp.MustCompile(`(?s)<i[^>]*>(.*?)</i>`)
	text = reItalic.ReplaceAllString(text, "*$1*")
	reEm := regexp.MustCompile(`(?s)<em[^>]*>(.*?)</em>`)
	text = reEm.ReplaceAllString(text, "*$1*")
	
	// Links
	reLink := regexp.MustCompile(`(?s)<a\s+(?:[^>]*?\s+)?href=["']([^"]*)["'][^>]*>(.*?)</a>`)
	text = reLink.ReplaceAllStringFunc(text, func(match string) string {
		sub := reLink.FindStringSubmatch(match)
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
	reUl := regexp.MustCompile(`(?i)<ul[^>]*>`) // Note: No need to escape / in Go raw strings
	text = reUl.ReplaceAllString(text, "")
	reUlEnd := regexp.MustCompile(`(?i)</ul>`)
	text = reUlEnd.ReplaceAllString(text, "\n")
	reLi := regexp.MustCompile(`(?s)<li[^>]*>(.*?)</li>`)
	text = reLi.ReplaceAllString(text, "* $1\n")
	
	// Tags cleanup
	reTags := regexp.MustCompile(`<[^>]+>`) // Note: No need to escape / in Go raw strings
	text = reTags.ReplaceAllString(text, "")
	
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

// ParseTranscriptFile extracts title, date, and body from a file
func ParseTranscriptFile(path string) (string, string, string, error) {
	contentBytes, err := os.ReadFile(path)
	if err != nil {
		return "", "", "", err
	}
	html := string(contentBytes)
	
	reTitle := regexp.MustCompile(`<h1 class="post-title">(.*?)</h1>`)
	reDate := regexp.MustCompile(`(?s)<p class="byline">(.*?)</p>`)
	reBody := regexp.MustCompile(`(?s)<div class="body textual">(.*?)</div>`)
	
	title := "Unknown Episode"
	if matches := reTitle.FindStringSubmatch(html); len(matches) > 1 {
		title = strings.TrimSpace(matches[1])
	}
	
	dateStr := "Unknown Date"
	if matches := reDate.FindStringSubmatch(html); len(matches) > 1 {
		dateStr = strings.TrimSpace(matches[1])
		// normalize whitespace
		dateStr = strings.Join(strings.Fields(dateStr), " ")
	}
	
	rawBody := ""
	if matches := reBody.FindStringSubmatch(html); len(matches) > 1 {
		rawBody = matches[1]
	}
	
	return title, dateStr, HTMLToMarkdown(rawBody), nil
}

func GetEpNum(filename string) int {
	re := regexp.MustCompile(`_(\d+)\.html`)
	matches := re.FindStringSubmatch(filename)
	if len(matches) > 1 {
		val, _ := strconv.Atoi(matches[1])
		return val
	}
	return 0
}

func ProcessPrefix(prefix, dataDir, outputBase string) error {
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
	
	fmt.Printf("Processing %d files for %s...\n", len(files), prefix)
	
	currentWordCount := 0
	currentByteCount := 0
	var currentChunk []string
	var chunkStartEp, chunkEndEp int
	firstInChunk := true
	
	for _, fpath := range files {
		epNum := GetEpNum(fpath)
		title, dateStr, content, err := ParseTranscriptFile(fpath)
		if err != nil {
			fmt.Printf("Error processing %s: %v. Skipping.\n", fpath, err)
			continue
		}
		
		if firstInChunk {
			chunkStartEp = epNum
			firstInChunk = false
		}
		
		epText := fmt.Sprintf("# Episode: %s\n**Date:** %s\n\n%s\n\n---\n\n", title, dateStr, content)
		
		epWords := len(strings.Fields(content))
		epBytes := len([]byte(epText))
		
		if (currentWordCount+epWords > MaxWords) || (currentByteCount+epBytes > MaxBytes) {
			writeChunk(outputBase, prefix, chunkStartEp, chunkEndEp, currentChunk)
			
			// Reset
			currentChunk = []string{}
			currentWordCount = 0
			currentByteCount = 0
			chunkStartEp = epNum
		}
		
		currentChunk = append(currentChunk, epText)
		currentWordCount += epWords
		currentByteCount += epBytes
		chunkEndEp = epNum
	}
	
	if len(currentChunk) > 0 {
		writeChunk(outputBase, prefix, chunkStartEp, chunkEndEp, currentChunk)
	}
	
	return nil
}

func writeChunk(base, prefix string, start, end int, content []string) {
	filename := filepath.Join(base, fmt.Sprintf("%s_Transcripts_%d-%d.md", prefix, start, end))
	f, err := os.Create(filename)
	if err != nil {
		fmt.Printf("Error creating %s: %v\n", filename, err)
		return
	}
	defer f.Close()
	
	fullText := strings.Join(content, "")
	f.WriteString(fullText)
	fmt.Printf("Written %s (Words: approx %d)\n", filename, len(strings.Fields(fullText)))
}
