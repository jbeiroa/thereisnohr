import os
from dataclasses import dataclass, field
from typing import List, Optional
import pymupdf
import pymupdf4llm

@dataclass
class Getter:
    directory: str
    save_to_file: bool = False
    current_index: int = field(init=False, default=0)
    files: List[str] = field(init=False)
    markdown: Optional[str] = field(init=False, default=None)

    def __post_init__(self):
        # List all PDF files in the directory
        self.files = [file for file in os.listdir(self.directory) if file.endswith('.pdf')]
        if not self.files:
            raise FileNotFoundError("No PDF files found in the specified directory.")

    def get_cv(self, path: str) -> str:
        """Gets one résumé from a given path.

        Args:
            path (str): path to the résumé file.

        Returns:
            str: résumé in markdown format.
        """
        doc = pymupdf.open(path)
        self.markdown = pymupdf4llm.to_markdown(doc, show_progress=False)

        return self.markdown
    
    def get_next(self) -> Optional[str]:
        """Processes the next PDF file in the directory."""
        if self.current_index >= len(self.files):
            print("No more files to process.")
            return None
        
        current_file_path = os.path.join(self.directory, self.files[self.current_index])
        self.current_index += 1
        
        self.markdown = self.get_cv(current_file_path)
        
        if self.save_to_file:
            md_file_path = os.path.splitext(current_file_path)[0] + ".md"
            with open(md_file_path, 'w', encoding='utf-8') as md_file:
                md_file.write(self.markdown)
        
        return self.markdown

    def reset(self):
        """Resets the processing index to the beginning."""
        self.current_index = 0
        self.markdown = None