import unittest
from normalize import normalize, modality, canonical, combine, ACTIVE, PENDING
NOW = '2026-09-23T01:00:00+00:00'
BASE = dict(title='Estágio em Relações Internacionais', company='Empresa teste', location='Rio de Janeiro, RJ, Brazil', job_url='https://www.linkedin.com/jobs/view/estagio-12345?trk=foo', job_type='internship', is_remote=False, description='Cursando Rela&ccedil;&otilde;es Internacionais.', date_posted='2026-09-20')
class Filters(unittest.TestCase):
    def parse(self, **changes): return normalize({**BASE, **changes}, 'linkedin', 'rio', NOW)
    def test_entities(self):
        job, reason = self.parse(); self.assertIsNone(reason); self.assertIn('Relações Internacionais', job['evidence'])
    def test_false_remote_does_not_imply_onsite(self): self.assertEqual(self.parse()[0]['mode'], 'unknown')
    def test_linkedin_misclassified_internship(self):
        job, reason = self.parse(job_type='fulltime', location='Greater Rio de Janeiro',
            description='REDE CIDADÃ Rio de Janeiro-RJ Presencial Área: Administração. Cursando Relações Internacionais.')
        self.assertIsNone(reason)
        self.assertEqual(job['mode'], 'on-site')
        self.assertEqual(job['city'], 'Rio de Janeiro, RJ, Brasil')
    def test_generic_rio_title_does_not_override_city(self):
        self.assertIsNone(self.parse(location='Niterói, RJ, Brazil', description='Rio de Janeiro-RJ Presencial. Relações Internacionais.')[0])
    def test_hybrid_precedes_remote(self): self.assertEqual(modality({**BASE, 'is_remote': True, 'description':'Modelo híbrido, com home office'}), 'hybrid')
    def test_explicit_onsite(self): self.assertEqual(self.parse(description='Modelo presencial. Relações Internacionais.')[0]['mode'], 'on-site')
    def test_other_cities_excluded(self):
        for city in ['Niterói, RJ, Brazil', 'São Paulo, SP, Brazil', 'Greater Rio de Janeiro']: self.assertIsNone(self.parse(location=city)[0])
    def test_brazil_remote(self):
        self.assertEqual(self.parse(location='Brazil', is_remote=True)[0]['mode'], 'remote'); self.assertIsNone(self.parse(location='Lisbon, Portugal', is_remote=True)[0])
    def test_missing_location(self): self.assertIsNone(self.parse(location=None, is_remote=True)[0])
    def test_stale_and_nonintern(self):
        self.assertIsNone(self.parse(date_posted='2025-01-01')[0]); self.assertIsNone(self.parse(title='Analista de RI', job_type='fulltime')[0])
    def test_other_subject(self): self.assertIsNone(self.parse(title='Estágio em Engenharia', description='Cursando Engenharia')[0])
    def test_any_course(self):
        for wording in ['Aceitamos qualquer curso superior.', 'Estudantes de todos os cursos.', 'Cursando graduação em qualquer área.']:
            job, reason = self.parse(title='Programa de estágio', description=wording)
            self.assertIsNone(reason)
            self.assertEqual(job['compatibility'], 'any-course')
    def test_related_does_not_claim_eligibility(self):
        job, reason = self.parse(title='Estágio comercial', description='Cursando Administração ou áreas correlatas.')
        self.assertIsNone(reason)
        self.assertEqual(job['compatibility'], 'related')
        self.assertIn('confirmar', job['relevance'])
    def test_generic_ad_does_not_imply_all_courses(self):
        self.assertIsNone(self.parse(title='Programa de estágio', description='Oportunidades para todos. Cursos gratuitos e benefícios.')[0])
    def test_any_course_keeps_location_rule(self):
        self.assertIsNone(self.parse(title='Programa de estágio', description='Qualquer curso superior', location='São Paulo, SP, Brasil')[0])
    def test_law_in_related_area(self):
        self.assertIsNone(self.parse(title='Estágio em Direito - Comércio Exterior', description='Cursando Direito')[0])
        self.assertIsNotNone(self.parse(title='Estágio em Direito - Comércio Exterior')[0])
    def test_urls(self):
        self.assertEqual(canonical(BASE['job_url']), 'https://www.linkedin.com/jobs/view/12345'); self.assertIsNone(canonical('javascript:alert(1)'))
        self.assertEqual(canonical('https://empresa.gupy.io/jobs/123?jobBoardSource=x'), 'https://empresa.gupy.io/jobs/123')
    def test_dedup_and_failure(self):
        job = self.parse()[0]; old = {**job, 'firstSeen':'2026-09-01'}; other = {**job, 'board':'google','sources':['google']}
        merged = combine([old], [job, other], [], NOW)
        self.assertEqual(len(merged), 1); self.assertEqual(merged[0]['firstSeen'], '2026-09-01'); self.assertEqual(merged[0]['sources'], ['google','linkedin'])
        self.assertEqual(combine([job], [], [], NOW)[0]['status'], PENDING)
        self.assertNotEqual(combine([job], [], [{'board':'linkedin','ok':True}], NOW)[0]['status'], ACTIVE)
if __name__ == '__main__': unittest.main()
