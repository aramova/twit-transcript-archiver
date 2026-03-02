import os
import re
import urllib.request
import time
import argparse
import sys

# Configuration
DATA_DIR = os.path.join(os.getcwd(), "data")
BASE_LIST_URL = "https://twit.tv/posts/transcripts"
BASE_SITE_URL = "https://twit.tv"
GRC_SN_BASE_URL = "https://www.grc.com/sn/sn-{ep}.htm"  # GRC.com Security Now transcripts
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Map of Show Title Segments to File Prefixes
# Use lowercase keys for easier matching
SHOW_MAP = {
    "intelligent machines": "IM",
    "this week in google": "TWIG",
    "windows weekly": "WW",
    "macbreak weekly": "MBW",
    "this week in tech": "TWIT",
    "security now": "SN",
    "this week in space": "TWIS",
    "tech news weekly": "TNW",
    "untitled linux show": "ULS",
    "hands-on tech": "HOT",
    "hands-on windows": "HOW",
    "hands-on apple": "HOA",
    "know how": "KH",
    "before you buy": "BYB",
    "ios today": "IOS",
    "all about android": "AAA",
    "floss weekly": "FLOSS",
    "ham nation": "HAM"
}

def setup_directories():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created data directory at: {DATA_DIR}")

def get_list_page(page_num):
    filename = os.path.join(DATA_DIR, f"transcripts_page_{page_num}.html")
    
    # Always try to download fresh list pages for the first few pages to catch new episodes
    # But cache older pages to speed up deep archives
    if page_num > 5 and os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
            
    url = BASE_LIST_URL
    if page_num > 1:
        url += f"?page={page_num}"
        
    print(f"Downloading list page {page_num}: {url}")
    retries = 3
    while retries > 0:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req) as response:
                content = response.read().decode('utf-8')
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                return content
        except Exception as e:
            print(f"Error downloading list page {page_num}: {e}. Retrying...")
            retries -= 1
            time.sleep(2)
            
    return None

def download_transcript_detail(url_path, title, prefix, throttle_time=1.0):
    # Extract episode number
    # Look for number typically at the end or before "transcript"
    ep_num_match = re.search(r'(\d+)', title)
    ep_num = ep_num_match.group(1) if ep_num_match else "unknown"
    
    # Special handling if multiple episodes have same number (rare but possible across shows? no, prefix handles that)
    filename = os.path.join(DATA_DIR, f"{prefix}_{ep_num}.html")
    
    if os.path.exists(filename):
        # We could add a verbose flag check here
        # print(f"Skipping existing: {filename}")
        return
        
    full_url = BASE_SITE_URL + url_path
    print(f"Downloading {prefix} {ep_num}: {title}")
    
    retries = 3
    while retries > 0:
        try:
            req = urllib.request.Request(full_url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req) as response:
                content = response.read().decode('utf-8')
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                if throttle_time > 0:
                    time.sleep(throttle_time)
                return
        except Exception as e:
            print(f"Error downloading {full_url}: {e}. Retrying...")
            retries -= 1
            time.sleep(2)

def fetch_grc_sn_transcripts(start_ep, end_ep, throttle_time=1.0):
    """
    Fetch Security Now transcripts from GRC.com.
    URL pattern: https://www.grc.com/sn/sn-{NNN}.htm
    Episodes < 1000 use 3-digit zero-padded numbers, >= 1000 use the raw number.
    
    GRC pages are full HTML pages with table layouts and <b>Speaker:</b> formatting.
    We extract the <body> content and date, then wrap in our standard HTML format.
    """
    print(f"\nFetching Security Now transcripts from GRC.com (episodes {start_ep}-{end_ep})...")
    
    # Regex to extract the date from GRC transcript text
    # GRC embeds dates like "recorded Tuesday, March 24, 2015" in the transcript
    grc_date_re = re.compile(
        r'recorded\s+\w+day,?\s+((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+,?\s+\d{4})',
        re.IGNORECASE
    )
    # Fallback: only match valid month names to avoid false positives from boilerplate
    valid_months = r'(?:January|February|March|April|May|June|July|August|September|October|November|December)'
    grc_date_fallback_re = re.compile(
        rf'Episode\s*#?\d+.*?({valid_months}\s+\d{{1,2}},?\s+\d{{4}})',
        re.IGNORECASE | re.DOTALL
    )
    
    # Extract body content between <body> and </body>
    grc_body_re = re.compile(r'<body[^>]*>(.*?)</body>', re.DOTALL | re.IGNORECASE)
    
    stats = {"downloaded": 0, "skipped": 0, "failed": 0}
    
    for ep in range(start_ep, end_ep + 1):
        filename = os.path.join(DATA_DIR, f"SN_{ep}.html")
        
        if os.path.exists(filename):
            stats["skipped"] += 1
            continue
        
        # Format episode number: zero-pad to 3 digits for < 1000
        ep_str = str(ep).zfill(3) if ep < 1000 else str(ep)
        
        url = GRC_SN_BASE_URL.format(ep=ep_str)
        print(f"GRC: Downloading SN {ep}: {url}")
        
        retries = 3
        while retries > 0:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
                with urllib.request.urlopen(req) as response:
                    raw_html = response.read().decode('utf-8', errors='replace')
                
                # Extract date from transcript text
                date_str = "Unknown Date"
                date_match = grc_date_re.search(raw_html)
                if date_match:
                    date_str = date_match.group(1).strip()
                else:
                    date_match = grc_date_fallback_re.search(raw_html)
                    if date_match:
                        date_str = date_match.group(1).strip()
                
                # Extract body content
                body_match = grc_body_re.search(raw_html)
                body_content = body_match.group(1).strip() if body_match else raw_html
                
                # Strip </div> tags from body so CONTENT_RE's lazy (.*?)</div> captures everything
                body_content = body_content.replace('</div>', '')
                
                # Wrap in our standard format so process_transcripts.py can handle it
                wrapped_html = (
                    f'<h1 class="post-title">Security Now {ep} Transcript</h1>\n'
                    f'<p class="byline">{date_str}</p>\n'
                    f'<div class="body textual">{body_content}</div>\n'
                )
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(wrapped_html)
                
                stats["downloaded"] += 1
                
                if throttle_time > 0:
                    time.sleep(throttle_time)
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    print(f"  SN {ep}: Not found on GRC.com (404). Skipping.")
                    stats["failed"] += 1
                    break
                print(f"  Error downloading SN {ep} from GRC: {e}. Retrying...")
                retries -= 1
                time.sleep(2)
            except Exception as e:
                print(f"  Error downloading SN {ep} from GRC: {e}. Retrying...")
                retries -= 1
                time.sleep(2)
        
        if retries == 0:
            stats["failed"] += 1
    
    print(f"\nGRC.com SN Results: Downloaded={stats['downloaded']}, Skipped={stats['skipped']}, Failed={stats['failed']}")
    return stats

def extract_items(html):
    # Looking for <div class="item summary"> ... <h2 class="title"><a href="...">Title</a></h2>
    item_pattern = re.compile(r'<div class="item summary">.*?<h2 class="title"><a href="([^"]+)">([^<]+)</a></h2>', re.DOTALL)
    items = []
    matches = item_pattern.findall(html)
    for href, title in matches:
        items.append({
            'url': href,
            'title': title.strip()
        })
    return items

def get_target_prefixes(args):
    targets = set()
    
    if args.all:
        return set(SHOW_MAP.values())
        
    if args.shows:
        for show_arg in args.shows:
            show_arg_clean = show_arg.strip().lower()
            
            # Check if it matches a prefix (value)
            if show_arg.upper() in SHOW_MAP.values():
                targets.add(show_arg.upper())
                continue
                
            # Check if it matches a show name (key)
            if show_arg_clean in SHOW_MAP:
                targets.add(SHOW_MAP[show_arg_clean])
                continue
                
            print(f"Warning: Unknown show '{show_arg}'. Available codes: {', '.join(sorted(SHOW_MAP.values()))}")
    
    # If no specific shows args, default to IM and TWIG for backward compatibility/default behavior
    if not targets and not args.all:
        print("No shows specified. Defaulting to IM and TWIG.")
        targets.add("IM")
        targets.add("TWIG")
        
    return targets

def main():
    parser = argparse.ArgumentParser(
        description="Fetch transcripts from TWiT.tv",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fetch_transcripts.py TWIT SN           # Download TWiT and Security Now
  python fetch_transcripts.py "Windows Weekly"  # Download by full show name
  python fetch_transcripts.py --all             # Download everything (takes a long time)
  python fetch_transcripts.py --pages 5 TWIT    # Only scan first 5 pages for TWIT
        """
    )
    parser.add_argument("shows", nargs="*", help="List of show codes or names to download (e.g. TWIT SN)")
    parser.add_argument("--all", action="store_true", help="Download transcripts for ALL known shows")
    parser.add_argument("--pages", type=int, default=200, help="Number of pages to scan (default 200)")
    parser.add_argument("--refresh-list", action="store_true", help="Force re-download of list pages")
    parser.add_argument("--throttle", type=float, default=1.0, help="Seconds to wait between requests (default 1.0)")
    parser.add_argument("--no-throttle", action="store_true", help="Disable throttling")
    parser.add_argument("--grc-sn-range", type=str, default=None,
                        help="Fetch SN transcripts from GRC.com for given episode range (e.g. '1-1066')")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    
    args = parser.parse_args()
    
    def debug_log(msg):
        if args.debug:
            print(f"[DEBUG] {msg}")

    setup_directories()
    target_prefixes = get_target_prefixes(args)
    throttle_time = 0.0 if args.no_throttle else args.throttle
    print(f"Targeting Shows: {', '.join(sorted(target_prefixes))}")
    if throttle_time > 0:
        print(f"Throttling enabled: {throttle_time}s delay")
    else:
        print("Throttling disabled.")
    
    stats = {
        "pages_scanned": 0,
        "pages_downloaded": 0,
        "pages_cached": 0,
        "transcripts_found": 0,
        "transcripts_downloaded": 0,
        "transcripts_skipped": 0,
        "transcripts_ignored": 0
    }

    page_num = 1
    scanning = True
    
    while scanning and page_num <= args.pages:
        stats["pages_scanned"] += 1
        debug_log(f"--- Processing Page {page_num} ---")
        
        filename = os.path.join(DATA_DIR, f"transcripts_page_{page_num}.html")
        page_content = None
        
        # Logic: Determine if we should download or use cache
        should_download = True
        if not args.refresh_list:
            if os.path.exists(filename):
                # We have a local file.
                # However, for the first few pages (e.g. 1-5), we might want to refresh to catch NEW episodes
                # unless explicitly told not to.
                # But for deep archives (page > 5), cache is fine.
                if page_num > 5:
                    should_download = False
                    debug_log(f"Page {page_num} > 5 and exists locally. Using cache.")
                else:
                    debug_log(f"Page {page_num} exists locally but is recent. Re-downloading to check for updates.")
            else:
                debug_log(f"Page {page_num} does not exist locally. Downloading.")
        else:
            debug_log(f"Refresh forced. Downloading Page {page_num}.")

        if should_download:
            url = BASE_LIST_URL
            if page_num > 1:
                url += f"?page={page_num}"
            
            print(f"Downloading list page {page_num}: {url}")
            retries = 3
            while retries > 0:
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
                    with urllib.request.urlopen(req) as response:
                        page_content = response.read().decode('utf-8')
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(page_content)
                        if throttle_time > 0:
                            time.sleep(throttle_time)
                        stats["pages_downloaded"] += 1
                        break
                except Exception as e:
                    print(f"Error downloading list page {page_num}: {e}. Retrying...")
                    retries -= 1
                    time.sleep(2)
        else:
            # Use cached
            stats["pages_cached"] += 1
            with open(filename, 'r', encoding='utf-8') as f:
                page_content = f.read()

        if not page_content:
            debug_log(f"Failed to get content for page {page_num}. Stopping.")
            break
            
        items = extract_items(page_content)
        if not items:
            print(f"No items found on page {page_num}. Stopping.")
            break
        
        debug_log(f"Found {len(items)} items on page {page_num}.")
        
        for item in items:
            title_lower = item['title'].lower()
            stats["transcripts_found"] += 1
            
            # Find match
            matched_prefix = None
            for show_name, prefix in SHOW_MAP.items():
                if show_name in title_lower:
                    matched_prefix = prefix
                    break
            
            if matched_prefix:
                if matched_prefix in target_prefixes:
                    # Check if file exists
                    ep_num_match = re.search(r'(\d+)', item['title'])
                    ep_num = ep_num_match.group(1) if ep_num_match else "unknown"
                    dest_file = os.path.join(DATA_DIR, f"{matched_prefix}_{ep_num}.html")
                    
                    if os.path.exists(dest_file):
                        debug_log(f"  [SKIP] {item['title']} ({matched_prefix}) - Already downloaded.")
                        stats["transcripts_skipped"] += 1
                    else:
                        debug_log(f"  [DOWNLOAD] {item['title']} ({matched_prefix}) - Downloading...")
                        download_transcript_detail(item['url'], item['title'], matched_prefix, throttle_time=throttle_time)
                        stats["transcripts_downloaded"] += 1
                else:
                    debug_log(f"  [IGNORE] {item['title']} ({matched_prefix}) - Not in target list.")
                    stats["transcripts_ignored"] += 1
            else:
                # debug_log(f"  [UNKNOWN] {item['title']} - No matching show found.")
                pass
        
        page_num += 1

    print("\n" + "="*40)
    print("           CRAWL SUMMARY")
    print("="*40)
    print(f"Pages Scanned:       {stats['pages_scanned']}")
    print(f"  - Downloaded:      {stats['pages_downloaded']}")
    print(f"  - Cached:          {stats['pages_cached']}")
    print(f"Transcripts Found:   {stats['transcripts_found']}")
    print(f"  - Downloaded:      {stats['transcripts_downloaded']}")
    print(f"  - Skipped (Exist): {stats['transcripts_skipped']}")
    print(f"  - Ignored (Type):  {stats['transcripts_ignored']}")
    print("="*40)

    # --- GRC.com Security Now Fetch ---
    if args.grc_sn_range:
        try:
            parts = args.grc_sn_range.split('-')
            grc_start = int(parts[0])
            grc_end = int(parts[1])
            fetch_grc_sn_transcripts(grc_start, grc_end, throttle_time=throttle_time)
        except (ValueError, IndexError):
            print(f"Error: Invalid --grc-sn-range format '{args.grc_sn_range}'. Use 'START-END' (e.g. '1-1066').")
    elif "SN" in target_prefixes:
        # Auto-fetch from GRC.com for any SN episodes missing from twit.tv
        # Determine the highest known episode number from existing files
        import glob
        existing_sn = glob.glob(os.path.join(DATA_DIR, "SN_*.html"))
        max_ep = 0
        for f in existing_sn:
            m = re.search(r'SN_(\d+)\.html', f)
            if m:
                max_ep = max(max_ep, int(m.group(1)))
        if max_ep > 0:
            print(f"\nAuto-fetching missing SN transcripts from GRC.com (episodes 1-{max_ep})...")
            fetch_grc_sn_transcripts(1, max_ep, throttle_time=throttle_time)

if __name__ == "__main__":
    main()
