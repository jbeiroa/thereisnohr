import json
import logging
from pathlib import Path

import fitz  # PyMuPDF
import typer

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = typer.Typer(help="Generate dummy PDFs from synthetic resume JSONL data.")

@app.command()
def generate(
    input_file: Path = typer.Option(..., "--input-file", help="Path to the input JSONL file"),
    output_dir: Path = typer.Option(..., "--output-dir", help="Directory to save the generated PDFs"),
    count: int = typer.Option(10, "--count", help="Number of PDFs to generate"),
):
    """
    Reads records from a JSONL file and generates dummy PDF resumes.
    """
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        raise typer.Exit(code=1)

    output_dir.mkdir(parents=True, exist_ok=True)
    
    processed = 0
    
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if processed >= count:
                break
                
            line = line.strip()
            if not line:
                continue
                
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse line: {line[:50]}...")
                continue
                
            # Expecting {"index": 123, "resume": "Text..."}
            resume_text = record.get("resume", "")
            index_id = record.get("index", processed)
            
            if not resume_text:
                continue
                
            pdf_path = output_dir / f"dummy_resume_{index_id}.pdf"
            
            # Create PDF
            doc = fitz.open()
            page = doc.new_page()
            
            # Define a rectangle for the text to wrap inside
            rect = fitz.Rect(50, 50, 550, 800)
            
            # Insert text, allowing it to wrap and create new pages if needed?
            # PyMuPDF insert_textbox does not auto-create pages if text overflows.
            # For a simple dummy PDF, this might be okay, or we can just insert as much as fits.
            # To handle multiple pages:
            # We can just insert it. If it overflows, it returns the unused portion.
            leftover = page.insert_textbox(rect, resume_text, fontsize=10, fontname="helv")
            
            while leftover >= 0: # insert_textbox returns index of unprinted char, or -1 if all fit
                page = doc.new_page()
                leftover_text = resume_text[int(leftover):]
                # if there is still leftover text, we might loop infinitely if we don't advance
                # actually, insert_textbox returns -1 if successful, or >= 0.
                if not leftover_text:
                    break
                leftover_new = page.insert_textbox(rect, leftover_text, fontsize=10, fontname="helv")
                if leftover_new == leftover:
                    # Prevent infinite loop if text cannot fit
                    break
                leftover = leftover_new
                
            doc.save(str(pdf_path))
            doc.close()
            
            processed += 1
            
    logger.info(f"Successfully generated {processed} dummy PDFs in {output_dir}")

if __name__ == "__main__":
    app()
