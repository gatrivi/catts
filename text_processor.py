import re

def fix_spacing(text):
    """
    Fixes spacing issues where letters are separated by spaces.
    This pattern matches single letters surrounded by spaces and joins them together.
    """
    # Pattern to find sequences of single letters separated by spaces
    # We'll use a regular expression to find and fix these
    def replace_spaced_letters(match):
        # Remove all spaces within the matched text
        spaced_word = match.group(0)
        # Only fix if the result is a valid word (all letters)
        # Remove spaces and check if it's alphabetic
        fixed = spaced_word.replace(' ', '')
        if fixed.isalpha():
            return fixed
        return spaced_word
    
    # Match patterns where there are spaces between what appear to be individual letters
    # This pattern looks for a letter, space, letter, space, etc.
    # Using word boundaries to ensure we're not matching parts of larger words
    pattern = r'\b(?:[a-zA-Z]\s)+[a-zA-Z]\b'
    fixed_text = re.sub(pattern, replace_spaced_letters, text)
    return fixed_text


def split_into_chapters(text):
    """
    Split text into chapters based on common patterns.
    Returns a list of dictionaries with 'title' and 'content' keys.
    """
    # Common patterns to identify chapter starts
    # These are more precise patterns to avoid false positives
    patterns = [
        r'^CHAPTER\s+\d+',
        r'^Chapter\s+\d+',
        r'^CHAPTER\s+[IVXLCDM]+',
        r'^Chapter\s+[IVXLCDM]+',
        r'^\d+\s*$',  # A line with just a number
    ]
    
    # Combine patterns with start of line or following newlines
    # Split on any occurrence of these patterns
    # Use a more robust approach by splitting on lines that match these patterns
    lines = text.split('\n')
    
    chapters = []
    current_chapter = {'title': 'Introduction', 'content': ''}
    
    for line in lines:
        # Check if the line matches any chapter pattern
        is_chapter_header = False
        for pattern in patterns:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                is_chapter_header = True
                break
        
        if is_chapter_header:
            # Save the current chapter
            if current_chapter['content'].strip():
                chapters.append(current_chapter)
            # Start a new chapter
            current_chapter = {'title': line.strip(), 'content': ''}
        else:
            current_chapter['content'] += line + '\n'
    
    # Add the last chapter
    if current_chapter['content'].strip():
        chapters.append(current_chapter)
    
    return chapters


def process_book(text):
    """Process the book text by fixing spacing and splitting into chapters"""
    # First fix the spacing
    fixed_text = fix_spacing(text)
    # Then split into chapters
    chapters = split_into_chapters(fixed_text)
    return chapters
