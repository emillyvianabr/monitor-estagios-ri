"""One bounded JobSpy query. Output only selected public job fields."""
import contextlib
import io
import json
import logging
import sys
from jobspy import scrape_jobs

class Capture(logging.Handler):
    def __init__(self):
        super().__init__(); self.messages = []
    def emit(self, record):
        if record.levelno >= logging.WARNING:
            self.messages.append(record.getMessage())

def main():
    spec = json.loads(sys.argv[1])
    if spec['source'] in {'gupy', '99jobs', 'ciee'}:
        from public_sources import collect
        print(json.dumps(collect(spec), ensure_ascii=True))
        return
    capture = Capture()
    # JobSpy loggers use their own handlers and do not always propagate.
    for name in list(logging.Logger.manager.loggerDict):
        if 'jobspy' in name.lower():
            logger = logging.getLogger(name)
            logger.handlers = [capture]
            logger.propagate = False
    google_term = f'estágio {spec["term"]} ' + ('remoto Brasil' if spec['scope'] == 'remote' else 'Rio de Janeiro RJ')
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            frame = scrape_jobs(site_name=[spec['source']], search_term='estágio ' + spec['term'],
                google_search_term=google_term, location='Brazil' if spec['scope'] == 'remote' else 'Rio de Janeiro, Brazil',
                results_wanted=spec['limit'], distance=5, job_type='internship',
                is_remote=spec['scope'] == 'remote', country_indeed='Brazil',
                linkedin_fetch_description=True, description_format='html', verbose=2)
        allowed = ['title', 'company', 'location', 'job_url', 'job_url_direct', 'is_remote', 'description', 'job_type', 'date_posted']
        rows = json.loads(frame[[c for c in allowed if c in frame.columns]].to_json(orient='records', date_format='iso'))
        result = dict(rows=rows, warnings=list(dict.fromkeys(capture.messages)), query=google_term)
    except Exception as error:
        result = dict(rows=[], warnings=[f'{type(error).__name__}: {error}'], query=google_term)
    print(json.dumps(result, ensure_ascii=True))

if __name__ == '__main__': main()
