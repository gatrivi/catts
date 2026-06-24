import re

def fix_spacing(text):
    """
    Fixes spacing issues where letters are separated by spaces.
    """
    # Improved pattern to handle more cases
    # Match sequences where single letters are separated by spaces
    pattern = r'\b(?:[a-zA-Z]\s){2,}[a-zA-Z]\b'
    
    def replace_spaced_letters(match):
        spaced_word = match.group(0)
        # Remove spaces and check if it looks like a real word
        fixed = spaced_word.replace(' ', '')
        # Basic check: if the fixed version is alphabetic and reasonable length
        if fixed.isalpha() and len(fixed) >= 2:
            return fixed
        return spaced_word
    
    fixed_text = re.sub(pattern, replace_spaced_letters, text)
    return fixed_text


def split_into_chapters(text):
    """
    Split text into chapters based on common patterns.
    Returns a list of dictionaries with 'title' and 'content' keys.
    """
    # More comprehensive patterns to identify chapter starts
    patterns = [
        r'^\s*CHAPTER\s+\d+\s*$',
        r'^\s*Chapter\s+\d+\s*$',
        r'^\s*CHAPTER\s+[IVXLCDM]+\s*$',
        r'^\s*Chapter\s+[IVXLCDM]+\s*$',
        r'^\s*\d+\s*$',
        r'^\s*[IVXLCDM]+\s*$',
        r'^\s*Section\s+\d+\s*$',
        r'^\s*SECTION\s+\d+\s*$',
    ]
    
    # Split the text into lines
    lines = text.split('\n')
    
    chapters = []
    # Start with an initial chapter
    current_title = 'Introduction'
    current_content = []
    in_chapter = False
    
    for line in lines:
        # Check if the line matches any chapter pattern
        is_chapter_header = False
        for pattern in patterns:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                is_chapter_header = True
                break
        
        if is_chapter_header:
            # If we're already in a chapter, save it
            if in_chapter or current_content:
                chapter_content = '\n'.join(current_content).strip()
                if chapter_content:
                    chapters.append({'title': current_title, 'content': chapter_content})
                current_content = []
            # Start new chapter
            current_title = line.strip()
            in_chapter = True
        else:
            current_content.append(line)
    
    # Add the last chapter
    if current_content:
        chapter_content = '\n'.join(current_content).strip()
        if chapter_content:
            chapters.append({'title': current_title, 'content': chapter_content})
    
    # Handle case where no chapters were found
    if not chapters:
        chapters.append({'title': 'Full Text', 'content': text.strip()})
    
    return chapters


def process_book(text):
    """Process the book text by fixing spacing and splitting into chapters"""
    # First fix the spacing
    fixed_text = fix_spacing(text)
    # Then split into chapters
    chapters = split_into_chapters(fixed_text)
    return chapters
