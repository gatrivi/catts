import os
import argparse
from text_processor import process_book

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Process a book text into chapters for TTS')
    parser.add_argument('input_file', nargs='?', default='ocr_output.txt', 
                        help='Path to the OCR text file (default: ocr_output.txt)')
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: File '{args.input_file}' not found.")
        return
    
    try:
        # Read OCR text from the specified file
        with open(args.input_file, 'r', encoding='utf-8') as file:
            ocr_text = file.read()
        
        # Process the text
        processed_chapters = process_book(ocr_text)
        
        # Create output directory for text files
        os.makedirs('chapters', exist_ok=True)
        
        # Generate text files for each chapter
        for i, chapter in enumerate(processed_chapters):
            chapter_text = f"{chapter['title']}\n\n{chapter['content']}"
            
            # Write chapter text to a file
            chapter_filename = f"chapters/chapter_{i+1:03d}.txt"
            with open(chapter_filename, 'w', encoding='utf-8') as file:
                file.write(chapter_text)
            
            print(f"Processed chapter {i+1}: {chapter['title']}")
        
        print(f"All {len(processed_chapters)} chapters processed!")
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
