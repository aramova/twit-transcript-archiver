
import re

SCRIPT_STYLE_RE = re.compile(r'<(script|style).*?</\1>', re.DOTALL)
BOLD_RE = re.compile(r'<(b|strong)[^>]*>(.*?)</\1>', re.DOTALL)
ITALIC_RE = re.compile(r'<(i|em)[^>]*>(.*?)</\1>', re.DOTALL)
A_RE = re.compile(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"[^>]*>(.*?)</a>', re.DOTALL)
TAG_RE = re.compile(r'<[^>]+>')
SPEAKER_NAME_RE = re.compile(r"^\*{0,2}([A-Z][a-zA-Z'.\-]+(?:\s+[A-Z][a-zA-Z'.\-]+)*)\*{0,2}\s*:\s*\*{0,2}\s*(.*)")

def html_to_markdown(html_content, ep_num="457", date_ymd="14-05-21"):
    if not html_content:
        return ""
    
    text = SCRIPT_STYLE_RE.sub('', html_content)
    
    # Remove AI-generated disclaimer
    disclaimer_pattern = r'\*?Please be advised this transcript is AI-generated.*?(?:ad-supported version of the show|approximate times|word for word)\.?\*?'
    text = re.sub(disclaimer_pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
    
    def sanitize_link(match):
        url = match.group(1)
        content = match.group(2)
        if url.startswith('/') or url.startswith('http://') or url.startswith('https://'):
            return f" [{content}]({url}) "
        return f" {content} "

    # --- Structural Tag Preservation ---
    # Replace tags with a marker, BUT don't use space yet
    text = re.sub(r'</?(?:p|br|div|tr|table|ul|ol|li|h1|h2|h3)[^>]*>', '__PARA__', text, flags=re.IGNORECASE)
    
    # Bold/Italic
    text = BOLD_RE.sub(r'**\2**', text)
    text = ITALIC_RE.sub(r'*\2*', text)
    
    # Links
    text = A_RE.sub(sanitize_link, text)
    
    # Surgical cleaning of noise tags
    text = re.sub(r'</?(?:span|font|o:p|st1:[^>]+|shape|path|lock|imagedata|v:[^>]+|w:[^>]+|m:[^>]+|style|script)[^>]*>', '', text, flags=re.IGNORECASE)
    
    # Strip ALL other remaining tags
    text = TAG_RE.sub(' ', text)
    
    # Normalize entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    
    # --- HERE IS THE FIX ---
    # Instead of collapsing EVERYTHING to a single line, 
    # we convert paragraph markers to newlines, AND normalize literal newlines to newlines.
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
    current_speaker = "Leo"
    buffer = []
    current_prefix = None

    def flush_buffer():
        if buffer:
            content = " ".join(buffer)
            # Normalize whitespace within the buffer
            content = re.sub(r'\s+', ' ', content).strip()
            if content:
                final_lines.append(f"{current_prefix} - {content}")
            buffer.clear()

    # Pattern for speaker/timestamp patterns at start of line
    METADATA_REGEXES = [
        re.compile(r'^(\d+:\d+(?::\d+)?)\s*(?:-\s*)?([^:]+)(?::\s*(.*))?'), # Pattern 1
        re.compile(r'^(.+?)\s*\[(\d+:\d+(?::\d+)?)\s*\]\s*:?\s*(.*)'), # Pattern 2
        re.compile(r'^(.+?)\s*\(\s*(\d+:\d+(?::\d+)?)\s*\)\s*:?\s*(.*)'), # Pattern 3
        re.compile(r'^\(\s*(\d+:\d+(?::\d+)?)\s*\)\s*:?\s*(.*)'), # Pattern 4
        SPEAKER_NAME_RE # Pattern 5
    ]

    for line in blocks:
        line = line.strip()
        if not line:
            continue
            
        found_new_metadata = False
        content = line
        
        # Test each regex
        for i, regex in enumerate(METADATA_REGEXES):
            match = regex.match(line)
            if match:
                found_new_metadata = True
                if i == 0: # Pattern 1: Timestamp - Speaker: Content
                    if line[0].isdigit():
                        current_timestamp = match.group(1)
                        potential_speaker = match.group(2).strip()
                        if len(potential_speaker) < 40 and not any(c in potential_speaker for c in '.!?'):
                            current_speaker = potential_speaker
                            content = (match.group(3) or "").strip()
                elif i == 1: # Pattern 2: Speaker [Timestamp]: Content
                    current_speaker = match.group(1).strip()
                    current_timestamp = match.group(2).strip()
                    content = match.group(3).strip()
                elif i == 2: # Pattern 3: Speaker (Timestamp): Content
                    current_speaker = match.group(1).strip()
                    current_timestamp = match.group(2).strip()
                    content = match.group(3).strip()
                elif i == 3: # Pattern 4: (Timestamp): Content
                    current_timestamp = match.group(1).strip()
                    content = match.group(2).strip()
                elif i == 4: # Pattern 5: Speaker: Content
                    current_speaker = match.group(1).strip()
                    content = match.group(2).strip()
                break # Found a match

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
    return "\n\n".join(final_lines)

monoblock_html = """
<span>Leo Laporte:</span> This is Twit.
<span>Dan Patterson:</span> Wonderful to be here.
"""

hopped_up_html = """
<p>Please be advised this transcript is AI-generated and may not be word for word. Time codes refer to the approximate times in the ad-supported version of the show.&nbsp;</p>
<p>EP:457 Date:14-05-21 - Leo - **Hopped
up on Goofballs
</p>
"""

print("--- MONOBLOCK TEST ---")
print(html_to_markdown(monoblock_html))
print("\n--- FRAGMENTATION TEST ---")
print(html_to_markdown(hopped_up_html))
