package scraper

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestExtractItems(t *testing.T) {
	html := `
	<div class="item summary">
		<h2 class="title"><a href="/show/1">Show Title 1</a></h2>
	</div>
	<div class="item summary">
		<h2 class="title"><a href="/show/2">Show Title 2</a></h2>
	</div>`
	
	items := ExtractItems(html)
	if len(items) != 2 {
		t.Errorf("Expected 2 items, got %d", len(items))
	}
	if items[0].Title != "Show Title 1" {
		t.Errorf("Expected 'Show Title 1', got '%s'", items[0].Title)
	}
	if items[1].URL != "/show/2" {
		t.Errorf("Expected '/show/2', got '%s'", items[1].URL)
	}
}

func TestDownloadPage(t *testing.T) {
	// Mock Server
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		fmt.Fprint(w, "<html>Content</html>")
	}))
	defer ts.Close()

	content, err := DownloadPage(ts.URL)
	if err != nil {
		t.Errorf("DownloadPage failed: %v", err)
	}
	if content != "<html>Content</html>" {
		t.Errorf("Unexpected content: %s", content)
	}
}

func TestDownloadPage_RetryFail(t *testing.T) {
	ts := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer ts.Close()

	_, err := DownloadPage(ts.URL)
	if err == nil {
		t.Error("Expected error from 500 response, got nil")
	}
}

func TestGetListPage_Cache(t *testing.T) {
	tmpDir, _ := os.MkdirTemp("", "twittest")
	defer os.RemoveAll(tmpDir)
	
	filename := filepath.Join(tmpDir, "transcripts_page_6.html")
	os.WriteFile(filename, []byte("CachedContent"), 0644)
	
	// Should use cache for page 6
	content, err := GetListPage(6, tmpDir, false)
	if err != nil {
		t.Errorf("GetListPage failed: %v", err)
	}
	if content != "CachedContent" {
		t.Errorf("Expected 'CachedContent', got '%s'", content)
	}
}

func TestDownloadTranscript(t *testing.T) {
	tmpDir, _ := os.MkdirTemp("", "twittest")
	defer os.RemoveAll(tmpDir)
	
	// Mock download by mocking DownloadPage? 
	// Since DownloadPage uses http.Get, we can't easily mock it without dependency injection or modifying global state (bad).
	// But we can check if it SKIPS existing files without network.
	
	filename := filepath.Join(tmpDir, "IM_123.html")
	os.WriteFile(filename, []byte("Existing"), 0644)
	
	err := DownloadTranscript("/path", "Show 123", "IM", tmpDir)
	if err != nil {
		t.Errorf("DownloadTranscript failed: %v", err)
	}
	// Verify content didn't change (proving no download happened)
	content, _ := os.ReadFile(filename)
	if string(content) != "Existing" {
		t.Error("File was overwritten despite existing")
	}
}
