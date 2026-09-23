import unittest
from public_sources import gupy_row, ciee_row
from normalize import normalize, modality

class PublicSources(unittest.TestCase):
    def test_gupy_explicit_hybrid_over_remote_flag(self):
        row = gupy_row({'name': 'Estágio RI', 'workplaceTypes': ['hybrid'], 'isRemoteWork': True})
        self.assertEqual(modality(row), 'hybrid')

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

if __name__ == '__main__': unittest.main()
