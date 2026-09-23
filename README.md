# Radar RI — Monitor de estágios

Painel para estudantes de Relações Internacionais, com oportunidades de RI, cursos abertos e áreas afins. Projeto sem chaves de API ou serviços pagos de coleta.

## Colocar no GitHub

1. Extraia o ZIP e envie **o conteúdo da pasta** para a raiz do repositório público, na branch `main`. Não envie apenas o ZIP. Inclua a pasta `.github`, que contém os workflows. `package.json` e `index.html` devem estar na raiz.
2. Em **Settings → Actions → General → Workflow permissions**, permita **Read and write permissions**, se necessário. Regras de proteção da branch podem impedir a gravação automática.
3. Para o site, escolha **Settings → Pages → Source → GitHub Actions**. O pacote já contém o workflow; não precisa criar outro.
4. Em **Actions → Monitor semanal RI → Run workflow**, execute a primeira coleta com os filtros ampliados.
5. Ao terminar, **Publicar painel** publica o HTML atualizado. Também é possível executá-lo manualmente. Se a primeira publicação falhar antes de ativar Pages, execute-a novamente após o passo 3.

O monitor está configurado para segunda-feira às **09:23 de Brasília** (12:23 UTC). O GitHub pode atrasar execuções e desativar agendamentos de repositórios públicos inativos. A execução manual permanece disponível. Nenhum workflow foi publicado ou executado pelo assistente; a ativação ocorre quando você subir os arquivos e habilitar os recursos.

Não é preciso cadastrar API keys ou tokens pessoais. O GitHub fornece o token usado pelo workflow para salvar resultados.

## Fontes e cobertura

- **LinkedIn:** JobSpy, termos configurados em `jobspy-config.json`, dois recortes (Rio e remoto Brasil), até 10 resultados por busca.
- **Gupy:** consulta pública por estágio, até 3 páginas de 100 resultados.
- **CIEE:** vitrine pública de estágio, até 3 páginas de 100 resultados. Os links de candidatura podem exigir login. Modalidade nem sempre está disponível.
- **99jobs:** primeira página da busca por estágio, até 30 cartões; lê detalhes apenas quando a localização está no recorte.

Google Jobs está desativado. Nube, Cia de Talentos e Prefeitura não fazem parte desta versão.

A coleta é limitada, não exaustiva. Uma fonte responder sem anúncios compatíveis não significa que não há vagas nela. Mudanças de página e bloqueios podem causar falhas, apresentadas no painel. Nenhum contorno de CAPTCHA ou autenticação é usado.

## Filtros

Presencial, híbrido e modalidade não identificada: **município do Rio de Janeiro**. Remoto: localização identificada no Brasil; confira restrições adicionais no anúncio. `is_remote=false` não comprova presencial.

Compatibilidade:
- **RI mencionada:** o anúncio cita o curso, mas os demais requisitos precisam ser conferidos.
- **Todos os cursos:** há indicação explícita de curso livre/qualquer graduação.
- **Área afim:** administrativo, comercial, marketing, logística, compras, sustentabilidade, economia, gestão de projetos e áreas semelhantes. Não confirma aceitação de RI.

Anúncios precisam ser identificados como estágio. Bancos de talentos são excluídos. Datas conhecidas fora de 45 dias são descartadas; anúncios sem data permanecem para conferência. Modalidade explícita da fonte tem prioridade.

## Dados incluídos

O pacote traz **4 anúncios da coleta anterior** para o painel abrir imediatamente. A busca ampliada para todos os cursos e áreas afins ainda não foi executada. Use a primeira execução manual para atualizar.

Histórico e relatório ficam em `data/jobspy-jobs.json`, `data/jobspy-audit.json` e `reports/jobspy.md`. Os nomes são mantidos por compatibilidade, mas abrangem as cinco fontes. Anúncios são deduplicados por URL; anúncios equivalentes com links diferentes podem continuar separados. Ausência na coleta não comprova encerramento. Atualizações parciais conservam dados das fontes não consultadas.

## Executar localmente

Requer Python 3.12 e Node.js 22 ou superior.

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
npm test
npm run monitor
```

Abra `index.html` no navegador. Não há dependências npm a instalar.

- `npm run smoke`: teste reduzido; não representa uma coleta completa.
- `python collector/run.py --sources gupy 99jobs ciee`: atualiza só as fontes indicadas.
- `node src/jobspy-report.mjs --render-only`: gera HTML e relatório sem consultar sites.
- `JOBSPY_PYTHON`: variável opcional com caminho do Python para o comando Node.

O monitor gera relatório mesmo quando uma fonte falha e termina com erro para sinalizar cobertura incompleta. O workflow salva os resultados disponíveis e o painel exibe falhas. O workflow Pages publica apenas o HTML, não o código nem o histórico completo.

## Verificação e referências

21 testes Python passaram localmente; as cinco fontes foram consultadas. Execução no GitHub e publicação Pages ainda precisam ser validadas no seu repositório.

- JobSpy: https://github.com/speedyapply/JobSpy
- Referência da consulta pública Gupy: https://github.com/DouglasFantoni/gupy-job-scrapper
- GitHub Pages: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site
- Execução manual: https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow

## Busca por título no LinkedIn

As buscas incluem estágio nas palavras-chave, sem exigir o tipo internship cadastrado no LinkedIn. O filtro local aceita título de estágio mesmo com categoria Full-time. Uma localização genérica Greater Rio de Janeiro só é resolvida para o município quando a descrição informa explicitamente Rio de Janeiro-RJ junto da modalidade. O anúncio 4468536717 passou nesse teste local usando o conteúdo público previamente obtido; isso não garante sua posição ou retorno na busca limitada do LinkedIn.

## Indeed

Indeed está integrado via JobSpy, com country_indeed=Brazil e os mesmos termos e recortes do LinkedIn. Busca por palavras-chave sem exigir categoria internship; o filtro local confirma estágio pelo título ou tipo informado. O teste inicial consulta até 5 resultados por recorte. A execução semanal faz a coleta configurada completa. A busca pode devolver cargos efetivos, que são descartados localmente. Não requer conta nem chave de API.
