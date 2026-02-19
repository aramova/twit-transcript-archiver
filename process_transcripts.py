import os
import re
import glob
import argparse

# Configuration
DATA_DIR = os.path.join(os.getcwd(), "data")
OUTPUT_BASE = DATA_DIR # Save outputs in the same data folder

# NotebookLM Limits (as of early 2026)
# Word Limit: 500,000 words per source
# File Size Limit: 200MB per file
# We use slightly lower operational limits to ensure compatibility and account for overhead.
MAX_WORDS = 490000
MAX_BYTES = 190 * 1024 * 1024 # 190 MB

def extract_year(date_str):
    """
    Extracts a 4-digit year from a date string using regex.
    Common formats: 'Wednesday, February 18, 2026' or 'Jan 1st 2025'
    """
    match = re.search(r'(\d{4})', date_str)
    return int(match.group(1)) if match else 0

def html_to_markdown(html_content):
    if not html_content:
        return ""
    
    text = re.sub(r'<(script|style).*?</\1>', '', html_content, flags=re.DOTALL)
    text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n\n', text, flags=re.DOTALL)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n\n', text, flags=re.DOTALL)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n\n', text, flags=re.DOTALL)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<(b|strong)[^>]*>(.*?)</\1>', r'**\2**', text, flags=re.DOTALL)
    text = re.sub(r'<(i|em)[^>]*>(.*?)</\1>', r'*\2*', text, flags=re.DOTALL)
    # 7. Convert Links (Sanitized)
    # [text](url)
    def sanitize_link(match):
        url = match.group(1)
        content = match.group(2)
        # Security: Only allow http(s) or relative paths to prevent javascript: XSS
        if url.startswith('/') or url.startswith('http://') or url.startswith('https://'):
            return f"[{content}]({url})"
        return content # Drop the link, keep the text

    text = re.sub(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>', sanitize_link, text, flags=re.DOTALL)
    text = re.sub(r'<ul[^>]*>', '', text)
    text = re.sub(r'</ul>', '\n', text)
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'* \1\n', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    
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
            
    return "\n".join(lines).strip()

def parse_transcript_file(filepath):
    """
    Parses a single HTML transcript file to extract metadata and clean content.
    Returns: (title, date_str, year, md_content)
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
        
    title_match = re.search(r'<h1 class="post-title">(.*?)</h1>', html)
    date_match = re.search(r'<p class="byline">(.*?)</p>', html, re.DOTALL)
    content_match = re.search(r'<div class="body textual">(.*?)</div>', html, re.DOTALL)
    
    title = title_match.group(1).strip() if title_match else "Unknown Episode"
    date_str = date_match.group(1).strip() if date_match else "Unknown Date"
    date_str = re.sub(r'\s+', ' ', date_str)
    year = extract_year(date_str)
    
    raw_content = content_match.group(1) if content_match else ""
    md_content = html_to_markdown(raw_content)
    
    return title, date_str, year, md_content

def get_ep_num(fname):
    # Matches {PREFIX}_{NUM}.html
    match = re.search(r'_(\d+)\.html', fname)
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
            title, date_str, year, content = parse_transcript_file(filepath)
            
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
            match = re.match(r'([A-Z0-9]+)_\d+\.html', basename)
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
