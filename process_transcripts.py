import os
import re
import glob
import argparse

# Configuration
DATA_DIR = os.path.join(os.getcwd(), "data")
OUTPUT_BASE = DATA_DIR # Save outputs in the same data folder
MAX_WORDS = 450000
MAX_BYTES = 180 * 1024 * 1024 # 180 MB

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
    text = re.sub(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL)
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
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
        
    title_match = re.search(r'<h1 class="post-title">(.*?)</h1>', html)
    date_match = re.search(r'<p class="byline">(.*?)</p>', html, re.DOTALL)
    content_match = re.search(r'<div class="body textual">(.*?)</div>', html, re.DOTALL)
    
    title = title_match.group(1).strip() if title_match else "Unknown Episode"
    date_str = date_match.group(1).strip() if date_match else "Unknown Date"
    date_str = re.sub(r'\s+', ' ', date_str)
    
    raw_content = content_match.group(1) if content_match else ""
    md_content = html_to_markdown(raw_content)
    
    return title, date_str, md_content

def get_ep_num(fname):
    # Matches {PREFIX}_{NUM}.html
    match = re.search(r'_(\d+)\.html', fname)
    return int(match.group(1)) if match else 0

def process_prefix(prefix):
    # Find all files with this prefix: e.g. DATA_DIR/IM_*.html
    pattern = os.path.join(DATA_DIR, f"{prefix}_*.html")
    files = glob.glob(pattern)
    
    if not files:
        print(f"No files found for prefix: {prefix}")
        return

    files.sort(key=get_ep_num)
    
    print(f"Processing {len(files)} files for {prefix}...")
    
    current_word_count = 0
    current_byte_count = 0
    current_chunk_content = []
    chunk_start_ep = None
    chunk_end_ep = None
    
    for filepath in files:
        try:
            ep_num = get_ep_num(filepath)
            title, date_str, content = parse_transcript_file(filepath)
            
            if chunk_start_ep is None:
                chunk_start_ep = ep_num
                
            episode_text = f"# Episode: {title}\n**Date:** {date_str}\n\n{content}\n\n"
            episode_text += "---\n\n"
            
            ep_words = len(content.split())
            ep_bytes = len(episode_text.encode('utf-8'))
            
            # Check limits
            if (current_word_count + ep_words > MAX_WORDS) or (current_byte_count + ep_bytes > MAX_BYTES):
                output_filename = os.path.join(OUTPUT_BASE, f"{prefix}_Transcripts_{chunk_start_ep}-{chunk_end_ep}.md")
                with open(output_filename, 'w', encoding='utf-8') as out:
                    out.writelines(current_chunk_content)
                print(f"Written {os.path.basename(output_filename)} (Words: {current_word_count})")
                
                # Reset
                current_chunk_content = []
                current_word_count = 0
                current_byte_count = 0
                chunk_start_ep = ep_num
                
            current_chunk_content.append(episode_text)
            current_word_count += ep_words
            current_byte_count += ep_bytes
            chunk_end_ep = ep_num
            
        except Exception as e:
            print(f"Error processing file {filepath}: {e}. Skipping.")
            continue
        
    # Write final chunk
    if current_chunk_content:
        output_filename = os.path.join(OUTPUT_BASE, f"{prefix}_Transcripts_{chunk_start_ep}-{chunk_end_ep}.md")
        with open(output_filename, 'w', encoding='utf-8') as out:
            out.writelines(current_chunk_content)
        print(f"Written {os.path.basename(output_filename)} (Words: {current_word_count})")

def main():
    parser = argparse.ArgumentParser(description="Process downloaded transcripts into NotebookLM-ready Markdown files.")
    parser.add_argument("--prefixes", nargs="+", help="List of prefixes to process (e.g. IM TWIG)")
    parser.add_argument("--all", action="store_true", help="Process ALL prefixes found in the data directory")
    
    args = parser.parse_args()
    
    prefixes_to_process = set()
    
    if args.all:
        # Scan directory for all unique prefixes
        all_files = glob.glob(os.path.join(DATA_DIR, "*_*.html"))
        for f in all_files:
            basename = os.path.basename(f)
            # Assumption: Prefix is everything before the underscore and number
            # e.g. IM_847.html -> IM
            match = re.match(r'([A-Z]+)_\d+\.html', basename)
            if match:
                prefixes_to_process.add(match.group(1))
    elif args.prefixes:
        prefixes_to_process = set(p.upper() for p in args.prefixes)
    else:
        print("No prefixes specified. Defaulting to IM and TWIG.")
        prefixes_to_process = {"IM", "TWIG"}
        
    for prefix in sorted(prefixes_to_process):
        process_prefix(prefix)

if __name__ == "__main__":
    main()
