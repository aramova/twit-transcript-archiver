package converter

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestHTMLToMarkdown(t *testing.T) {
	tests := []struct {
		input    string
		expected string
	}{
		{"<p>Hello <b>World</b></p>", "Hello **World**"},
		{"<h1>Title</h1>", "# Title"},
		{"<a href='/link'>text</a>", "[text](/link)"},
		{"<ul><li>A</li><li>B</li></ul>", "* A\n* B"},
		{"<script>bad</script>Good", "Good"},
	}

	for _, tt := range tests {
		got := HTMLToMarkdown(tt.input)
		if !strings.Contains(got, tt.expected) {
			t.Errorf("HTMLToMarkdown(%q) = %q; want %q", tt.input, got, tt.expected)
		}
	}
}

func TestGetEpNum(t *testing.T) {
	if n := GetEpNum("IM_100.html"); n != 100 {
		t.Errorf("Expected 100, got %d", n)
	}
	if n := GetEpNum("bad.html"); n != 0 {
		t.Errorf("Expected 0, got %d", n)
	}
}

func TestProcessPrefix(t *testing.T) {
	tmpDir, _ := os.MkdirTemp("", "processtest")
	defer os.RemoveAll(tmpDir)

	// Create dummy input files
	f1 := filepath.Join(tmpDir, "IM_1.html")
	os.WriteFile(f1, []byte(`
		<h1 class="post-title">Ep 1</h1>
		<p class="byline">Feb 1st 2025</p>
		<div class="body textual">Content 1</div>
	`), 0644)
	
	f2 := filepath.Join(tmpDir, "IM_2.html")
	os.WriteFile(f2, []byte(`
		<h1 class="post-title">Ep 2</h1>
		<p class="byline">Feb 2nd 2025</p>
		<div class="body textual">Content 2</div>
	`), 0644)

	err := ProcessPrefix("IM", tmpDir, tmpDir, false)
	if err != nil {
		t.Fatalf("ProcessPrefix failed: %v", err)
	}

	// Check output
	files, _ := filepath.Glob(filepath.Join(tmpDir, "IM_Transcripts_1-2.md"))
	if len(files) != 1 {
		t.Error("Output file not created")
	} else {
		content, _ := os.ReadFile(files[0])
		s := string(content)
		if !strings.Contains(s, "# Episode: Ep 1") {
			t.Error("Output missing content from Ep 1")
		}
		if !strings.Contains(s, "# Episode: Ep 2") {
			t.Error("Output missing content from Ep 2")
		}
	}
}

func TestProcessPrefixByYear(t *testing.T) {
	tmpDir, err := os.MkdirTemp("", "processtestyear")
	if err != nil {
		t.Fatalf("failed to create temp dir: %v", err)
	}
	defer os.RemoveAll(tmpDir)

	// Create dummy input files across different years
	f1 := filepath.Join(tmpDir, "IM_1.html")
	os.WriteFile(f1, []byte(`
		<h1 class="post-title">Ep 1</h1>
		<p class="byline">Dec 31st 2024</p>
		<div class="body textual">Content 2024</div>
	`), 0644)
	
	f2 := filepath.Join(tmpDir, "IM_2.html")
	os.WriteFile(f2, []byte(`
		<h1 class="post-title">Ep 2</h1>
		<p class="byline">Jan 1st 2025</p>
		<div class="body textual">Content 2025</div>
	`), 0644)

	err := ProcessPrefix("IM", tmpDir, tmpDir, true)
	if err != nil {
		t.Fatalf("ProcessPrefix with byYear=true failed: %v", err)
	}

	// Check output - should be two files
	files2024, _ := filepath.Glob(filepath.Join(tmpDir, "IM_Transcripts_2024_1_1.md"))
	files2025, _ := filepath.Glob(filepath.Join(tmpDir, "IM_Transcripts_2025_2_2.md"))
	
	if len(files2024) != 1 {
		t.Errorf("Expected 2024 output file, found %d", len(files2024))
	}
	if len(files2025) != 1 {
		t.Errorf("Expected 2025 output file, found %d", len(files2025))
	}
}
