import os
from getter import Getter
from handler import Handler
from profiler import Profiler

def get_cvs_path():
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