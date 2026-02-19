import os
import re
import glob
import argparse
import datetime

# Configuration
DATA_DIR = os.path.join(os.getcwd(), "data")
OUTPUT_BASE = DATA_DIR # Save outputs in the same data folder

# NotebookLM Limits (as of early 2026)
# Word Limit: 500,000 words per source
# File Size Limit: 200MB per file
# We use slightly lower operational limits to ensure compatibility and account for overhead.
MAX_WORDS = 490000
MAX_BYTES = 190 * 1024 * 1024 # 190 MB

# Pre-compiled Regular Expressions for performance
YEAR_RE = re.compile(r'(\d{4})')
EP_NUM_RE = re.compile(r'_(\d+)\.html')
PREFIX_RE = re.compile(r'([A-Z0-9]+)_\d+\.html')

# Regexes for HTML parsing
SCRIPT_STYLE_RE = re.compile(r'<(script|style).*?</\1>', re.DOTALL)
H1_RE = re.compile(r'<h1[^>]*>(.*?)</h1>', re.DOTALL)
H2_RE = re.compile(r'<h2[^>]*>(.*?)</h2>', re.DOTALL)
H3_RE = re.compile(r'<h3[^>]*>(.*?)</h3>', re.DOTALL)
P_RE = re.compile(r'<p[^>]*>(.*?)</p>', re.DOTALL)
BR_RE = re.compile(r'<br\s*/?>')
BOLD_RE = re.compile(r'<(b|strong)[^>]*>(.*?)</\1>', re.DOTALL)
ITALIC_RE = re.compile(r'<(i|em)[^>]*>(.*?)</\1>', re.DOTALL)
A_RE = re.compile(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
UL_RE = re.compile(r'<ul[^>]*>')
UL_END_RE = re.compile(r'</ul>')
LI_RE = re.compile(r'<li[^>]*>(.*?)</li>', re.DOTALL)
TAG_RE = re.compile(r'<[^>]+>')
WHITESPACE_RE = re.compile(r'\s+')

# Regexes for metadata parsing
TITLE_RE = re.compile(r'<h1 class="post-title">(.*?)</h1>')
BYLINE_RE = re.compile(r'<p class="byline">(.*?)</p>', re.DOTALL)
CONTENT_RE = re.compile(r'<div class="body textual">(.*?)</div>', re.DOTALL)


def extract_year(date_str):
    """
    Extracts a 4-digit year from a date string using regex.
    Common formats: 'Wednesday, February 18, 2026' or 'Jan 1st 2025'
    """
    match = YEAR_RE.search(date_str)
    return int(match.group(1)) if match else 0

def parse_date_ymd(date_str):
    """
    Parses a date string into YY-MM-DD format.
    Handles ordinal suffixes (st, nd, rd, th).
    """
    if not date_str:
        return "00-01-01"

    # Remove ordinal suffixes
    clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
    
    # Common formats
    formats = [
        "%B %d %Y",      # May 21 2025
        "%b %d %Y",      # Feb 5 2025
        "%A, %B %d, %Y",  # Wednesday, February 18, 2026
        "%B %d, %Y"      # May 21, 2025
    ]
    
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(clean_date, fmt)
            return dt.strftime("%y-%m-%d")
        except ValueError:
            continue
            
    return "00-01-01" # Fallback

def html_to_markdown(html_content, ep_num=0, date_ymd="00-01-01"):
    if not html_content:
        return ""
    
    text = SCRIPT_STYLE_RE.sub('', html_content)
    text = H1_RE.sub(r'# \1\n\n', text)
    text = H2_RE.sub(r'## \1\n\n', text)
    text = H3_RE.sub(r'### \1\n\n', text)
    text = P_RE.sub(r'\1\n\n', text)
    text = BR_RE.sub('\n', text)
    text = BOLD_RE.sub(r'**\2**', text)
    text = ITALIC_RE.sub(r'*\2*', text)
    
    def sanitize_link(match):
        url = match.group(1)
        content = match.group(2)
        # Security: Only allow http(s) or relative paths to prevent javascript: XSS
        if url.startswith('/') or url.startswith('http://') or url.startswith('https://'):
            return f"[{content}]({url})"
        return content # Drop the link, keep the text

    text = A_RE.sub(sanitize_link, text)
    text = UL_RE.sub('', text)
    text = UL_END_RE.sub('\n', text)
    text = LI_RE.sub(r'* \1\n', text)
    text = TAG_RE.sub('', text)
    
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    
    lines = []
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
        elif not lines or lines[-1] != "":
            lines.append("")
            
    # --- Timestamp Standardization Pass ---
    final_lines = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            final_lines.append("")
            i += 1
            continue
            
        # Pattern 1: HH:MM:SS - Speaker (Standard)
        ts_match_p1 = re.match(r'^(\d+:\d+(?::\d+)?)\s*(?:-\s*)?(.*)', line)
        
        # Pattern 2: Speaker [HH:MM:SS]: (Secondary)
        ts_match_p2 = re.match(r'^(.+?)\s*\[(\d+:\d+(?::\d+)?)\]\s*:?\s*(.*)', line)
        
        # Pattern 3: Speaker (HH:MM:SS): (Discovered 2021-2023)
        ts_match_p3 = re.match(r'^(.+?)\s*\((\d+:\d+(?::\d+)?)\s*\)\s*:?\s*(.*)', line)

        # Pattern 4: (HH:MM:SS): (Discovered 2022)
        ts_match_p4 = re.match(r'^\((\d+:\d+(?::\d+)?)\)\s*:?\s*(.*)', line)

        timestamp = None
        speaker = None
        rest_of_line = ""

        if ts_match_p1 and line[0].isdigit():
            timestamp = ts_match_p1.group(1)
            rest_of_line = ts_match_p1.group(2).strip()
        elif ts_match_p2:
            speaker = ts_match_p2.group(1).strip()
            timestamp = ts_match_p2.group(2).strip()
            rest_of_line = ts_match_p2.group(3).strip()
            if rest_of_line.startswith(':'):
                rest_of_line = rest_of_line.lstrip(':').strip()
        elif ts_match_p3:
            speaker = ts_match_p3.group(1).strip()
            timestamp = ts_match_p3.group(2).strip()
            rest_of_line = ts_match_p3.group(3).strip()
            if rest_of_line.startswith(':'):
                rest_of_line = rest_of_line.lstrip(':').strip()
        elif ts_match_p4:
            timestamp = ts_match_p4.group(1).strip()
            rest_of_line = ts_match_p4.group(2).strip()
            if rest_of_line.startswith(':'):
                rest_of_line = rest_of_line.lstrip(':').strip()

        if timestamp:
            formatted_prefix = f"EP:{ep_num} Date:{date_ymd} TS:{timestamp} -"
            if speaker:
                formatted_prefix = f"EP:{ep_num} Date:{date_ymd} TS:{timestamp} - {speaker}"
            
            merged_text = rest_of_line
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                is_next_ts = (re.match(r'^\d+:\d+', next_line) or 
                              re.search(r'\[\d+:\d+\]', next_line) or 
                              re.match(r'^.+?\s*\(\d+:\d+', next_line) or
                              re.match(r'^\(\d+:\d+\)', next_line))
                if next_line and not is_next_ts:
                    if merged_text:
                        merged_text += " " + next_line
                    else:
                        merged_text = next_line
                    i += 1
            
            if merged_text:
                final_lines.append(f"{formatted_prefix} {merged_text}")
            else:
                final_lines.append(formatted_prefix)
        else:
            final_lines.append(line)
            
        i += 1

    return "\n".join(final_lines).strip()

def parse_transcript_file(filepath, ep_num=0):
    """
    Parses a single HTML transcript file to extract metadata and clean content.
    Returns: (title, date_str, year, md_content)
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
        
    title_match = TITLE_RE.search(html)
    date_match = BYLINE_RE.search(html)
    content_match = CONTENT_RE.search(html)
    
    title = title_match.group(1).strip() if title_match else "Unknown Episode"
    date_str = date_match.group(1).strip() if date_match else "Unknown Date"
    date_str = WHITESPACE_RE.sub(' ', date_str)
    year = extract_year(date_str)
    
    raw_content = content_match.group(1) if content_match else ""
    ymd_date = parse_date_ymd(date_str)
    md_content = html_to_markdown(raw_content, ep_num=ep_num, date_ymd=ymd_date)
    
    return title, date_str, year, md_content

def get_ep_num(fname):
    # Matches {PREFIX}_{NUM}.html
    match = EP_NUM_RE.search(fname)
    return int(match.group(1)) if match else 0

def process_prefix(prefix, by_year=False):
    """
    Processes all HTML files for a given prefix, combining them into Markdown chunks.
    If by_year is True, chunks are also split when the calendar year changes.
    """
    # Find all files with this prefix: e.g. DATA_DIR/IM_*.html
    pattern = os.path.join(DATA_DIR, f"{prefix}_*.html")
    files = glob.glob(pattern)
    
    if not files:
        print(f"No files found for prefix: {prefix}")
        return

    # Ensure episodes are processed in chronological/numerical order
    files.sort(key=get_ep_num)
    
    print(f"Processing {len(files)} files for {prefix} (By Year: {by_year})...")
    
    current_word_count = 0
    current_byte_count = 0
    current_chunk_content = []
    chunk_start_ep = None
    chunk_end_ep = None
    current_year = None
    
    def write_current_chunk():
        nonlocal current_chunk_content, current_word_count, current_byte_count, chunk_start_ep, chunk_end_ep, current_year
        if not current_chunk_content:
            return
            
        # Filename Pattern:
        # By Year: {PREFIX}_Transcripts_{YEAR}_{START_EP}_{END_EP}.md
        # Default: {PREFIX}_Transcripts_{START_EP}-{END_EP}.md
        if by_year and current_year:
            output_name = f"{prefix}_Transcripts_{current_year}_{chunk_start_ep}_{chunk_end_ep}.md"
        else:
            output_name = f"{prefix}_Transcripts_{chunk_start_ep}-{chunk_end_ep}.md"
            
        output_filename = os.path.join(OUTPUT_BASE, output_name)
        with open(output_filename, 'w', encoding='utf-8') as out:
            out.writelines(current_chunk_content)
        print(f"Written {os.path.basename(output_filename)} (Words: {current_word_count}, Bytes: {current_byte_count})")
        
        # Reset counters for the next chunk
        current_chunk_content = []
        current_word_count = 0
        current_byte_count = 0
        chunk_start_ep = None
    
    for filepath in files:
        try:
            ep_num = get_ep_num(filepath)
            title, date_str, year, content = parse_transcript_file(filepath, ep_num=ep_num)
            
            # Metadata and content for the markdown file
            episode_header = f"# Episode: {title}\n**Date:** {date_str}\n\n"
            episode_body = f"{content}\n\n---\n\n"
            full_episode_text = episode_header + episode_body
            
            ep_words = len(content.split())
            ep_bytes = len(full_episode_text.encode('utf-8'))
            
            # Decision Logic for Splitting Chunks:
            # 1. Exceeds NotebookLM Word Limit
            # 2. Exceeds NotebookLM Byte Limit
            # 3. Year changes (if by_year flag is set)
            split_needed = False
            if (current_word_count + ep_words > MAX_WORDS) or (current_byte_count + ep_bytes > MAX_BYTES):
                split_needed = True
            elif by_year and current_year is not None and year != current_year:
                split_needed = True
            
            if split_needed:
                write_current_chunk()
                
            if chunk_start_ep is None:
                chunk_start_ep = ep_num
            
            current_chunk_content.append(full_episode_text)
            current_word_count += ep_words
            current_byte_count += ep_bytes
            chunk_end_ep = ep_num
            current_year = year
            
        except Exception as e:
            print(f"Error processing file {filepath}: {e}. Skipping.")
            continue
        
    # Write the final remaining chunk
    write_current_chunk()

def main():
    parser = argparse.ArgumentParser(description="Process downloaded transcripts into NotebookLM-ready Markdown files.")
    parser.add_argument("--prefixes", nargs="+", help="List of prefixes to process (e.g. IM TWIG)")
    parser.add_argument("--all", action="store_true", help="Process ALL prefixes found in the data directory")
    parser.add_argument("--by-year", action="store_true", help="Break files up by year as well as size limits")
    
    args = parser.parse_args()
    
    prefixes_to_process = set()
    
    if args.all:
        # Scan directory for all unique prefixes
        all_files = glob.glob(os.path.join(DATA_DIR, "*_*.html"))
        for f in all_files:
            basename = os.path.basename(f)
            # Assumption: Prefix is everything before the underscore and number
            # e.g. IM_847.html -> IM
            match = PREFIX_RE.match(basename)
            if match:
                prefixes_to_process.add(match.group(1))
    elif args.prefixes:
        prefixes_to_process = set(p.upper() for p in args.prefixes)
    else:
        print("No prefixes specified. Defaulting to IM and TWIG.")
        prefixes_to_process = {"IM", "TWIG"}
        
    for prefix in sorted(prefixes_to_process):
        process_prefix(prefix, by_year=args.by_year)

if __name__ == "__main__":
    main()
