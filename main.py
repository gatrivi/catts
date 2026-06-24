import os
from text_processor import process_book

def main():
    # Read OCR text from a file (adjust the filename as needed)
    ocr_text_path = 'ocr_output.txt'
    with open(ocr_text_path, 'r', encoding='utf-8') as file:
        ocr_text = file.read()
    
    # Process the text
    processed_chapters = process_book(ocr_text)
    
    # Create output directory for audio files
    os.makedirs('chapters', exist_ok=True)
    
    # Generate audio for each chapter
    for i, chapter in enumerate(processed_chapters):
        chapter_text = f"{chapter['title']}\n\n{chapter['content']}"
        
        # Write chapter text to a file (for debugging or TTS input)
        chapter_filename = f"chapters/chapter_{i+1:03d}.txt"
        with open(chapter_filename, 'w', encoding='utf-8') as file:
            file.write(chapter_text)
        
        # Here you would integrate with your TTS system
        # For example:
        # tts_output_path = f"chapters/chapter_{i+1:03d}.mp3"
        # generate_tts_audio(chapter_text, tts_output_path)
        
        print(f"Processed chapter {i+1}: {chapter['title']}")
    
    print("All chapters processed!")

if __name__ == "__main__":
    main()
