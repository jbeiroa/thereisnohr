"""Application module `thereisnohr.data.getter`."""

import os
from dataclasses import dataclass, field
from typing import List, Optional
import pymupdf4llm

@dataclass
class Getter:
    """
    A class for processing PDF files in a specified directory and converting them to markdown format.

    Attributes
    ----------
    directory : str
        Path to the directory containing PDF files.
    save_to_file : bool, optional
        If True, saves the converted markdown to a file. Defaults to False.
    current_index : int
        Tracks the index of the current file being processed. Initialized to 0.
    files : List[str]
        List of PDF files in the directory. Initialized during object creation.
    markdown : Optional[str]
        Holds the markdown representation of the last processed file. Defaults to None.

    Methods
    -------
    __post_init__():
        Initializes the list of PDF files in the directory. Raises FileNotFoundError if no PDF files are found.
    
    get_cv(path: str) -> str:
        Converts a PDF file at the specified path to markdown format.
    
    get_next() -> Optional[str]:
        Processes the next PDF file in the directory and converts it to markdown format.
        If `save_to_file` is True, saves the markdown to a file. Returns the markdown or None if no files remain.
    
    reset():
        Resets the processing index to the beginning and clears the last processed markdown.
    """

    directory: str
    save_to_file: bool = False
    current_index: int = field(init=False, default=0)
    files: List[str] = field(init=False)
    markdown: Optional[str] = field(init=False, default=None)

    def __post_init__(self):
        """
        Initializes the list of PDF files in the directory. Raises a FileNotFoundError
        if no PDF files are found in the specified directory.

        Raises
        ------
        FileNotFoundError
            If no PDF files are found in the specified directory.
        """
        self.files = [file for file in os.listdir(self.directory) if file.endswith('.pdf')]
        if not self.files:
            raise FileNotFoundError("No PDF files found in the specified directory.")

    def get_cv(self, path: str) -> str:
        """
        Converts a PDF file at the specified path to markdown format.

        Parameters
        ----------
        path : str
            Path to the PDF file to be converted.

        Returns
        -------
        str
            The markdown representation of the PDF file.
        """
        self.markdown = pymupdf4llm.to_markdown(path, show_progress=False)
        return self.markdown
    
    def get_next(self) -> Optional[str]:
        """
        Processes the next PDF file in the directory and converts it to markdown format.
        If `save_to_file` is True, saves the markdown to a file.

        Returns
        -------
        Optional[str]
            The markdown representation of the next PDF file, or None if no files remain.
        """
        if self.current_index >= len(self.files):
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
        """
        Resets the processing index to the beginning and clears the last processed markdown.

        Returns
        -------
        None
        """
        self.current_index = 0
        self.markdown = None