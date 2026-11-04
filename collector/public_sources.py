"""Bounded public listings, without accounts or API keys."""
import json
import re
import time
from urllib.parse import urlsplit, urlencode, quote
import requests
from bs4 import BeautifulSoup
from normalize import text, norm, region, modality


def get(url, params=None):
    response = requests.get(url, params=params, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json,text/html'}, timeout=25)
    response.raise_for_status()
    response.encoding = 'utf-8'
    return response


def gupy_row(j):
    modes = j.get('workplaceTypes') or j.get('workplaceType') or []
    if isinstance(modes, str): modes = [modes]
    mode = next((m for m in ['hybrid', 'remote', 'on-site'] if m in modes), None)
    # O portal público da Gupy só lista vagas no Brasil e não devolve mais o campo country.
    place = [str(j[k]) for k in ['city', 'state'] if j.get(k)]
    country = j.get('country') or 'Brasil'
    return dict(title=j.get('name'), company=j.get('careerPageName'),
                location=', '.join([*place, str(country)]),
                job_url=j.get('jobUrl'), description=j.get('description'),
                job_type='internship' if j.get('type') == 'vacancy_type_internship' else j.get('type'),
                date_posted=j.get('publishedDate'), is_remote=j.get('isRemoteWork') is True or mode == 'remote', explicit_mode=mode)


# A API /api/v1/jobs da Gupy foi desativada (404). A página de busca do portal ainda traz a
# primeira página de resultados embutida em __NEXT_DATA__ (12 por página, paginável com page=N).
GUPY_SEARCH = 'https://portal.gupy.io/job-search/'
# "estagiário" traz ~85 estágios no Rio que "estágio" não traz (a busca casa o título e ignora termos compostos).
GUPY_TERMS = ('estágio', 'estagiário')
GUPY_SCOPES = tuple(scope for term in GUPY_TERMS for scope in (
    {'term': term, 'state': 'Rio de Janeiro', 'city': 'Rio de Janeiro'},
    {'term': term, 'workplaceTypes': 'remote'},
))


def gupy_url(params, page):
    # O portal lê os filtros do CAMINHO (/job-search/term=...&page=2); em query string ele ignora a busca.
    return GUPY_SEARCH + urlencode({**params, 'page': page + 1}, quote_via=quote)


def gupy_page(params, page):
    response = get(gupy_url(params, page))
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', response.text, re.S)
    if not match: raise ValueError('Gupy: __NEXT_DATA__ ausente; verificar estrutura do portal')
    listing = json.loads(match.group(1)).get('props', {}).get('pageProps', {}).get('initialJobList')
    if not isinstance(listing, dict) or not isinstance(listing.get('data'), list):
        raise ValueError('Formato de listagem inesperado')
    return listing['data'], listing.get('pagination') or {}


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
        if source == 'gupy':
            pages = 1 if spec.get('smoke') else 9  # o portal limita o total a ~100 por busca
            seen = set()
            for scope_index, params in enumerate(GUPY_SCOPES):
                for page in range(pages):
                    if page: time.sleep(1)
                    items, pagination = gupy_page(params, page)
                    for j in items:
                        if j.get('id') in seen: continue
                        seen.add(j.get('id'))
                        rows.append(gupy_row(j))
                    limit = pagination.get('limit') or len(items) or 1
                    if len(items) < limit or (pagination.get('offset', 0) + limit) >= (pagination.get('total') or 0): break
                if scope_index + 1 < len(GUPY_SCOPES): time.sleep(1)
        elif source == 'ciee':
            size = 5 if spec.get('smoke') else 500
            pages = 1 if spec.get('smoke') else 12  # a vitrine tem ~3.700 estágios; antes só 300 eram lidos
            for page in range(pages):
                data = get('https://api.ciee.org.br/vagas/vitrine-vaga/publicadas',
                           {'tipoVaga': 'ESTAGIO', 'page': page, 'size': size, 'sort': 'codigoVaga,desc'}).json()
                items = data.get('content')
                if not isinstance(items, list): raise ValueError('Formato de listagem inesperado')
                # nivelEscolar: SU = superior, TE = técnico, EM = médio. Só interessa o nível superior;
                # vagas sem o campo são mantidas, pois ausência de dado não prova que sejam de outro nível.
                rows.extend(ciee_row(j) for j in items if j.get('nivelEscolar') in (None, 'SU'))
                if len(items) < size: break
                if page + 1 < pages: time.sleep(1)
        elif source == '99jobs':
            pages = 1 if spec.get('smoke') else 10
            processed, previous_first = 0, None
            for page in range(1, pages + 1):
                soup = BeautifulSoup(get('https://www.99jobs.com/opportunities/search',
                                         {'search[term]': 'estagio', 'page': page}).text, 'html.parser')
                cards = soup.select('a.opportunity-card')
                if not cards:
                    if page == 1 and not any(t in norm(soup.get_text()) for t in ['nenhuma oportunidade', 'nenhum resultado', 'nao encontramos']):
                        raise ValueError('Lista vazia sem marcador reconhecido; verificar estrutura da 99jobs')
                    break
                first = cards[0].get('href', '')
                if first == previous_first: break  # página repetida: fim da paginação
                previous_first = first
                for card in cards:
                    if processed >= spec['limit']: break
                    processed += 1
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
                if processed >= spec['limit']: break
                time.sleep(1)
        return dict(rows=rows, warnings=[])
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        return dict(rows=rows, warnings=[f'{type(exc).__name__}: {exc}'])
