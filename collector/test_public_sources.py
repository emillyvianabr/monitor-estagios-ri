import unittest
from public_sources import gupy_row, ciee_row
from normalize import normalize, modality

class PublicSources(unittest.TestCase):
    def test_gupy_explicit_hybrid_over_remote_flag(self):
        row = gupy_row({'name': 'Estágio RI', 'workplaceTypes': ['hybrid'], 'isRemoteWork': True})
        self.assertEqual(modality(row), 'hybrid')

    def test_gupy_portal_format_rio_onsite(self):
        # Formato atual do portal: workplaceType (string), sem country.
        row = gupy_row({'name': 'Estágio Comercial', 'workplaceType': 'on-site', 'city': 'Rio de Janeiro',
                        'state': 'Rio de Janeiro', 'type': 'vacancy_type_internship',
                        'jobUrl': 'https://x.gupy.io/job/abc?jobBoardSource=gupy_portal', 'careerPageName': 'X',
                        'publishedDate': '2026-09-20T10:00:00.000Z', 'description': 'Atuação comercial.'})
        self.assertEqual(row['location'], 'Rio de Janeiro, Rio de Janeiro, Brasil')
        job, reason = normalize(row, 'gupy', 'public', '2026-09-23T00:00:00+00:00')
        self.assertIsNone(reason)
        self.assertEqual(job['mode'], 'on-site')
        self.assertNotIn('jobBoardSource', job['url'])

    def test_gupy_portal_format_remote_other_state_kept(self):
        row = gupy_row({'name': 'Estágio em Marketing', 'workplaceType': 'remote', 'city': 'Recife', 'state': 'Pernambuco',
                        'type': 'vacancy_type_internship', 'jobUrl': 'https://x.gupy.io/job/def', 'description': ''})
        job, reason = normalize(row, 'gupy', 'public', '2026-09-23T00:00:00+00:00')
        self.assertIsNone(reason)
        self.assertEqual(job['mode'], 'remote')

    def test_gupy_portal_other_city_onsite_excluded(self):
        row = gupy_row({'name': 'Estágio em Marketing', 'workplaceType': 'on-site', 'city': 'Recife', 'state': 'Pernambuco',
                        'type': 'vacancy_type_internship', 'jobUrl': 'https://x.gupy.io/job/ghi', 'description': ''})
        self.assertIsNone(normalize(row, 'gupy', 'public', '2026-09-23T00:00:00+00:00')[0])

    def test_gupy_page_parses_next_data(self):
        import json
        from unittest import mock
        import public_sources
        html = '<script id="__NEXT_DATA__" type="application/json">' + json.dumps({'props': {'pageProps': {'initialJobList': {
            'data': [{'id': 1}], 'pagination': {'total': 1, 'limit': 12, 'offset': 0}}}}}) + '</script>'
        with mock.patch.object(public_sources, 'get', return_value=mock.Mock(text=html)):
            items, pagination = public_sources.gupy_page({'term': 'estágio'}, 0)
        self.assertEqual(items, [{'id': 1}])
        self.assertEqual(pagination['total'], 1)

    def test_gupy_url_filters_go_in_path(self):
        from public_sources import gupy_url
        url = gupy_url({'term': 'estágio', 'state': 'Rio de Janeiro'}, 1)
        self.assertEqual(url, 'https://portal.gupy.io/job-search/term=est%C3%A1gio&state=Rio%20de%20Janeiro&page=2')
        self.assertNotIn('?', url)

    def test_gupy_page_fails_loudly_when_structure_changes(self):
        from unittest import mock
        import public_sources
        with mock.patch.object(public_sources, 'get', return_value=mock.Mock(text='<html></html>')):
            with self.assertRaises(ValueError):
                public_sources.gupy_page({'term': 'estágio'}, 0)

    def test_ciee_location_and_unknown_mode(self):
        row = ciee_row({'codigoVaga': 123, 'tipoVaga': 'ESTAGIO', 'areaProfissional': 'Relações Internacionais',
                        'local': {'cidade': 'Rio de Janeiro', 'uf': 'RJ'}, 'atividades': ['Apoiar cooperação internacional']})
        job, reason = normalize(row, 'ciee', 'public', '2026-09-23T00:00:00+00:00')
        self.assertIsNone(reason)
        self.assertEqual(job['mode'], 'unknown')
        self.assertIn('codigoVaga=123', job['url'])

    def test_ciee_other_city_excluded(self):
        row = ciee_row({'codigoVaga': 123, 'tipoVaga': 'ESTAGIO', 'areaProfissional': 'Relações Internacionais',
                        'local': {'cidade': 'Niterói', 'uf': 'RJ'}})
        self.assertIsNone(normalize(row, 'ciee', 'public', '2026-09-23T00:00:00+00:00')[0])

    def test_gupy_scopes_cover_both_terms_in_rio_and_remote(self):
        from public_sources import GUPY_SCOPES
        self.assertEqual({s['term'] for s in GUPY_SCOPES}, {'estágio', 'estagiário'})
        self.assertEqual(sum(1 for s in GUPY_SCOPES if s.get('city') == 'Rio de Janeiro'), 2)
        self.assertEqual(sum(1 for s in GUPY_SCOPES if s.get('workplaceTypes') == 'remote'), 2)

    def test_gupy_collect_dedupes_across_terms_and_stops_at_last_page(self):
        from unittest import mock
        import public_sources
        calls = []
        def fake(params, page):
            calls.append((params['term'], page))
            return [{'id': 1, 'name': 'Estágio A'}, {'id': 2, 'name': 'Estágio B'}], {'total': 2, 'limit': 12, 'offset': 0}
        with mock.patch.object(public_sources, 'gupy_page', side_effect=fake), mock.patch.object(public_sources.time, 'sleep'):
            result = public_sources.collect({'source': 'gupy', 'smoke': False, 'limit': 10})
        self.assertEqual(result['warnings'], [])
        self.assertEqual(len(result['rows']), 2)   # mesmas vagas nos 4 recortes: deduplicadas por id
        self.assertEqual(len(calls), 4)            # 1 página por recorte, sem paginar além do total

    def test_ciee_collect_keeps_only_higher_education(self):
        from unittest import mock
        import public_sources
        items = [{'codigoVaga': 1, 'tipoVaga': 'ESTAGIO', 'areaProfissional': 'Administrativa', 'nivelEscolar': 'SU', 'local': {'cidade': 'Rio de Janeiro', 'uf': 'RJ'}},
                 {'codigoVaga': 2, 'tipoVaga': 'ESTAGIO', 'areaProfissional': 'Administrativa - TÉC.', 'nivelEscolar': 'TE', 'local': {'cidade': 'Rio de Janeiro', 'uf': 'RJ'}},
                 {'codigoVaga': 3, 'tipoVaga': 'ESTAGIO', 'areaProfissional': 'Ensino Médio', 'nivelEscolar': 'EM', 'local': {'cidade': 'Rio de Janeiro', 'uf': 'RJ'}},
                 {'codigoVaga': 4, 'tipoVaga': 'ESTAGIO', 'areaProfissional': 'Administrativa', 'local': {'cidade': 'Rio de Janeiro', 'uf': 'RJ'}}]
        with mock.patch.object(public_sources, 'get', return_value=mock.Mock(json=lambda: {'content': items})):
            result = public_sources.collect({'source': 'ciee', 'smoke': True, 'limit': 5})
        self.assertEqual([r['job_url'].split('codigoVaga=')[1].split('&')[0] for r in result['rows']], ['1', '4'])

    def test_ciee_collect_reads_large_pages(self):
        from unittest import mock
        import public_sources
        sizes = []
        def fake_get(url, params=None):
            sizes.append(params['size'])
            return mock.Mock(json=lambda: {'content': []})
        with mock.patch.object(public_sources, 'get', side_effect=fake_get):
            public_sources.collect({'source': 'ciee', 'smoke': False, 'limit': 10})
        self.assertEqual(sizes, [500])

if __name__ == '__main__': unittest.main()
