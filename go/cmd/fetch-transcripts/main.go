package main

import (
	"flag"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/aramova/twit-transcript-archiver/go/internal/config"
	"github.com/aramova/twit-transcript-archiver/go/internal/scraper"
	"github.com/aramova/twit-transcript-archiver/go/internal/utils"
)

func main() {
	allPtr := flag.Bool("all", false, "Download transcripts for ALL known shows")
	pagesPtr := flag.Int("pages", 200, "Number of pages to scan")
	refreshPtr := flag.Bool("refresh-list", false, "Force re-download of list pages")
	throttlePtr := flag.Duration("throttle", 1*time.Second, "Duration to wait between requests (e.g. 1s, 500ms)")
	noThrottlePtr := flag.Bool("no-throttle", false, "Disable throttling")
	// "shows" flag is harder in Go flag package as it doesn't support nargs easily without a custom Value
	// We'll treat remaining args as shows if --all is not set

	flag.Parse()

	dataDir := config.GetDataDir()
	if err := utils.EnsureDir(dataDir); err != nil {
		fmt.Printf("Error creating data dir: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("Using data directory: %s\n", dataDir)

	throttle := *throttlePtr
	if *noThrottlePtr {
		throttle = 0
	}
	if throttle > 0 {
		fmt.Printf("Throttling enabled: %v delay\n", throttle)
	} else {
		fmt.Println("Throttling disabled.")
	}

	targetPrefixes := make(map[string]bool)

	if *allPtr {
		for _, prefix := range config.ShowMap {
			targetPrefixes[prefix] = true
		}
	} else {
		args := flag.Args()
		if len(args) == 0 {
			fmt.Println("No shows specified. Defaulting to IM and TWIG.")
			targetPrefixes["IM"] = true
			targetPrefixes["TWIG"] = true
		} else {
			for _, arg := range args {
				argClean := strings.ToLower(strings.TrimSpace(arg))
				found := false

				// Check values (prefixes)
				for _, p := range config.ShowMap {
					if p == strings.ToUpper(argClean) {
						targetPrefixes[p] = true
						found = true
						break
					}
				}
				if found {
					continue
				}

				// Check keys (names)
				if prefix, ok := config.ShowMap[argClean]; ok {
					targetPrefixes[prefix] = true
					found = true
				}

				if !found {
					fmt.Printf("Warning: Unknown show '%s'\n", arg)
				}
			}
		}
	}

	var shows []string
	for p := range targetPrefixes {
		shows = append(shows, p)
	}
	fmt.Printf("Targeting Shows: %v\n", shows)

	stats := struct {
		PagesScanned          int
		PagesDownloaded       int
		PagesCached           int
		TranscriptsFound      int
		TranscriptsDownloaded int
		TranscriptsSkipped    int
		TranscriptsIgnored    int
	}{}

	// Main Loop
	for pageNum := 1; pageNum <= *pagesPtr; pageNum++ {
		stats.PagesScanned++
		fmt.Printf("--- Processing Page %d ---\n", pageNum)

		html, cached, err := scraper.GetListPageWithCacheStatus(pageNum, dataDir, *refreshPtr, throttle)
		if err != nil {
			fmt.Printf("Failed to get content for page %d: %v. Stopping.\n", pageNum, err)
			break
		}
		if cached {
			stats.PagesCached++
		} else {
			stats.PagesDownloaded++
		}

		items := scraper.ExtractItems(html)
		if len(items) == 0 {
			fmt.Printf("No items found on page %d. Stopping.\n", pageNum)
			break
		}

		fmt.Printf("Found %d items on page %d.\n", len(items), pageNum)

		for _, item := range items {
			stats.TranscriptsFound++
			titleLower := strings.ToLower(item.Title)
			var matchedPrefix string

			for name, prefix := range config.ShowMap {
				if strings.Contains(titleLower, name) {
					matchedPrefix = prefix
					break
				}
			}

			if matchedPrefix != "" {
				if targetPrefixes[matchedPrefix] {
					skipped, err := scraper.DownloadTranscriptWithStatus(item.URL, item.Title, matchedPrefix, dataDir, throttle)
					if err != nil {
						fmt.Printf("Error downloading %s: %v\n", item.Title, err)
					} else if skipped {
						stats.TranscriptsSkipped++
					} else {
						stats.TranscriptsDownloaded++
					}
				} else {
					// fmt.Printf("  [IGNORE] %s\n", item.Title)
					stats.TranscriptsIgnored++
				}
			} else {
				stats.TranscriptsIgnored++
			}
		}
	}

	fmt.Println("\n========================================")
	fmt.Println("           CRAWL SUMMARY")
	fmt.Println("========================================")
	fmt.Printf("Pages Scanned:       %d\n", stats.PagesScanned)
	fmt.Printf("  - Downloaded:      %d\n", stats.PagesDownloaded)
	fmt.Printf("  - Cached:          %d\n", stats.PagesCached)
	fmt.Printf("Transcripts Found:   %d\n", stats.TranscriptsFound)
	fmt.Printf("  - Downloaded:      %d\n", stats.TranscriptsDownloaded)
	fmt.Printf("  - Skipped (Exist): %d\n", stats.TranscriptsSkipped)
	fmt.Printf("  - Ignored (Type):  %d\n", stats.TranscriptsIgnored)
	fmt.Println("========================================")
}
