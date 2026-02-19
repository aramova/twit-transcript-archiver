package config

import (
	"os"
	"path/filepath"
	"regexp"
)

var (
	// Base URL for the transcript list
	BaseListURL = "https://twit.tv/posts/transcripts"
	// Base URL for the site
	BaseSiteURL = "https://twit.tv"

	// Data directory (relative to where the binary is run, usually project root)
	// We assume the user runs the binary from the project root or the 'go' folder.
	// We'll try to resolve it relative to the 'git' root if possible.
	// We'll try to resolve it relative to the 'git' root if possible.
	DataDir = "data"

	// PrefixRegex matches transcript filenames like IM_123.html or TWIG_05.html
	PrefixRegex = regexp.MustCompile(`([A-Z0-9]+)_\d+\.html`)
)

// ShowMap maps lowercase show title segments to file prefixes
var ShowMap = map[string]string{
	"intelligent machines": "IM",
	"this week in google":  "TWIG",
	"windows weekly":       "WW",
	"macbreak weekly":      "MBW",
	"this week in tech":    "TWIT",
	"security now":         "SN",
	"this week in space":   "TWIS",
	"tech news weekly":     "TNW",
	"untitled linux show":  "ULS",
	"hands-on tech":        "HOT",
	"hands-on windows":     "HOW",
	"hands-on apple":       "HOA",
	"know how":             "KH",
	"before you buy":       "BYB",
	"ios today":            "IOS",
	"all about android":    "AAA",
	"floss weekly":         "FLOSS",
	"ham nation":           "HAM",
}

// GetDataDir returns the absolute path to the data directory.
// It checks if "data" exists in current dir, otherwise checks "../data"
func GetDataDir() string {
	cwd, _ := os.Getwd()

	// Check current dir
	localData := filepath.Join(cwd, "data")
	if _, err := os.Stat(localData); err == nil {
		return localData
	}

	// Check parent dir (if running from git/go/)
	parentData := filepath.Join(filepath.Dir(cwd), "data")
	if _, err := os.Stat(parentData); err == nil {
		return parentData
	}

	// Check parent/parent (if running from git/go/cmd/...)
	ppData := filepath.Join(filepath.Dir(filepath.Dir(cwd)), "data")
	if _, err := os.Stat(ppData); err == nil {
		return ppData
	}

	// Default to local data dir even if it doesn't exist (caller will create)
	return localData
}
