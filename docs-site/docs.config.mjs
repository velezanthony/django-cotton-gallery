import { defineDocsConfig, NavIcon } from '@velezanthony/design/integration';

const REPO = 'https://github.com/velezanthony/django-cotton-gallery';

/* The pages stay in ../docs, in English only, with the same two sections the MkDocs site had. */
export default defineDocsConfig({
  site: {
    name: 'django-cotton-gallery',
    social: { github: REPO },
    footer: { license: { label: 'MIT', href: `${REPO}/blob/main/LICENSE` } },
    seo: {
      description:
        'Drop-in playground for Django Cotton component libraries — annotated, copy-and-pasteable, themable.',
    },
    // GTM loads only when PUBLIC_GTM_ID is set at build time, as with MkDocs.
    analytics: { privacyUrl: { en: 'https://velezanthony.github.io/en/privacy/' } },
  },
  i18n: { locales: ['en'] },
  content: {
    dir: '../docs',
    repoRoot: '..',
    editUrl: `${REPO}/edit/main`,
    nav: [
      { label: 'Home', slug: 'index' },
      {
        label: 'For users',
        dir: 'users',
        sidebar: ['users/getting-started', 'users/features', 'users/configuration', 'users/annotations'],
      },
      {
        label: 'For contributors',
        dir: 'contributors',
        sidebar: [
          'contributors',
          'contributors/development',
          'contributors/testing',
          'contributors/architecture',
          'contributors/i18n',
          'contributors/release',
        ],
      },
      { label: 'GitHub', href: REPO, icon: NavIcon.GITHUB },
    ],
  },
});
