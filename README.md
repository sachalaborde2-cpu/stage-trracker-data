# Internship Scraper — Sacha Laborde

Scraper de stages Front Office (Sales / Trading / Structuring) à Paris et
Londres. Tourne automatiquement toutes les 3h via GitHub Actions (gratuit,
aucun serveur à gérer) et écrit ses résultats dans `offers.json`, lu par
l'onglet "Offres" de l'application de suivi de candidatures.

## Ce qu'il fait, honnêtement

- Respecte le `robots.txt` de chaque site avant de le scraper : si un site
  l'interdit, la source est automatiquement ignorée (pas de contournement).
- Rate-limite ses requêtes (quelques secondes entre chaque appel).
- **Ne touche jamais à LinkedIn** — voir la note dans `config.yaml`.
- Deux sources sont activées par défaut (eFinancialCareers,
  Welcome to the Jungle) car elles agrègent des dizaines d'employeurs en une
  seule page — c'est le meilleur rapport effort/couverture.
- Les sources par banque (Goldman Sachs, JPMorgan, BNP Paribas...) sont
  **désactivées par défaut** dans `config.yaml` (`enabled: false`) : leurs
  sélecteurs CSS sont des points de départ que je n'ai pas pu tester
  (accès réseau restreint depuis mon environnement). Il faut les calibrer
  une par une avant de les activer — voir plus bas.

## Mise en place (une seule fois)

1. Crée un nouveau repo GitHub **public** (public = pas besoin
   d'authentification pour que l'app aille lire `offers.json`).
   Nom suggéré : `stage-tracker-data`.

2. Pousse tous les fichiers de ce dossier dedans :
   ```bash
   cd stage-tracker-data
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<TON_USERNAME>/stage-tracker-data.git
   git push -u origin main
   ```

3. Sur GitHub, va dans l'onglet **Actions** du repo et active les workflows
   si demandé. Le scraper tournera automatiquement toutes les 3h. Tu peux
   aussi le lancer manuellement : onglet Actions → "Scrape internship
   offers" → "Run workflow".

4. Une fois qu'il a tourné au moins une fois, récupère l'URL de ton fichier
   `offers.json` :
   ```
   https://raw.githubusercontent.com/<TON_USERNAME>/stage-tracker-data/main/offers.json
   ```
   Colle cette URL dans l'app (onglet "Offres" → "Configurer la source").

## Calibrer un sélecteur pour une nouvelle banque

Les sites de carrière changent souvent de structure HTML, donc chaque
source par banque doit être calibrée à la main :

1. Ouvre la page de recherche du site dans ton navigateur (ex. la page de
   résultats Goldman Sachs pour "Paris, Internship").
2. Clic droit sur une offre dans les résultats → "Inspecter" (DevTools).
3. Repère l'élément HTML qui englobe UNE offre (souvent une balise
   `<article>`, `<li>`, ou une `<div>` avec une classe/`data-testid`
   explicite) → c'est ton `listing_selector`.
4. À l'intérieur, repère le lien du titre (`title_selector` /
   `link_selector`), et si possible le nom de l'entreprise et la
   localisation.
5. Mets à jour `config.yaml` avec ces sélecteurs et passe `enabled: true`.
6. Lance `python scraper.py` en local pour vérifier que ça remonte des
   résultats cohérents avant de laisser GitHub Actions tourner seul.

Le plus simple et le plus rapide pour cette étape : demande à **Claude
Code** de le faire pour toi (il peut ouvrir le site, inspecter le HTML réel,
écrire les sélecteurs et tester — je ne peux pas le faire moi-même faute
d'accès réseau à ces sites depuis cet environnement).

## Ajouter une nouvelle source

Duplique un bloc dans `sources:` du `config.yaml`, choisis
`aggregator_html` (plusieurs employeurs) ou `company_html` (un seul), et
calibre les sélecteurs comme ci-dessus.

## Cadre légal / éthique — à respecter si tu modifies le scraper

- Toujours vérifier `robots.txt` avant d'ajouter une source (déjà fait
  automatiquement dans le code).
- Ne jamais retirer le rate-limiting.
- Ne jamais scraper LinkedIn, Indeed, ou Glassdoor sans avoir vérifié
  explicitement leurs conditions d'utilisation — ces plateformes sont
  connues pour interdire le scraping et bannir les comptes/IP.
- Usage strictement personnel et non-commercial (recherche de stage pour
  toi-même).
