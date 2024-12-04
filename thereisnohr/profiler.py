import os
import re
from dataclasses import dataclass, field
from typing import List
import ollama

@dataclass
class Profiler:
    resume: str
    save_to_file: bool = False
    model: str = 'llama3.2:1b'
    categories: List = field(default_factory=lambda: ['contact', 'education', 'experience', 'skills'])

    def split_by_blocks(self):
        block_pattern = r'\.\n|\n\n'
        blocks = re.split(block_pattern, self.resume)
        for idx, block in enumerate(blocks):
            blocks[idx] = re.sub(r'#+\s', '', block).lstrip('\n')

        blocks = list(filter(None, blocks))
        return blocks
            

    def get_name(self):
        prompt = f"""The following text is an excerpt from a job candidate's résumé for a teaching position.
        ---
        {self.resume}
        ---
        Extract the candidate's full name. Return only the name as your answer, formated in sentence case and without any other information nor special characters such as punctuation symbols. 
        """
        response = ollama.generate(
            model=self.model,
            prompt=prompt
        )
        return response['response']
        
    def summarize(self):
        prompt = f"""You are a human resources expert, specialized in talent acquisition for schools. 
        You are tasked with summarizing résumés highlighting the following aspects:
            - Contact Information (phone number, email address and social network handles/personal web pages).
            - Education (degrees obtained and other studies such as courses made).
            - Job Experience (teaching/research positions, non teaching jobs, etc.).
            - Skills (technical or others).
        The following text is a candidate's résumé.
        ---
        {self.resume}
        ---
        Write a 100 to 150 words summary of the résumé given.
        """
        response = ollama.generate(
            model=self.model,
            prompt=prompt
        )
        return response['response']