import os
import re
import glob
import argparse
import datetime
import concurrent.futures
import multiprocessing

# Configuration
DATA_DIR = os.path.join(os.getcwd(), "data")
OUTPUT_BASE = DATA_DIR # Save outputs in the same data folder

# NotebookLM Limits (as of early 2026)
# Word Limit: 500,000 words per source
# File Size Limit: 200MB per file
# We use slightly lower operational limits to ensure compatibility and account for overhead.
MAX_WORDS = 250000
MAX_BYTES = 100 * 1024 * 1024 # 100 MB

# Pre-compiled Regular Expressions for performance
YEAR_RE = re.compile(r'(\d{4})')
EP_NUM_RE = re.compile(r'_(\d+)\.html')
PREFIX_RE = re.compile(r'([A-Z0-9]+)_\d+\.html')

# Pattern 5: Speaker Name: (no timestamp, for older transcripts)
# Matches lines like "Leo Laporte: ...", "Jeff Jarvis: ..."
# Also handles markdown bold/italic: "**Leo Laporte:** ...", "*Leo Laporte:* ..."
SPEAKER_NAME_RE = re.compile(r"^\*{0,2}([A-Z][a-zA-Z'.\-]+(?:\s+[A-Z][a-zA-Z'.\-]+)*)\*{0,2}\s*:\s*\*{0,2}\s*(.*)")


# Episode number from title (e.g. "This Week in Tech 638 Transcript")
TITLE_EP_RE = re.compile(r'(\d+)\s*(?:\(|$|[Tt]ranscript)')

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

# Map of Show Title Segments to File Prefixes
# Same as in fetch_transcripts.py for consistency
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
        "%B %d, %Y",     # May 21, 2025
        "%b %d, %Y"      # Mar 28, 2008
    ]
    
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(clean_date, fmt)
            return dt.strftime("%y-%m-%d")
        except ValueError:
            continue
            
    return "00-01-01" # Fallback

def extract_ep_from_title(title):
    """
    Extracts an episode number from the HTML title text.
    Handles formats like:
      - 'This Week in Tech 638 Transcript'
      - 'Security Now 1000 transcript'
      - 'This Week in Google 233 (Transcript)'
    """
    if not title:
        return 0
    match = TITLE_EP_RE.search(title)
    return int(match.group(1)) if match else 0

def html_to_markdown(html_content, ep_num=0, date_ymd="00-01-01"):
    if not html_content:
        return ""
    
    # --- Surgical Noise Cleaning ---
    # Strip tags that don't add structure or formatting (span, font, o:p, st1, etc.)
    text = SCRIPT_STYLE_RE.sub('', html_content)
    text = re.sub(r'</?(?:span|font|o:p|body|html|head|meta|link|style|script|center|st1:[^>]+|shape|path|imagedata|v:[^>]+)[^>]*>', '', text, flags=re.IGNORECASE)
    
    # Remove AI-generated disclaimer
    disclaimer_pattern = r'\*?Please be advised this transcript is AI-generated.*?(?:ad-supported version of the show|approximate times|word for word)\.?\*?'
    text = re.sub(disclaimer_pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
    
    
    # --- Formatting Tags ---
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
        if url.startswith('/') or url.startswith('http://') or url.startswith('https://'):
            return f" [{content}]({url}) "
        return f" {content} "

    # --- Structural Tag Preservation ---
    # Convert major break tags into markers. These handle the paragraph boundaries.
    text = re.sub(r'</?(?:p|br|div|tr|table|ul|ol|li|h1|h2|h3)[^>]*>', '__PARA__', text, flags=re.IGNORECASE)
    
    # Links
    text = A_RE.sub(sanitize_link, text)
    
    # Strip ALL other remaining tags - including things like <o:p>, <span>, <body>, etc.
    text = TAG_RE.sub(' ', text)
    
    # Normalize entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    
    # --- HERE IS THE FIX ---
    # Instead of collapsing EVERYTHING to a single line (monoblock),
    # we convert paragraph markers to newlines, AND preserve literal newlines as blocks.
    text = text.replace('__PARA__', '\n')
    
    # Now split the condensed string by newlines
    blocks = text.split('\n')
    
    lines = []
    for block in blocks:
        stripped = block.strip()
        if stripped:
            lines.append(stripped)

    # --- Context-Tracking Pass ---
    final_lines = []
    current_timestamp = None
    current_speaker = None
    buffer = []
    current_prefix = None

    def flush_buffer():
        if buffer:
            content = " ".join(buffer)
            # Normalize internal whitespace in the buffered content
            content = re.sub(r'\s+', ' ', content).strip()
            if content:
                final_lines.append(f"{current_prefix} - {content}")
            buffer.clear()

    # Pre-compiled list of metadata regexes for clarity and performance
    METADATA_REGEXES = [
        re.compile(r'^(\d+:\d+(?::\d+)?)\s*(?:-\s*)?([^:]+)(?::\s*(.*))?'), # Pattern 1: Timestamp - Speaker: Content
        re.compile(r'^(.+?)\s*\[(\d+:\d+(?::\d+)?)\s*\]\s*:?\s*(.*)'),      # Pattern 2: Speaker [Timestamp]: Content
        re.compile(r'^(.+?)\s*\(\s*(\d+:\d+(?::\d+)?)\s*\)\s*:?\s*(.*)'),  # Pattern 3: Speaker (Timestamp): Content
        re.compile(r'^\(\s*(\d+:\d+(?::\d+)?)\s*\)\s*:?\s*(.*)'),          # Pattern 4: (Timestamp): Content
        SPEAKER_NAME_RE                                                  # Pattern 5: Speaker: Content
    ]

    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        found_new_metadata = False
        content = line

        # Try matching each pattern
        for i, regex in enumerate(METADATA_REGEXES):
            match = regex.match(line)
            if match:
                found_new_metadata = True
                if i == 0: # Pattern 1
                    if line[0].isdigit():
                        current_timestamp = match.group(1)
                        potential_speaker = match.group(2).strip()
                        if len(potential_speaker) < 40 and not any(c in potential_speaker for c in '.!?'):
                            current_speaker = potential_speaker
                            content = (match.group(3) or "").strip()
                        else:
                            content = potential_speaker + (f": {match.group(3)}" if match.group(3) else "")
                elif i == 1: # Pattern 2
                    current_speaker = match.group(1).strip()
                    current_timestamp = match.group(2).strip()
                    content = match.group(3).strip()
                elif i == 2: # Pattern 3
                    current_speaker = match.group(1).strip()
                    current_timestamp = match.group(2).strip()
                    content = match.group(3).strip()
                elif i == 3: # Pattern 4
                    current_timestamp = match.group(1).strip()
                    content = match.group(2).strip()
                elif i == 4: # Pattern 5
                    current_speaker = match.group(1).strip()
                    content = match.group(2).strip()
                break # Found a match

        if found_new_metadata and content.startswith(':'):
            content = content.lstrip(':').strip()
        
        # Build current meta-prefix
        prefix_parts = [f"EP:{ep_num}", f"Date:{date_ymd}"]
        if current_timestamp:
            prefix_parts.append(f"TS:{current_timestamp}")
        
        prefix = " ".join(prefix_parts)
        if current_speaker:
            prefix += f" - {current_speaker}"
        else:
            prefix += " -"

        if found_new_metadata:
            flush_buffer()
            current_prefix = prefix
            if content:
                buffer.append(content)
        else:
            if current_prefix is None:
                current_prefix = prefix
            buffer.append(line)

    flush_buffer()
    # Join with double newlines for clear paragraph separation in Markdown
    return "\n\n".join(final_lines)

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
    
    # Fallback: extract episode number from title if filename-based extraction returned 0
    if ep_num == 0:
        ep_num = extract_ep_from_title(title)
    
    # If CONTENT_RE failed (e.g. missing </div> in malformed legacy pages), 
    # use the "Transcript of Episode" marker as a start point.
    if content_match:
        raw_content = content_match.group(1)
    else:
        marker = "Transcript of Episode"
        idx = html.find(marker)
        if idx >= 0:
            raw_content = html[idx:]
        else:
            raw_content = html # Fallback to full HTML if marker not found
            
    ymd_date = parse_date_ymd(date_str)
    md_content = html_to_markdown(raw_content, ep_num=ep_num, date_ymd=ymd_date)
    
    return title, date_str, year, md_content

def get_ep_num(fname):
    # Matches {PREFIX}_{NUM}.html
    match = EP_NUM_RE.search(fname)
    return int(match.group(1)) if match else 0

def _parse_single_file(filepath):
    """
    Helper function for ProcessPoolExecutor.
    Parses a single transcript file and returns the result.
    """
    try:
        ep_num = get_ep_num(filepath)
        title, date_str, year, content = parse_transcript_file(filepath, ep_num=ep_num)
        return {
            'ep_num': ep_num,
            'title': title,
            'date_str': date_str,
            'year': year,
            'content': content,
            'filepath': filepath
        }
    except Exception as e:
        return {'error': str(e), 'filepath': filepath}

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
    
    cpu_count = multiprocessing.cpu_count()
    max_workers = max(1, cpu_count - 1)
    print(f"Processing {len(files)} files for {prefix} (By Year: {by_year}) using {max_workers} workers...")
    
    parsed_results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Map file parsing across processes
        results = list(executor.map(_parse_single_file, files))
        
        for res in results:
            if 'error' in res:
                print(f"Error processing file {res['filepath']}: {res['error']}. Skipping.")
            else:
                parsed_results.append(res)

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
    
    for res in parsed_results:
        ep_num = res['ep_num']
        title = res['title']
        date_str = res['date_str']
        year = res['year']
        content = res['content']
        
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
            
    # Write the final remaining chunk
    write_current_chunk()

def main():
    parser = argparse.ArgumentParser(
        description="Process downloaded transcripts into NotebookLM-ready Markdown files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python process_transcripts.py TWIT SN           # Process TWiT and Security Now
  python process_transcripts.py --by-year TWIT    # Process TWiT and split by year
  python process_transcripts.py --all             # Process all downloaded files
  python process_transcripts.py "Windows Weekly"  # Process by full show name
        """
    )
    parser.add_argument("shows", nargs="*", help="List of show codes or names to process (e.g. TWIT SN)")
    parser.add_argument("--all", action="store_true", help="Process ALL prefixes found in the data directory")
    parser.add_argument("--by-year", action="store_true", help="Break files up by year as well as size limits")
    
    args = parser.parse_args()
    
    prefixes_to_process = set()
    
    if args.all:
        # Scan directory for all unique prefixes
        all_files = glob.glob(os.path.join(DATA_DIR, "*_*.html"))
        for f in all_files:
            basename = os.path.basename(f)
            match = PREFIX_RE.match(basename)
            if match:
                prefixes_to_process.add(match.group(1))
    elif args.shows:
        for show_arg in args.shows:
            show_arg_clean = show_arg.strip().lower()
            
            # Check if it matches a prefix (value)
            if show_arg.upper() in SHOW_MAP.values():
                prefixes_to_process.add(show_arg.upper())
                continue
                
            # Check if it matches a show name (key)
            if show_arg_clean in SHOW_MAP:
                prefixes_to_process.add(SHOW_MAP[show_arg_clean])
                continue
                
            # If not in SHOW_MAP, it might be an ad-hoc prefix
            prefixes_to_process.add(show_arg.upper())
    else:
        print("No shows specified. Defaulting to IM and TWIG.")
        prefixes_to_process = {"IM", "TWIG"}
        
    for prefix in sorted(prefixes_to_process):
        process_prefix(prefix, by_year=args.by_year)

if __name__ == "__main__":
    main()
