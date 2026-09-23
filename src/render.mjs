import { readFile, writeFile, rename } from 'node:fs/promises';
export async function render(data) {
  const root = new URL('../', import.meta.url);
  const template = await readFile(new URL('web/template.html', root), 'utf8');
  const json = JSON.stringify(data).replace(/</g, '\\u003c');
  await writeFile(new URL('index.html.tmp', root), template.replace('/*DATA_PLACEHOLDER*/', () => json));
  await rename(new URL('index.html.tmp', root), new URL('index.html', root));
}
