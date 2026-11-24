# Hosting GODSEYE PREDICTIONS as your own private website

The site is one self-contained file: `deploy/index.html` (every weekly build regenerates it:
`python run.py site --season S --week W && cp outputs/site/gods_eye.html deploy/index.html`).
No server code is needed; any static host works. "Private" means a login in front of it.

## Recommended: Cloudflare Pages + Cloudflare Access (free, email login, your own domain)
1. Buy a domain (Cloudflare Registrar sells them at cost, e.g. godseyepredictions.com) or move your DNS to Cloudflare.
2. Cloudflare dashboard → Workers & Pages → Create → Pages → "Upload assets" (drag the `deploy/` folder) → project name `godseye`.
   You get `godseye.pages.dev` immediately; add your custom domain under the project's Custom domains tab.
3. Zero Trust → Access → Applications → Add an application → Self-hosted → domain = your site.
   Policy: Allow → Include → Emails → list the addresses you and your friend use. Everyone else sees a Cloudflare login page.
   Cloudflare emails a one-time code; no passwords to manage.
4. Each week: re-upload `index.html` (or connect the GitHub repo once GitHub access is fixed and pushes auto-deploy).

## Alternatives
- **Netlify**: drag-and-drop deploy; password protection needs the Pro plan.
- **Vercel**: drag-and-drop; "Deployment Protection" password needs Pro.
- **GitHub Pages**: free, but public; not suitable for a private site.
- **Keep the claude.ai artifact**: already private-by-link, updates automatically from here; no custom domain.

## What changes when self-hosted
- Player headshots from nfl.com can be shown (the claude.ai sandbox blocks external images; a normal host does not).
- The file ships with live correlations, intel and probabilities baked in; nothing calls an API from the page.
