"""Application module `thereisnohr.pipeline.main`."""

import os
from getter import Getter
from handler import Handler
from profiler import Profiler
from selector import Candidate_Selector

def get_cvs_path():
    """Get cvs path.

    Returns:
        object: Computed result.

    """
    repo_path = os.path.dirname(os.getcwd())
    cvs_path = os.path.join(repo_path, 'cvs')
    return cvs_path

if __name__ == '__main__':
    cvs_path = get_cvs_path()
    getter = Getter(cvs_path)
    while True:
        cv = getter.get_next()
        if cv is None:
            break
        handler = Handler(cv)
        data = handler.clean_resume_blocks()
        profiler = Profiler(data[0])
        summary = profiler.summarize()
        with open(os.path.join(cvs_path, 'summary.txt'), 'a') as out:
            out.write(summary)
            out.write('\n\n-------------------\n\n')
        print(summary)
        print('\n\n-------------------\n\n')
    
    summaries_path = os.path.join(cvs_path, 'summary.txt')
    descriptions_path = os.path.join(cvs_path, 'job_descriptions.txt')
    with open(summaries_path, 'r') as file:
        txt = file.read()
        summaries = txt.split('\n\n-------------------\n\n')
    summaries.pop(-1)

    with open(descriptions_path, 'r') as file:
        txt = file.read()
        job_descriptions = txt.split('\n\n-------------------\n\n')
    selector = Candidate_Selector(summaries, job_descriptions[1])
    selector.print_top_candidates(k=3)    