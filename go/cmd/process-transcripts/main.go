package main

import (
	"flag"
	"fmt"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/aramova/twit-transcript-archiver/go/internal/config"
	"github.com/aramova/twit-transcript-archiver/go/internal/converter"
)

func main() {
	allPtr := flag.Bool("all", false, "Process ALL prefixes found in data directory")
	// prefixes via args
	
	flag.Parse()
	
dataDir := config.GetDataDir()
	
	prefixesToProcess := make(map[string]bool)
	
	if *allPtr {
		files, _ := filepath.Glob(filepath.Join(dataDir, "*_*.html"))
		re := regexp.MustCompile(`([A-Z]+)_\d+\.html`)
		for _, f := range files {
			base := filepath.Base(f)
			matches := re.FindStringSubmatch(base)
			if len(matches) > 1 {
				prefixesToProcess[matches[1]] = true
			}
		}
	} else {
		args := flag.Args()
		if len(args) == 0 {
			fmt.Println("No prefixes specified. Defaulting to IM and TWIG.")
			prefixesToProcess["IM"] = true
			prefixesToProcess["TWIG"] = true
		} else {
			for _, arg := range args {
				prefixesToProcess[strings.ToUpper(arg)] = true
			}
		}
	}
	
	for prefix := range prefixesToProcess {
		if err := converter.ProcessPrefix(prefix, dataDir, dataDir); err != nil {
			fmt.Printf("Error processing prefix %s: %v\n", prefix, err)
		}
	}
}
