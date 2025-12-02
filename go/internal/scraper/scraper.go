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

// GetListPage retrieves the list page content, using cache if appropriate
func GetListPage(pageNum int, dataDir string, forceRefresh bool) (string, error) {
	filename := filepath.Join(dataDir, fmt.Sprintf("transcripts_page_%d.html", pageNum))
	
	shouldDownload := true
	if !forceRefresh {
		if utils.FileExists(filename) {
			// Cache logic: Pages > 5 are cached indefinitely
			if pageNum > 5 {
				shouldDownload = false
			} else {
				// Recent pages (1-5) are re-downloaded to check for updates
				// In a real app we might check file age, but here we mimic the python script
				// which says "exists locally but is recent. Re-downloading"
				shouldDownload = true
			}
		}
	}
	
	if !shouldDownload {
		content, err := os.ReadFile(filename)
		if err == nil {
			return string(content), nil
		}
	}
	
	url := config.BaseListURL
	if pageNum > 1 {
		url = fmt.Sprintf("%s?page=%d", url, pageNum)
	}
	
	fmt.Printf("Downloading list page %d: %s\n", pageNum, url)
	content, err := DownloadPage(url)
	if err != nil {
		return "", err
	}
	
	err = os.WriteFile(filename, []byte(content), 0644)
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

// DownloadTranscript downloads a specific transcript
func DownloadTranscript(urlPath, title, prefix, dataDir string) error {
	// Extract episode number
	re := regexp.MustCompile(`(\d+)`)
	matches := re.FindStringSubmatch(title)
	epNum := "unknown"
	if len(matches) > 1 {
		epNum = matches[1]
	}
	
	filename := filepath.Join(dataDir, fmt.Sprintf("%s_%s.html", prefix, epNum))
	
	if utils.FileExists(filename) {
		return nil // Skip
	}
	
	fullURL := config.BaseSiteURL + urlPath
	fmt.Printf("Downloading %s %s: %s\n", prefix, epNum, title)
	
	content, err := DownloadPage(fullURL)
	if err != nil {
		return err
	}
	
	return os.WriteFile(filename, []byte(content), 0644)
}
