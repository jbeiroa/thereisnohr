"""Application module `thereisnohr.models.profiler`."""

from dataclasses import dataclass, field
from typing import List
import ollama

@dataclass
class Profiler:
    """
    A class for summarizing résumés into structured categories using AI models.

    Attributes
    ----------
    resume : str
        The raw text of the résumé to summarize.
    save_to_file : bool, optional
        If True, saves the summary to a file. Defaults to False.
    model : str, optional
        The AI model used for generating the summary. Defaults to 'llama3.2:1b'.

    Methods
    -------
    summarize() -> str:
        Summarizes the résumé into a structured format based on predefined categories.
    """

    resume: str
    save_to_file: bool = False
    model: str = 'llama3.2:1b'
    categories: List[str] = field(default_factory=lambda: ['contact', 'education', 'experience', 'skills'])
        
    def summarize(self) -> str:
        """
        Summarizes the résumé into a structured format based on predefined categories.

        Returns
        -------
        str
            A structured summary of the résumé including name, skills, experience, and education.
        """
        prompt = f"""You are a human resources expert, specialized in talent acquisition for schools.
        You are tasked with summarizing résumés in the following structured format:
        - Name: [Name here]
        - Skills: [Skills listed here]
        - Experience: [Job experience and other relevant experience here]
        - Education: [Degrees obtained and courses taken]
        
        The summary should extract and organize the following details:
        - Name: The candidate’s full name.
        - Skills: List of technical and non-technical skills.
        - Experience: Teaching/research positions, non-teaching roles, and any other relevant professional experience.
        - Education: Degrees obtained and other studies, including courses taken.
        
        The following text is a candidate’s résumé:
        
        {self.resume}
        
        Provide the structured summary based on the given résumé. Do not output any explanatory text.
        """
        response = ollama.generate(
            model=self.model,
            prompt=prompt
        )
        return response['response']