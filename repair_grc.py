"""Fast repair: just strip </div> from GRC body content + fix dates using simple string search."""
import os, re, glob

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December']

def find_date_fast(text):
    """Fast date finder - prioritize 'This is Security Now! ... for [Date]' intro pattern."""
    
    # Pattern: "recorded Tuesday, February 5th, 2019"
    # Added optional day name and more flexible spacing/tags
    # Use \W+ to match any non-word characters (handles non-breaking spaces, commas, etc.)
    intro_match = re.search(r'(?:Security Now!|Episode \d+).*?(?:for|recorded)\W+(?:[A-Z][a-z]+\W+)?([A-Z][a-z]+\W+\d{1,2}(?:st|nd|rd|th)?\W+\d{4})', text[:30000], re.IGNORECASE | re.DOTALL)
    if intro_match:
        ds = intro_match.group(1)
        ds = re.sub(r'\W+', ' ', ds).strip()
        ds = re.sub(r'(\d{1,2})(?:st|nd|rd|th)', r'\1', ds)
        m = re.match(rf'([A-Z][a-z]+)\s+(\d{{1,2}})\s+(\d{{4}})', ds)
        if m:
            return f"{m.group(1)} {m.group(2)}, {m.group(3)}"

    # Try "recorded Wednesday, March 24, 2015" without the Episode/Security Now! anchor
    # Also handle if there's a <b> or <p> between 'recorded' and the date
    lines = text[:15000].split('\n')
    for line in lines[:300]:
        for m in MONTHS:
            idx = line.find(m)
            if idx == -1: continue
            rec_idx = line.lower().find('recorded')
            if rec_idx >= 0 and rec_idx < idx:
                # Extract starting from month
                rest = line[idx:]
                dm = re.match(rf'({m})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})', rest)
                if dm:
                    return f"{dm.group(1)} {dm.group(2)}, {dm.group(3)}"
    
    # Fallback 1: find first "Episode #NNN" then look for month nearby
    ep_idx = text.find('Episode')
    if ep_idx == -1: ep_idx = text.find('episode')
    if ep_idx >= 0:
        nearby = text[ep_idx:ep_idx+2000] # Increased window
        for m in MONTHS:
            idx = nearby.find(m)
            if idx >= 0:
                rest = nearby[idx:]
                dm = re.match(rf'({m})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})', rest)
                if dm:
                    return f"{dm.group(1)} {dm.group(2)}, {dm.group(3)}"
    
    # Fallback 2: "Last Edit: Nov 14, 2005"
    last_edit = re.search(rf'Last Edit:\s*([A-Z][a-z]+\s+\d{{1,2}},\s+\d{{4}})', text, re.IGNORECASE)
    if last_edit:
        return last_edit.group(1)
    
    # Fallback 3: Just the first month-day-year pattern found in the first 10k chars
    for m in MONTHS:
        match = re.search(rf'({m})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})', text[:10000])
        if match:
            return f"{match.group(1)} {match.group(2)}, {match.group(3)}"

    return None

def clean_grc_body(text):
    """Strip GRC masthead, navigation menus, and sidebar from the body content."""
    
    # Marker for the actual transcript header
    # e.g. <font ...><b>Transcript of Episode #13</b></font>
    content_start = re.search(r'(?:Transcript of Episode #\d+)', text)
    if content_start:
        return text[content_start.start():]
    
    # Fallback: Find the first speaker attribution
    speaker_start = re.search(r'<b>(?:Leo Laporte|Steve Gibson):</b>', text)
    if speaker_start:
        # Go back a bit to catch any leading description/tease
        start_idx = max(0, speaker_start.start() - 1000)
        return text[start_idx:]
    
    return text

repaired = 0
skipped = 0
date_fixed = 0

for filepath in sorted(glob.glob(os.path.join(DATA_DIR, "SN_*.html"))):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    if not content.startswith('<h1 class="post-title">Security Now'):
        skipped += 1
        continue
    
    # Split on our markers
    lines = content.split('\n', 2)  # title, byline, rest
    if len(lines) < 3:
        skipped += 1
        continue
    
    title_line = lines[0]
    old_byline = lines[1]
    body_line = lines[2]
    
    # Extract old date
    old_date_m = re.search(r'<p class="byline">(.*?)</p>', old_byline)
    old_date = old_date_m.group(1) if old_date_m else ""
    
    # Try to find better date
    new_date = find_date_fast(body_line)
    if new_date and (new_date != old_date or old_date == "Unknown Date"):
        date_fixed += 1
        byline = f'<p class="byline">{new_date}</p>'
    else:
        byline = old_byline
    
    # Clean body: strip navbar/masthead and trailing </div>
    body_cleaned = clean_grc_body(body_line)
    body_fixed = body_cleaned.replace('</div>', '')
    
    # Rebuild with wrapper's closing </div> at the end
    new_content = f"{title_line}\n{byline}\n{body_fixed}</div>\n"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    repaired += 1
    if repaired % 100 == 0:
        print(f"  ...repaired {repaired} files so far")

print(f"Repaired {repaired} GRC files (dates fixed: {date_fixed}), skipped {skipped} twit.tv files")

# Delete markdown files to force regeneration
md_deleted = 0
for pattern in ["SN_Transcripts*.md", "TWIT_Transcripts*.md"]:
    for fp in glob.glob(os.path.join(DATA_DIR, pattern)):
        os.remove(fp)
        md_deleted += 1
print(f"Deleted {md_deleted} existing markdown files")
