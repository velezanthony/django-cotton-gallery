import { defineDocsSite } from '@velezanthony/design/integration';
import docsConfig from './docs.config.mjs';

// Published as a GitHub Pages project site, under /django-cotton-gallery.
export default defineDocsSite(docsConfig, {
  base: '/django-cotton-gallery',
  site: 'https://velezanthony.github.io',
});
