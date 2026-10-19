// Export the editable Markdown through HTML and Chromium print-to-PDF.
import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import { readFile, writeFile, mkdtemp, rm } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';

const require = createRequire(import.meta.url);
const bundled = path.join(os.homedir(), '.cache/codex-runtimes',
  'codex-primary-runtime/dependencies/node/node_modules');
function dependency(name) {
  try { return require(name); }
  catch { return require(path.join(bundled, name)); }
}
const { marked } = dependency('marked');
const { chromium } = dependency('playwright');
const Prism = dependency('prismjs');
dependency('prismjs/components/prism-python');
const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const basename = 'Yunya_Lin_UChicago_Coding_Essay';
const markdown = await readFile(path.join(root, `${basename}.md`), 'utf8');
const codeBlocks = [];
const renderer = new marked.Renderer();
renderer.code = ({ text, lang }) => {
  const language = lang === 'python' ? 'python' : 'text';
  codeBlocks.push(text);
  const content = language === 'python'
    ? Prism.highlight(text, Prism.languages.python, 'python')
    : text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
  return `<pre><code class="language-${language}">${content}</code></pre>\n`;
};
const html = marked.parse(markdown, { gfm: true, renderer });
const css = `
@page { size: Letter; margin: 0.5in 0.75in; }
* { box-sizing: border-box; print-color-adjust: exact; -webkit-print-color-adjust: exact; }
html { color: #000; background: #fff; }
body { margin: 0; font: 10.5pt/1.2 "Times New Roman", Times, serif; }
h1 { font-size: 15pt; line-height: 1.15; text-align: center; margin: 0 0 10pt; }
h2 { font-size: 11.5pt; line-height: 1.15; margin: 9pt 0 4pt; break-after: avoid; }
h3 { font-size: 10.5pt; line-height: 1.15; margin: 8pt 0 4pt; break-after: avoid; }
p { margin: 0 0 7pt; orphans: 2; widows: 2; }
pre { margin: 0; padding: 5pt 7pt; border: 0.5pt solid #ccc;
  background: #f7f7f7; break-inside: avoid; overflow-wrap: normal; }
pre, code { font-family: "Courier New", Courier, monospace; }
pre code { display: block; font-size: 9.25pt; line-height: 10.6pt;
  white-space: pre; color: #000; }
/* Restrained notebook colors; outputs and the analytical figure stay black. */
.token.comment { color: #408080; font-style: italic; }
.token.keyword, .token.boolean { color: #008000; font-weight: bold; }
.token.string, .token.triple-quoted-string { color: #ba2121; }
.token.operator { color: #aa22ff; }
.token.function { color: #0000ff; }
.token.number, .token.builtin { color: #008000; }
.token.punctuation { color: #333; }
pre:has(code.language-text) { background: #fff; border-color: #aaa; }
pre code.language-text { font-size: 9pt; line-height: 10.5pt; }
.page-break { break-after: page; }
.page-break + h2 { margin-top: 0; }
img { display: block; width: 100%; height: auto; margin: 9pt 0 0; }
p:has(img) { margin-bottom: 3pt; break-after: avoid; }
.figure-caption p { font-size: 9.5pt; line-height: 11.5pt; margin: 0 0 7pt; }
.source-note p { font-size: 9.3pt; line-height: 11pt; margin: 0; }
a { color: inherit; text-decoration: none; }
`;
const temp = await mkdtemp(path.join(os.tmpdir(), 'uchicago-markdown-'));
let browser;
try {
  const file = path.join(temp, 'essay.html');
  await writeFile(file, `<!doctype html><html lang="en"><head>
    <meta charset="utf-8"><title>Purchase Conversion by Visitor Type</title>
    <base href="${pathToFileURL(root + path.sep).href}"><style>${css}</style>
    </head><body>${html}</body></html>`);
  const executablePath = chromium.executablePath();
  browser = await chromium.launch({ headless: true,
    ...(existsSync(executablePath) ? { executablePath } : { channel: 'chrome' }) });
  const page = await browser.newPage();
  await page.goto(pathToFileURL(file).href, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  const renderedCode = await page.locator('pre code').allTextContents();
  if (JSON.stringify(renderedCode) !== JSON.stringify(codeBlocks)) {
    throw new Error('Syntax highlighting changed the code or output text');
  }
  const failedImages = await page.locator('img').evaluateAll(images =>
    images.filter(i => !i.complete || !i.naturalWidth).map(i => i.src));
  if (failedImages.length) throw new Error(`Unloaded image: ${failedImages}`);
  const overflowingCode = await page.locator('pre').evaluateAll(blocks =>
    blocks.filter(b => b.scrollWidth > b.clientWidth + 1).length);
  if (overflowingCode) throw new Error('Code exceeds the printable width');
  await page.pdf({ path: path.join(root, `${basename}.pdf`),
    preferCSSPageSize: true, printBackground: true, displayHeaderFooter: true,
    headerTemplate: '<span></span>',
    footerTemplate: '<div style="font-family:Times New Roman;font-size:9pt;'+
      'width:100%;text-align:center;color:black;"><span class="pageNumber"></span></div>' });
  console.log(`Exported ${basename}.md to ${basename}.pdf`);
} finally {
  if (browser) await browser.close();
  await rm(temp, { recursive: true, force: true });
}
