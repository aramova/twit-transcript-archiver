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

// DownloadPage downloads content from a URL with retries
func DownloadPage(url string) (string, error) {
	var lastErr error
	for retries := 3; retries > 0; retries-- {
		resp, err := http.Get(url)
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
		
		time.Sleep(1 * time.Second) // Be nice
		return string(body), nil
	}
	return "", fmt.Errorf("failed after retries: %v", lastErr)
}

// GetListPageWithCacheStatus retrieves the list page content, using cache if appropriate
// Returns content, isCached, error
func GetListPageWithCacheStatus(pageNum int, dataDir string, forceRefresh bool) (string, bool, error) {
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
	content, err := DownloadPage(url)
	if err != nil {
		return "", false, err
	}
	
	err = os.WriteFile(filename, []byte(content), 0644)
	return content, false, err
}

// Wrapper for backward compatibility if needed, though we updated main.go
func GetListPage(pageNum int, dataDir string, forceRefresh bool) (string, error) {
	content, _, err := GetListPageWithCacheStatus(pageNum, dataDir, forceRefresh)
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
func DownloadTranscriptWithStatus(urlPath, title, prefix, dataDir string) (bool, error) {
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
	
	content, err := DownloadPage(fullURL)
	if err != nil {
		return false, err
	}
	
	return false, os.WriteFile(filename, []byte(content), 0644)
}

// Wrapper
func DownloadTranscript(urlPath, title, prefix, dataDir string) error {
	_, err := DownloadTranscriptWithStatus(urlPath, title, prefix, dataDir)
	return err
}
