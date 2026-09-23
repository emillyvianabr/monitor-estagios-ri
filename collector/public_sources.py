"""Bounded public listings, without accounts or API keys."""
import json
import re
import time
from urllib.parse import urlsplit
import requests
from bs4 import BeautifulSoup
from normalize import text, norm, region, modality


def get(url, params=None):
    response = requests.get(url, params=params, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json,text/html'}, timeout=25)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response


def gupy_row(j):
    modes = j.get('workplaceTypes') or []
    if isinstance(modes, str): modes = [modes]
    mode = next((m for m in ['hybrid', 'remote', 'on-site'] if m in modes), None)
    return dict(title=j.get('name'), company=j.get('careerPageName'),
                location=', '.join(str(j[k]) for k in ['city', 'state', 'country'] if j.get(k)),
                job_url=j.get('jobUrl'), description=j.get('description'),
                job_type='internship' if j.get('type') == 'vacancy_type_internship' else j.get('type'),
                date_posted=j.get('publishedDate'), is_remote=j.get('isRemoteWork') is True, explicit_mode=mode)


def ciee_row(j):
    loc = j.get('local') or {}
    # Only public vacancy fields; no contact or account data.
    body = ' '.join([text(j.get('areaProfissional')), text(j.get('descricao')),
                     *[text(a) for a in j.get('atividades') or []]])
    return dict(title=('Estágio em ' if j.get('tipoVaga') == 'ESTAGIO' else '') + text(j.get('areaProfissional')),
                company=j.get('nomeEmpresa'), description=body,
                location=', '.join([text(loc.get('cidade')), text(loc.get('uf')), 'Brasil']),
                job_type='internship' if j.get('tipoVaga') == 'ESTAGIO' else '',
                job_url='https://ciee.app/login?codigoVaga=' + str(j['codigoVaga']) + '&acesso=VITRINE_VAGA',
                is_remote=False, date_posted=None)


def collect(spec):
    source = spec['source']
    rows = []
    try:
        if source in {'gupy', 'ciee'}:
            size = 5 if spec.get('smoke') else 100
            pages = 1 if spec.get('smoke') else 3
            for page in range(pages):
                if source == 'gupy':
                    data = get('https://employability-portal.gupy.io/api/v1/jobs',
                               {'jobName': 'estágio', 'offset': page * size, 'limit': size}).json()
                    items = data.get('data')
                    adapt = gupy_row
                else:
                    data = get('https://api.ciee.org.br/vagas/vitrine-vaga/publicadas',
                               {'tipoVaga': 'ESTAGIO', 'page': page, 'size': size, 'sort': 'codigoVaga,desc'}).json()
                    items = data.get('content')
                    adapt = ciee_row
                if not isinstance(items, list): raise ValueError('Formato de listagem inesperado')
                rows.extend(adapt(j) for j in items)
                if len(items) < size: break
                if page + 1 < pages: time.sleep(1)
        elif source == '99jobs':
            soup = BeautifulSoup(get('https://www.99jobs.com/opportunities/search',
                                 {'search[term]': 'estagio'}).text, 'html.parser')
            cards = soup.select('a.opportunity-card')
            if not cards and not any(t in norm(soup.get_text()) for t in ['nenhuma oportunidade', 'nenhum resultado', 'nao encontramos']):
                raise ValueError('Lista vazia sem marcador reconhecido; verificar estrutura da 99jobs')
            for card in cards[:spec['limit']]:
                def field(selector):
                    el = card.select_one(selector)
                    return text(el.get_text(' ', strip=True)) if el else ''
                url = card.get('href', '').split('?')[0]
                host = urlsplit(url).hostname or ''
                if not (host == '99jobs.com' or host.endswith('.99jobs.com')): continue
                label = norm(field('.opportunity-label-acting-mode'))
                mode = {'hibrido': 'hybrid', 'remoto': 'remote', 'presencial': 'on-site'}.get(label)
                location = field('.opportunity-address')
                if re.search(r',\s*(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)$', location):
                    location += ', Brasil'
                row = dict(title=field('h1'), company=field('.opportunity-company-infos h2'),
                           location=location, job_url=url,
                           description='', explicit_mode=mode, is_remote=mode == 'remote',
                           job_type='internship' if 'estagio' in norm(field('.opportunity-label-level')) else '', date_posted=None)
                if not region(row, mode or 'unknown'): continue
                detail = BeautifulSoup(get(url).text, 'html.parser')
                for script in detail.select('script[type="application/ld+json"]'):
                    try:
                        obj = json.loads(script.string or script.get_text())
                        objects = obj if isinstance(obj, list) else [obj]
                        for item in objects:
                            if item.get('@type') == 'JobPosting':
                                row.update(title=item.get('title') or row['title'], description=item.get('description') or '', date_posted=item.get('datePosted'))
                    except (ValueError, AttributeError): pass
                if not row['description']:
                    for el in detail(['script', 'style', 'nav', 'footer', 'form']): el.decompose()
                    row['description'] = text(detail.get_text(' ', strip=True))[:20000]
                rows.append(row)
                time.sleep(1)
        return dict(rows=rows, warnings=[])
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return dict(rows=rows, warnings=[f'{type(exc).__name__}: {exc}'])
