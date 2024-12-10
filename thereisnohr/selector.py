import os
from itertools import product
from dataclasses import dataclass, field
from sentence_transformers import SentenceTransformer, util
from typing import List


@dataclass
class Candidate_Selector():
    candidates: List[str] = field(default=None)
    job_description: str = field(default=None)
    model: str = 'paraphrase-multilingual-MiniLM-L12-v2'

    def make_model(self):
        return SentenceTransformer(self.model)
    
    def embed(self, data):
        embedding = self.make_model().encode(data)
        return embedding
    
    def calculate_similarities(self):
        candidates = self.embed(self.candidates)
        job = self.embed(self.job_description)
        hits = util.semantic_search(job, candidates)

        return hits
    
    
    def select_top_candidates(self, k = 1):
        hits = self.calculate_similarities()
        if k == 1:
            return hits[0][:k]['corpus_id']
        top_k = []
        for i in range(k):
            top_k.append(hits[0][i]['corpus_id'])
        return top_k

    def print_top_candidates(self, k = 1):
        top_k = self.select_top_candidates(k=k)
        result = f"""Job desciption: {self.job_description}

        Top {k} candidate summaries:

        {'\n\n------\n\n'.join([self.candidates[k] for k in top_k])}
        """
        print(result)
