import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { render } from './render.mjs';
const root = new URL('../', import.meta.url);
let exitCode = 0;
if (!process.argv.includes('--render-only')) {
  const result = spawnSync(process.env.JOBSPY_PYTHON || 'python', [fileURLToPath(new URL('collector/run.py', root)), ...(process.argv.includes('--smoke') ? ['--smoke'] : [])], { stdio:'inherit', shell:false });
  if (result.error) throw result.error;
  exitCode = result.status ?? 1;
}
const data = JSON.parse(await readFile(new URL('data/jobspy-jobs.json', root), 'utf8'));
await render(data);
const esc = s => String(s ?? 'Não informado').replace(/[\r\n]+/g,' ').replace(/[\\`*_{}\[\]<>()|]/g,'\\$&');
const modes = {remote:'Remoto',hybrid:'Híbrido','on-site':'Presencial',unknown:'Não identificado'};
const active = data.jobs.filter(j=>j.status === 'encontrada na última coleta');
const lines = ['# Radar RI · JobSpy','',`Coleta: ${data.checkedAt}`, '', data.partial ? 'Teste parcial de integração; não representa cobertura completa.' : 'Busca limitada às consultas configuradas; não representa todas as vagas disponíveis.', '', '## Fontes','',...data.health.map(h=>`- ${h.board}: ${h.ok?esc(h.note):'FALHA — '+esc(h.error)}`),'', `## Vagas encontradas (${active.length})`, ''];
for(const j of active)lines.push(`### [${esc(j.title)}](${j.url})`,'',`${esc(j.company)} · ${esc(j.city)} · ${modes[j.mode]}`,'', `${esc(j.relevance)}. Fontes: ${esc(j.sources.join(', '))}.`,'',esc(j.evidence),'');
if(!active.length)lines.push('Nenhuma vaga compatível retornada nas buscas concluídas. Fontes com falha não foram verificadas.','');
await mkdir(new URL('reports/',root),{recursive:true});
await writeFile(new URL('reports/jobspy.md',root),lines.join('\n'));
if(process.env.GITHUB_STEP_SUMMARY)await writeFile(process.env.GITHUB_STEP_SUMMARY,lines.join('\n'));
process.exitCode = exitCode;
