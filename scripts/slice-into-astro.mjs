#!/usr/bin/env node
/**
 * One-shot slicer: reads index.html and splits it into Astro components
 * under src/components/ + src/styles/global.css + src/pages/index.astro
 *
 * Section boundaries are detected by the comment markers ("═══════════ X ═══════════")
 * that already exist in the source file.
 */

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');

const src = readFileSync(resolve(ROOT, 'index.html'), 'utf8');

// ── Extract <style> block ────────────────────────────────────────
const styleMatch = src.match(/<style>([\s\S]*?)<\/style>/);
if (!styleMatch) throw new Error('Could not find <style> block');
const styleBody = styleMatch[1].trim();

// ── Extract trailing <script> block ──────────────────────────────
const scriptMatch = src.match(/<script>([\s\S]*?)<\/script>\s*<\/body>/);
if (!scriptMatch) throw new Error('Could not find trailing <script>');
const scriptBody = scriptMatch[1].trim();

// ── Extract <head> meta + font links ────────────────────────────
const headInner = src.match(/<head>([\s\S]*?)<\/head>/)[1];
const fontLinks = [...headInner.matchAll(/<link\s+[^>]+>/g)].map(m => m[0]).join('\n');
const metaDesc = headInner.match(/<meta name="description"[^>]+>/)?.[0] ?? '';

// ── Slice body by section comment markers ───────────────────────
const body = src.match(/<body>([\s\S]*?)<\/body>/)[1];

// Each section starts with: <!-- ═══════════ TITLE ═══════════ -->
// and ends just before the next such marker (or </main> / </body>).
function sliceByMarker(label, start, end) {
  const startIdx = body.indexOf(start);
  if (startIdx < 0) throw new Error(`Missing start marker for ${label}: ${start}`);
  let endIdx;
  if (end === '__EOF__') endIdx = body.length;
  else {
    endIdx = body.indexOf(end, startIdx + start.length);
    if (endIdx < 0) throw new Error(`Missing end marker for ${label}: ${end}`);
  }
  return body.slice(startIdx, endIdx).trim();
}

const M = {
  nav:        '<!-- ═══════════ NAV ═══════════ -->',
  hero:       '<!-- ═══════════ HERO ═══════════ -->',
  skillband:  '<!-- ═══════════ SKILL BANNER · full-width, sits at 100vh cutoff ═══════════ -->',
  about:      '<!-- ═══════════ ABOUT / EXPERTISE ═══════════ -->',
  work:       '<!-- ═══════════ CASE STUDIES ═══════════ -->',
  stack:      '<!-- ═══════════ STACK MATRIX ═══════════ -->',
  experience: '<!-- ═══════════ EXPERIENCE LEDGER ═══════════ -->',
  timeline:   '<!-- ═══════════ TIMELINE ═══════════ -->',
  contact:    '<!-- ═══════════ CONTACT ═══════════ -->',
  footer:     '<!-- ═══════════ FOOTER ═══════════ -->',
};

const sections = {
  Nav:        sliceByMarker('Nav',        M.nav,        '<main id="top">'),
  Hero:       sliceByMarker('Hero',       M.hero,       M.skillband),
  SkillBand:  sliceByMarker('SkillBand',  M.skillband,  M.about),
  About:      sliceByMarker('About',      M.about,      M.work),
  Work:       sliceByMarker('Work',       M.work,       M.stack),
  Stack:      sliceByMarker('Stack',      M.stack,      M.experience),
  Experience: sliceByMarker('Experience', M.experience, M.timeline),
  Timeline:   sliceByMarker('Timeline',   M.timeline,   M.contact),
  Contact:    sliceByMarker('Contact',    M.contact,    '</main>'),
  Footer:     sliceByMarker('Footer',     M.footer,     '<script>'),
};

// ── Write global CSS ────────────────────────────────────────────
mkdirSync(resolve(ROOT, 'src/styles'), { recursive: true });
writeFileSync(resolve(ROOT, 'src/styles/global.css'), styleBody + '\n');

// ── Write components ────────────────────────────────────────────
mkdirSync(resolve(ROOT, 'src/components'), { recursive: true });
for (const [name, html] of Object.entries(sections)) {
  // Inject mobile-drawer <aside> into Nav component (it sits between </header> and <main>)
  let body = html;
  if (name === 'Nav') {
    const drawerMatch = src.match(/<aside class="nav__drawer"[\s\S]*?<\/aside>/);
    if (drawerMatch) body += '\n\n' + drawerMatch[0];
  }
  writeFileSync(resolve(ROOT, `src/components/${name}.astro`), `---\n// ${name} section — extracted from legacy index.html on ${new Date().toISOString().slice(0,10)}\n---\n${body}\n`);
}

// ── Write Scripts component (just the inline behavior script) ───
writeFileSync(
  resolve(ROOT, 'src/components/Scripts.astro'),
  `---\n// Inline behavior: nav scroll state, mobile drawer, stack filter, reveal-on-scroll.\n---\n<script is:inline>\n${scriptBody}\n</script>\n`
);

// ── Write src/pages/index.astro ─────────────────────────────────
mkdirSync(resolve(ROOT, 'src/pages'), { recursive: true });
const indexAstro = `---
import '../styles/global.css';
import Nav from '../components/Nav.astro';
import Hero from '../components/Hero.astro';
import SkillBand from '../components/SkillBand.astro';
import About from '../components/About.astro';
import Work from '../components/Work.astro';
import Stack from '../components/Stack.astro';
import Experience from '../components/Experience.astro';
import Timeline from '../components/Timeline.astro';
import Contact from '../components/Contact.astro';
import Footer from '../components/Footer.astro';
import Scripts from '../components/Scripts.astro';
---
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Kevin Carpenter — Senior Full-Stack Architect</title>
${metaDesc}
${fontLinks}
</head>
<body>
<Nav />
<main id="top">
  <Hero />
  <SkillBand />
  <About />
  <Work />
  <Stack />
  <Experience />
  <Timeline />
  <Contact />
</main>
<Footer />
<Scripts />
</body>
</html>
`;
writeFileSync(resolve(ROOT, 'src/pages/index.astro'), indexAstro);

console.log('✔ Sliced index.html into:');
console.log('  src/styles/global.css');
for (const name of Object.keys(sections)) console.log(`  src/components/${name}.astro`);
console.log('  src/components/Scripts.astro');
console.log('  src/pages/index.astro');
