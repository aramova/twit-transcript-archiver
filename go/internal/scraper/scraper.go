package scraper

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/aramova/twit-transcript-archiver/go/internal/config"
	"github.com/aramova/twit-transcript-archiver/go/internal/utils"
)

type Item struct {
	URL   string
	Title string
}

// DownloadPage downloads content from a URL with retries and throttling
func DownloadPage(url string, throttle time.Duration) (string, error) {
	var lastErr error
	for retries := 3; retries > 0; retries-- {
		client := &http.Client{}
		req, err := http.NewRequest("GET", url, nil)
		if err != nil {
			lastErr = err
			time.Sleep(2 * time.Second)
			continue
		}
		req.Header.Set("User-Agent", config.UserAgent)

		resp, err := client.Do(req)
		if err != nil {
			lastErr = err
			time.Sleep(2 * time.Second)
			continue
		}
		defer resp.Body.Close()

		if resp.StatusCode != 200 {
			lastErr = fmt.Errorf("status code %d", resp.StatusCode)
			time.Sleep(2 * time.Second)
			continue
		}

		body, err := io.ReadAll(resp.Body)
		if err != nil {
			lastErr = err
			time.Sleep(2 * time.Second)
			continue
		}

		if throttle > 0 {
			time.Sleep(throttle)
		}
		return string(body), nil
	}
	return "", fmt.Errorf("failed after retries: %v", lastErr)
}

// GetListPageWithCacheStatus retrieves the list page content, using cache if appropriate
// Returns content, isCached, error
func GetListPageWithCacheStatus(pageNum int, dataDir string, forceRefresh bool, throttle time.Duration) (string, bool, error) {
	filename := filepath.Join(dataDir, fmt.Sprintf("transcripts_page_%d.html", pageNum))

	shouldDownload := true
	if !forceRefresh {
		if utils.FileExists(filename) {
			// Cache logic: Pages > 5 are cached indefinitely
			if pageNum > 5 {
				shouldDownload = false
			} else {
				// Recent pages (1-5) are re-downloaded to check for updates
				shouldDownload = true
			}
		}
	}

	if !shouldDownload {
		content, err := os.ReadFile(filename)
		if err == nil {
			return string(content), true, nil
		}
	}

	url := config.BaseListURL
	if pageNum > 1 {
		url = fmt.Sprintf("%s?page=%d", url, pageNum)
	}

	fmt.Printf("Downloading list page %d: %s\n", pageNum, url)
	content, err := DownloadPage(url, throttle)
	if err != nil {
		return "", false, err
	}

	err = os.WriteFile(filename, []byte(content), 0644)
	return content, false, err
}

// Wrapper for backward compatibility if needed, though we updated main.go
func GetListPage(pageNum int, dataDir string, forceRefresh bool, throttle time.Duration) (string, error) {
	content, _, err := GetListPageWithCacheStatus(pageNum, dataDir, forceRefresh, throttle)
	return content, err
}

// ExtractItems parses the HTML list page to find transcripts
func ExtractItems(html string) []Item {
	// <div class="item summary">.*?<h2 class="title"><a href="([^"]+)">([^<]+)</a></h2>
	re := regexp.MustCompile(`(?s)<div class="item summary">.*?<h2 class="title"><a href="([^"]+)">([^<]+)</a></h2>`)
	matches := re.FindAllStringSubmatch(html, -1)

	var items []Item
	for _, match := range matches {
		if len(match) >= 3 {
			url := match[1]
			// Security: Ensure strict relative path
			if !strings.HasPrefix(url, "/") {
				continue
			}

			items = append(items, Item{
				URL:   url,
				Title: strings.TrimSpace(match[2]),
			})
		}
	}
	return items
}

// DownloadTranscriptWithStatus downloads a specific transcript
// Returns skipped (bool) and error
func DownloadTranscriptWithStatus(urlPath, title, prefix, dataDir string, throttle time.Duration) (bool, error) {
	// Extract episode number
	re := regexp.MustCompile(`(\d+)`)
	matches := re.FindStringSubmatch(title)
	epNum := "unknown"
	if len(matches) > 1 {
		epNum = matches[1]
	}

	filename := filepath.Join(dataDir, fmt.Sprintf("%s_%s.html", prefix, epNum))

	if utils.FileExists(filename) {
		return true, nil // Skipped
	}

	fullURL := config.BaseSiteURL + urlPath
	fmt.Printf("Downloading %s %s: %s\n", prefix, epNum, title)

	content, err := DownloadPage(fullURL, throttle)
	if err != nil {
		return false, err
	}

	return false, os.WriteFile(filename, []byte(content), 0644)
}

// Wrapper
func DownloadTranscript(urlPath, title, prefix, dataDir string, throttle time.Duration) error {
	_, err := DownloadTranscriptWithStatus(urlPath, title, prefix, dataDir, throttle)
	return err
}
