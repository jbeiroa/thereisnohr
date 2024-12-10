import re
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Handler:
    """
    A class for processing and cleaning text blocks from résumés.

    Attributes
    ----------
    resume : str
        The raw text of the résumé to process.

    Methods
    -------
    split_by_blocks() -> List[str]:
        Splits the résumé text into blocks based on double newline characters.
    
    clean_resume_blocks() -> Tuple[str, List[str]]:
        Cleans the text blocks, removes unwanted elements, extracts links, and removes duplicates.
    """

    resume: str

    def split_by_blocks(self) -> List[str]:
        """
        Splits the résumé text into blocks based on double newline characters.

        Returns
        -------
        List[str]
            A list of cleaned text blocks with leading/trailing whitespace and unnecessary characters removed.
        """
        block_pattern = r'\n\n'
        blocks = re.split(block_pattern, self.resume)
        for idx, block in enumerate(blocks):
            blocks[idx] = re.sub(r'#+\s', '', block).lstrip('\n')

        blocks = list(filter(None, blocks))
        return blocks
    
    def clean_resume_blocks(self) -> Tuple[str, List[str]]:
        """
        Cleans text blocks by removing links, unwanted patterns, and duplicates.
        Extracts hyperlinks and returns cleaned text and extracted links.

        Returns
        -------
        Tuple[str, List[str]]
            A tuple containing:
            - The cleaned text of unique blocks as a single string.
            - A list of extracted links from the text.
        """
        extracted_links = []
        unique_blocks = []
        seen_blocks = set()
        
        for block in self.split_by_blocks():
            # Remove special character sequences (e.g., '-----')
            if re.match(r'^[\-\s]+$', block):
                continue
            
            # Remove year ranges (e.g., '2022 - 2024', '2016 - Present')
            if re.search(r'\b\d{4}\s*-\s*(\d{4}|Present)\b', block):
                continue
            
            # Remove geographical data (e.g., 'Bs. As. Argentina')
            if re.search(r'\b(?:[A-Z][a-z]+\.)+\s*[A-Z][a-z]+(?:\s*\b[A-Z][a-z]+)?', block):
                continue
            
            # Optionally, remove very short blocks (e.g., single words or short sequences)
            if len(block.split()) < 3:
                continue

            # Find all links in the current block
            links = re.findall(r'https?://[^\s\)\]]+', block)
            extracted_links.extend(links)
    
            # Remove links from the block
            cleaned_block = re.sub(r'https?://[^\s\)\]]+', '', block).strip()

            # Remove leftover patterns like '[Some text] ()'
            cleaned_block = re.sub(r'\[([^\[\]]+)\]\s*\(\s*\)', r'\1', cleaned_block).strip()

            # Normalize by removing newline characters and trimming extra spaces
            normalized_block = ' '.join(cleaned_block.splitlines()).strip()
    
            # Check if the normalized version is already processed
            if normalized_block not in seen_blocks:
                seen_blocks.add(normalized_block)
                unique_blocks.append(normalized_block)  # Keep the original formatting in the output
            
            text = "\n".join(unique_blocks)
            
        return text, extracted_links