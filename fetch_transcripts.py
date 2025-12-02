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
            with urllib.request.urlopen(url) as response:
                content = response.read().decode('utf-8')
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                time.sleep(1) 
                return content
        except Exception as e:
            print(f"Error downloading list page {page_num}: {e}. Retrying...")
            retries -= 1
            time.sleep(2)
            
    return None

def download_transcript_detail(url_path, title, prefix):
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
            with urllib.request.urlopen(full_url) as response:
                content = response.read().decode('utf-8')
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                time.sleep(1)
                return
        except Exception as e:
            print(f"Error downloading {full_url}: {e}. Retrying...")
            retries -= 1
            time.sleep(2)

def extract_items(html):
    # Looking for <div class="item summary"> ... <h2 class="title"><a href="...">Title</a></h2>
    item_pattern = re.compile(r'<div class="item summary">.*?<h2 class="title"><a href="([^"]+)">([^<]+)</a></h2>', re.DOTALL)
    items = []
    matches = item_pattern.findall(html)
    for href, title in matches:
        # Security: Ensure strict relative path to prevent SSRF/Open Redirects
        if not href.startswith('/'):
            # print(f"Warning: Skipping non-relative URL: {href}")
            continue
            
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
    parser = argparse.ArgumentParser(description="Fetch transcripts from TWiT.tv")
    parser.add_argument("--shows", nargs="+", help="List of show codes to download (e.g. IM TWIG WW SN)")
    parser.add_argument("--all", action="store_true", help="Download transcripts for ALL known shows")
    parser.add_argument("--pages", type=int, default=200, help="Number of pages to scan (default 200)")
    parser.add_argument("--refresh-list", action="store_true", help="Force re-download of list pages")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    
    args = parser.parse_args()
    
    def debug_log(msg):
        if args.debug:
            print(f"[DEBUG] {msg}")

    setup_directories()
    target_prefixes = get_target_prefixes(args)
    print(f"Targeting Shows: {', '.join(sorted(target_prefixes))}")
    
    page_num = 1
    scanning = True
    
    while scanning and page_num <= args.pages:
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
                    with urllib.request.urlopen(url) as response:
                        page_content = response.read().decode('utf-8')
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(page_content)
                        time.sleep(1)
                        break
                except Exception as e:
                    print(f"Error downloading list page {page_num}: {e}. Retrying...")
                    retries -= 1
                    time.sleep(2)
        else:
            # Use cached
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
                    else:
                        debug_log(f"  [DOWNLOAD] {item['title']} ({matched_prefix}) - Downloading...")
                        download_transcript_detail(item['url'], item['title'], matched_prefix)
                else:
                    debug_log(f"  [IGNORE] {item['title']} ({matched_prefix}) - Not in target list.")
            else:
                # debug_log(f"  [UNKNOWN] {item['title']} - No matching show found.")
                pass
        
        page_num += 1

if __name__ == "__main__":
    main()
