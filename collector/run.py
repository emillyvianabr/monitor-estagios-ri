"""Local JobSpy pipeline; does not publish or schedule anything."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time
from normalize import normalize, combine

ROOT = Path(__file__).resolve().parents[1]

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke', action='store_true', help='One RI query per scope and source, up to 5 results each')
    parser.add_argument('--sources', nargs='+', help='Atualizar somente estas fontes; preservar as demais')
    args = parser.parse_args()
    config = json.loads((ROOT / 'jobspy-config.json').read_text(encoding='utf-8'))
    if args.sources and not set(args.sources) <= set(config['sources']):
        parser.error('Fonte não configurada')
    now = datetime.now(timezone.utc).isoformat()
    found, health, audit = [], [], []
    for source in args.sources or config['sources']:
        warnings, count, queries, accepted = [], 0, 0, 0
        terms = ['estágio'] if source in {'gupy', 'ciee', '99jobs'} else (config['terms'][:1] if args.smoke else config['terms'])
        for term in terms:
            for scope in (config['scopes'] if source in {'linkedin', 'indeed'} else ['public']):
                spec = dict(source=source, term=term, scope=scope, smoke=args.smoke, limit=5 if args.smoke else config['resultsPerSearch'])
                if source == '99jobs' and not args.smoke: spec['limit'] = 30
                try:
                    proc = subprocess.run([sys.executable, str(ROOT / 'collector/worker.py'), json.dumps(spec)], capture_output=True, text=True, encoding='utf-8', timeout=config['queryTimeoutSeconds'])
                    if proc.returncode: raise RuntimeError(f'worker terminou com código {proc.returncode}')
                    result = json.loads(proc.stdout)
                except (subprocess.TimeoutExpired, RuntimeError, ValueError) as exc:
                    result = dict(rows=[], warnings=[str(exc)])
                queries += 1
                count += len(result['rows'])
                rejected = Counter()
                for row in result['rows']:
                    job, reason = normalize(row, source, scope, now, config['maxAgeDays'])
                    if job:
                        found.append(job); accepted += 1
                    else: rejected[reason] += 1
                audit.append(dict(source=source, term=term, scope=scope, received=len(result['rows']), rejected=dict(rejected), warnings=result['warnings']))
                print(json.dumps(audit[-1], ensure_ascii=True), flush=True)
                warnings.extend(result['warnings'])
                # Stop this source on warnings (including blocks/parser failures); no bypass/retry.
                if warnings: break
                time.sleep(config['pauseSeconds'])
            if warnings: break
        health.append(dict(board=source, ok=not warnings, listed=count, matches=accepted,
                           note=f'{queries} busca(s), {count} resultado(s), {accepted} candidato(s) ao painel.',
                           error='; '.join(dict.fromkeys(warnings))[:1200] if warnings else None))
    file = ROOT / 'data/jobspy-jobs.json'
    previous_data = json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
    previous = previous_data.get('jobs', [])
    # A smoke test is partial; it must not close entries from a full collection.
    reconciliation_health = [{**h, 'ok': False} for h in health] if args.smoke else health
    jobs = combine(previous, found, reconciliation_health, now)
    if args.sources:
        untouched = {j['url']: j for j in previous if not set(j.get('sources', [j['board']])) & set(args.sources)}
        jobs = [untouched.get(j['url'], j) for j in jobs]
        health.extend({**h, 'note': 'Coleta anterior: ' + (h.get('note') or '')} for h in previous_data.get('health', []) if h['board'] in config['sources'] and h['board'] not in args.sources)
    data = dict(checkedAt=now, engine='Fontes públicas + LinkedIn e Indeed via JobSpy', partial=args.smoke, health=health, jobs=jobs)
    write_json(file, data)
    write_json(ROOT / 'data/jobspy-audit.json', dict(checkedAt=now, queries=audit))
    return 1 if any(not h['ok'] for h in health) else 0

if __name__ == '__main__': sys.exit(run())
