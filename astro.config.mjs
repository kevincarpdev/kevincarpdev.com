// @ts-check
import { defineConfig } from 'astro/config';

// Static one-pager for Hostinger deployment.
// `npm run build` outputs to ./dist — upload that folder to Hostinger public_html.
export default defineConfig({
  site: 'https://kevincarpdev.com',
  output: 'static',
  trailingSlash: 'ignore',
  build: {
    format: 'file', // produces /dist/index.html not /dist/index/index.html
    assets: '_assets',
  },
  // Use Vite's default esbuild CSS minifier — works without extra deps.
});
