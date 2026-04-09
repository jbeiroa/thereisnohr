import json
import logging
from pathlib import Path

import pymupdf
import typer
from litellm import completion

# We'll use a simple approach to wrap markdown in HTML for pymupdf
def md_to_html(md_text: str) -> str:
    # Very basic conversion for common resume elements
    # Since we can't easily install new packages, we'll try to use what's available
    # Actually, let's see if 'markdown' package is installed.
    try:
        import markdown
        return markdown.markdown(md_text)
    except ImportError:
        # Fallback to a very simple manual wrap if needed, but 'markdown' is common.
        # Let's check pyproject.toml first.
        return f"<html><body>{md_text.replace('\n', '<break>').replace('<break>', '<br>')}</body></html>"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = typer.Typer(help="Generate dummy PDFs from synthetic resume JSONL data using LLM structuring.")

@app.command()
def generate(
    input_file: Path = typer.Option(Path("finetune_data/train.jsonl"), "--input-file", help="Path to the input JSONL file"),
    output_dir: Path = typer.Option(Path("data/dummy_pdfs"), "--output-dir", help="Directory to save the generated PDFs"),
    count: int = typer.Option(20, "--count", help="Number of PDFs to generate"),
    max_lines: int = typer.Option(60, "--max-lines", help="Maximum number of lines to read from the input file"),
):
    """
    Reads records from a JSONL file and generates high-quality PDF resumes.
    """
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        raise typer.Exit(code=1)

    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean output directory
    for f in output_dir.glob("*.pdf"):
        f.unlink()
        logger.info(f"Deleted old dummy PDF: {f.name}")

    model = "openai/gpt-4o-mini"
    
    processed = 0
    lines_read = 0
    
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            if processed >= count or lines_read >= max_lines:
                break
            
            lines_read += 1
            line = line.strip()
            if not line:
                continue
                
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse line {lines_read}: {line[:50]}...")
                continue
                
            resume_text = record.get("resume", "")
            if not resume_text:
                continue
            
            # Step 1: Filter and Structure with LLM
            prompt = (
                "You are an expert resume formatter. I will provide a text that might be a resume or a candidate evaluation. "
                "If it is a resume, format it into a professional, well-structured Markdown document with clear sections "
                "(Contact Information, Summary, Experience, Education, Skills, etc.). Use bullet points and headers. "
                "If it is NOT a resume (e.g., it's an evaluation or commentary), respond ONLY with the word 'INVALID'.\n\n"
                f"--- TEXT START ---\n{resume_text}\n--- TEXT END ---"
            )
            
            try:
                logger.info(f"Processing candidate at line {lines_read}...")
                response = completion(
                    model=model,
                    messages=[{"role": "user", "content": prompt}]
                )
                structured_md = response.choices[0].message.content.strip()
                
                if structured_md == "INVALID":
                    logger.info(f"Skipping line {lines_read}: Not a valid resume.")
                    continue
                
                # Strip markdown code block markers if present
                if structured_md.startswith("```markdown"):
                    structured_md = structured_md.replace("```markdown", "", 1).rstrip("`").strip()
                elif structured_md.startswith("```"):
                    structured_md = structured_md.replace("```", "", 1).rstrip("`").strip()

                if not structured_md:
                    logger.warning(f"LLM returned empty content for line {lines_read}")
                    continue

                # Step 2: Convert to HTML then PDF
                # We'll use a very simple HTML conversion since we know PyMuPDF handles HTML well.
                # Wrap in a basic CSS for better look
                html_content = f"""
                <html>
                <head>
                <style>
                    body {{ font-family: sans-serif; line-height: 1.4; margin: 40px; font-size: 11pt; }}
                    h1 {{ color: #2c3e50; border-bottom: 1px solid #eee; }}
                    h2 {{ color: #34495e; margin-top: 20px; }}
                    ul {{ margin-bottom: 10px; }}
                    li {{ margin-bottom: 5px; }}
                </style>
                </head>
                <body>
                {md_to_html(structured_md)}
                </body>
                </html>
                """
                
                pdf_path = output_dir / f"dummy_resume_{processed + 1}.pdf"
                
                # Use PyMuPDF's HTML engine
                doc = pymupdf.open("html", html_content.encode("utf-8"))
                pdf_bytes = doc.convert_to_pdf()
                pdf_doc = pymupdf.open("pdf", pdf_bytes)
                pdf_doc.save(str(pdf_path))
                pdf_doc.close()
                doc.close()
                
                logger.info(f"Generated: {pdf_path.name}")
                processed += 1
                
            except Exception as e:
                logger.error(f"Error processing line {lines_read}: {e}")
                continue
                
    logger.info(f"Successfully generated {processed} dummy PDFs in {output_dir}")

if __name__ == "__main__":
    app()
