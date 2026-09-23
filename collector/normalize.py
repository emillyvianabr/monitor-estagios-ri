"""Conservative filters; absence of data is never evidence of on-site work."""
import re
import html
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

ACTIVE = 'encontrada na última coleta'
PENDING = 'verificação pendente'

def text(value):
    value = html.unescape(html.unescape(str(value or '')))
    value = re.sub(r'<[^>]+>', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()

def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD', text(value).lower()) if unicodedata.category(c) != 'Mn')

def canonical(value):
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            return None
        if url.hostname == 'linkedin.com' or url.hostname.endswith('.linkedin.com'):
            match = re.search(r'/jobs/view/(?:[^/]*-)?(\d+)/?$', url.path)
            if match:
                return 'https://www.linkedin.com/jobs/view/' + match.group(1)
        query = [(k, v) for k, v in parse_qsl(url.query) if not k.lower().startswith('utm_') and k.lower() not in {'trk', 'trackingid', 'refid', 'jobboardsource'}]
        return urlunsplit((url.scheme, url.netloc.lower(), url.path.rstrip('/'), urlencode(query), ''))
    except (TypeError, ValueError):
        return None

def modality(row):
    if row.get('explicit_mode') in {'remote', 'hybrid', 'on-site'}:
        return row['explicit_mode']
    title = norm(row.get('title'))
    body = norm(row.get('description'))
    hybrid = bool(re.search(r'\b(?:hibrid[oa]|hybrid)\b', title + ' ' + body))
    if hybrid:
        return 'hybrid'
    remote = row.get('is_remote') is True or bool(re.search(r'\b(?:100% remoto|100% remota|fully remote|trabalho remoto|modelo remoto|modalidade remota|home office)\b', title + ' ' + body))
    onsite = bool(re.search(r'\b(?:presencial|on-site|onsite)\b', title) or re.search(r'\b(?:modelo|trabalho|atuacao|modalidade)\s*(?:de trabalho)?\s*[:\-]?\s*presencial\b', body))
    if remote and onsite:
        return 'unknown'
    if remote:
        return 'remote'
    if onsite:
        return 'on-site'
    return 'unknown'

def region(row, mode):
    loc = norm(row.get('location'))
    brazil = bool(re.search(r'\b(?:brazil|brasil)\b', loc))
    # JobSpy commonly returns "Rio de Janeiro, RJ, BR" as well.
    if loc.endswith(', br'):
        brazil = True
    rio = bool(re.fullmatch(r'rio de janeiro\s*[,\-]\s*(?:rj|rio de janeiro)(?:\s*,\s*(?:brasil|brazil|br))?', loc))
    rio = rio or loc in {'rio de janeiro, brazil', 'rio de janeiro, brasil'}
    return (brazil or rio) if mode == 'remote' else rio

def compatibility(title, body):
    combined = norm(title + ' ' + body)
    if re.search(r'\b(?:relacoes internacionais|international relations)\b', combined):
        return 'requirements', 'RI mencionada no anúncio — conferir requisitos', 'relacoes internacionais'
    any_course = re.search(r'\b(?:qualquer curso(?: superior)?|(?:todos os|todas as) cursos|todas as (?:areas de (?:formacao|conhecimento)|graduacoes)|(?:curso superior|graduacao|ensino superior) (?:completo ou cursando |cursando )?em qualquer area|independentemente (?:do curso|da (?:area de )?formacao))\b', combined)
    if any_course and not re.search(r'\b(?:nao aceitamos|nao aceita|nao e para)\s+' + re.escape(any_course.group()), combined):
        return 'any-course', 'Todos os cursos — conferir demais requisitos', any_course.group()
    if re.search(r'\bestagio (?:em|de) (?:direito|engenharia|enfermagem|medicina|educacao fisica)\b', norm(title)):
        return None, None, None
    close = ['comercio exterior', 'comex', 'cooperacao internacional', 'relacoes governamentais', 'relacoes institucionais', 'negocios internacionais']
    for term in close:
        if re.search(r'\b' + term + r'\b', combined):
            return 'related', 'Área afim — confirmar se aceita RI', term
    broader = r'administrativ[oa]|administracao|comercial|marketing|logistica|suprimentos|compras|sustentabilidade|esg|politicas publicas|ciencias (?:humanas|sociais)|economia|gestao de projetos'
    match = re.search(r'\b(?:' + broader + r')\b', norm(title))
    if not match:
        match = re.search(r'\b(?:cursando|estudantes? de|graduacao em|cursos? de|formacao em)\s+(?:' + broader + r')\b', norm(body))
    if match:
        return 'related', 'Área afim — confirmar se aceita RI', match.group()
    return None, None, None

def normalize(row, source, scope, now, max_age=45):
    row = dict(row)
    # Resolve only a broad Rio location, with city AND modality together in the ad.
    # A title mentioning Rio alone does not prove the municipality.
    if norm(row.get('location')) in {'greater rio de janeiro', 'regiao metropolitana do rio de janeiro'}:
        place = re.search(r'\brio de janeiro\s*[-/,]\s*rj\s*[-|:]?\s*(presencial|hibrido|remoto)\b', norm(row.get('description')))
        if place:
            row['location'] = 'Rio de Janeiro, RJ, Brasil'
            row['explicit_mode'] = {'presencial': 'on-site', 'hibrido': 'hybrid', 'remoto': 'remote'}[place.group(1)]
    title = text(row.get('title'))
    body = text(row.get('description'))
    title_n, body_n = norm(title), norm(body)
    if not re.search(r'\bestagi(?:o|ari[oa]s?)\b|\bintern(?:ship)?\b', title_n) and 'internship' not in norm(row.get('job_type')):
        return None, 'não confirmado como estágio'
    if re.search(r'\b(?:banco de talentos|talent pool)\b', title_n):
        return None, 'banco de talentos'
    category, relevance, matched = compatibility(title, body)
    if not category:
        return None, 'sem evidência de RI, cursos abertos ou área afim'
    mode = modality(row)
    if not region(row, mode):
        return None, 'localização ou modalidade fora do recorte/insuficiente'
    posted = row.get('date_posted')
    if posted:
        try:
            age = (datetime.fromisoformat(now).date() - datetime.fromisoformat(str(posted).replace('Z', '+00:00')).date()).days
            if age > max_age or age < -1:
                return None, 'data fora da janela'
        except ValueError:
            posted = None
    url = canonical(row.get('job_url_direct') or row.get('job_url'))
    if not url:
        return None, 'link inválido'
    evidence = body[:450] if body else 'Descrição indisponível. Confira requisitos e curso aceito no anúncio.'
    hit = body_n.find(matched)
    if hit >= 0:
        evidence = ('…' if hit > 80 else '') + body[max(0, hit - 80):hit + 370]
    return dict(url=url, board=source, sources=[source], sourceUrls=[canonical(row.get('job_url')) or url],
                title=title, company=text(row.get('company')) or 'Empresa não informada',
                city=text(row.get('location')), state='', mode=mode, relevance=relevance, compatibility=category,
                deadline=None, published=posted, evidence=evidence, firstSeen=now, lastSeen=now,
                status=ACTIVE, searchScopes=[scope]), None

def combine(previous, found, health, now):
    successful = {h['board'] for h in health if h['ok']}
    merged = {j['url']: {**j, 'status': 'não encontrada na última coleta' if set(j.get('sources', [j['board']])) <= successful else PENDING} for j in previous}
    for job in found:
        old = merged.get(job['url'])
        if old:
            job = {**job, 'firstSeen': old['firstSeen'], 'sources': sorted(set(old.get('sources', [old['board']]) + job['sources'])), 'sourceUrls': sorted(set(old.get('sourceUrls', [old['url']]) + job['sourceUrls']))}
        merged[job['url']] = job
    return sorted(merged.values(), key=lambda j: j['firstSeen'], reverse=True)
