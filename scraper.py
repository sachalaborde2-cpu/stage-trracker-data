#!/usr/bin/env python3
"""
Scraper de stages Front Office (Sales / Trading / Structuring) — Paris & London
Sacha Laborde

Respecte robots.txt de chaque source, rate-limite ses requêtes, et NE scrape
JAMAIS LinkedIn (violation de ses CGU). Conçu pour tourner via GitHub Actions
toutes les quelques heures (voir .github/workflows/scrape.yml).

Usage: python scraper.py
"""
import json
import time
import hashlib
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib import robotparser

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "config.yaml"

# Reconnaît les URLs d'offres eFinancialCareers, ex:
# https://www.efinancialcareers.com/jobs-United_Kingdom-London-Some_Title.id24522970
EFC_JOB_URL_RE = re.compile(
    r'href="(https://www\.efinancialcareers\.(?:com|fr|co\.uk)'
    r'/jobs-([A-Za-z_]+)-([A-Za-z_\.]+)-([\w\-\.]+?)\.id(\d+))"[^>]*>'
    r'([^<]{3,200})</a>'
)


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_existing(output_path):
    if output_path.exists():
        try:
            return json.loads(output_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"[warn] {output_path} illisible, on repart de zéro.")
    return []


def offer_id(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def robots_allowed(url, user_agent):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = robotparser.RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception as e:
        print(f"[warn] robots.txt illisible pour {robots_url} ({e}) — source ignorée par prudence.")
        return False


def text_matches(haystack, needles):
    h = haystack.lower()
    return any(n.lower() in h for n in needles)


def passes_filters(title, location, config):
    combined = f"{title} {location}"
    if not text_matches(combined, config["role_keywords"]):
        return False
    if not text_matches(combined, config["contract_keywords"]):
        return False
    if not text_matches(combined, config["location_keywords"]):
        return False
    if text_matches(combined, config["exclude_keywords"]):
        return False
    return True


def scrape_efinancialcareers(source, config, session):
    """
    eFinancialCareers encode le pays et la ville directement dans l'URL de
    chaque offre (ex: /jobs-United_Kingdom-London-Titre.id123456), ce qui
    est BEAUCOUP plus fiable que de deviner des classes CSS (qui changent
    souvent). On extrait donc les offres par pattern d'URL plutôt que par
    sélecteur — la localisation vient directement de l'URL (fiable à 100%),
    le titre vient du texte du lien. Le nom de l'entreprise est en
    best-effort (cf. README, à calibrer si besoin avec du HTML réel).
    """
    results = []
    urls_to_try = [source["search_url"]]
    if source.get("search_url_alt"):
        urls_to_try.append(source["search_url_alt"])

    for url in urls_to_try:
        if source.get("respect_robots_txt", True):
            if not robots_allowed(url, config["user_agent"]):
                print(f"[skip] {source['name']}: robots.txt interdit {url}")
                continue
        try:
            resp = session.get(url, headers={"User-Agent": config["user_agent"]}, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[error] {source['name']}: échec de la requête ({e})")
            continue

        matches = EFC_JOB_URL_RE.findall(resp.text)
        print(f"[info] {source['name']}: {len(matches)} lien(s) d'offre brut(s) détecté(s) sur {url}")

        seen_ids = {}
        for full_url, country_slug, city_slug, title_slug, job_id, link_text in matches:
            link_text = link_text.strip()
            if link_text.lower() in ("apply now", "save", "postuler", ""):
                continue  # doublon du même lien (bouton "Apply now"), on garde la version avec le vrai titre
            if job_id in seen_ids:
                continue
            seen_ids[job_id] = True

            location = f"{city_slug.replace('_', ' ')}, {country_slug.replace('_', ' ')}"
            title = link_text

            # Company: best-effort — cherche un tag <img alt="..."> juste avant
            # le lien dans le HTML brut (les logos d'entreprise précèdent
            # généralement le titre dans ces listes). Si rien de trouvé,
            # on laisse vide plutôt que d'inventer.
            company = ""
            idx = resp.text.find(full_url)
            if idx != -1:
                snippet_before = resp.text[max(0, idx - 400):idx]
                alt_matches = re.findall(r'alt="([^"]{2,60})"', snippet_before)
                generic = {"logo", "company logo", "", "icon"}
                candidates = [a for a in alt_matches if a.strip().lower() not in generic]
                if candidates:
                    company = candidates[-1].strip()

            if not passes_filters(title, location, config):
                continue

            results.append({
                "id": offer_id(full_url),
                "company": company or "(voir l'offre)",
                "title": title,
                "location": location,
                "url": full_url,
                "source": source["name"],
            })

        time.sleep(source.get("rate_limit_seconds", 3))

    return results



    """Retourne une liste de dicts offre pour une source donnée. Ne lève
    jamais d'exception vers l'appelant — une source en échec est juste
    loguée et ignorée, pour ne pas casser tout le run."""
    results = []
    urls_to_try = [source["search_url"]]
    if source.get("search_url_alt"):
        urls_to_try.append(source["search_url_alt"])

    for url in urls_to_try:
        if source.get("respect_robots_txt", True):
            if not robots_allowed(url, config["user_agent"]):
                print(f"[skip] {source['name']}: robots.txt interdit {url}")
                continue

        try:
            resp = session.get(url, headers={"User-Agent": config["user_agent"]}, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[error] {source['name']}: échec de la requête ({e})")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(source["listing_selector"])
        print(f"[info] {source['name']}: {len(cards)} carte(s) brute(s) trouvée(s) sur {url}")

        for card in cards:
            try:
                title_el = card.select_one(source["title_selector"])
                link_el = card.select_one(source["link_selector"])
                if not title_el or not link_el:
                    continue
                title = title_el.get_text(strip=True)
                href = link_el.get("href", "")
                if not href:
                    continue
                full_url = urljoin(url, href)

                company = source["name"]
                if source.get("company_selector"):
                    company_el = card.select_one(source["company_selector"])
                    if company_el:
                        company = company_el.get_text(strip=True)

                location = ""
                if source.get("location_selector"):
                    loc_el = card.select_one(source["location_selector"])
                    if loc_el:
                        location = loc_el.get_text(strip=True)

                if not passes_filters(title, location, config):
                    continue

                results.append({
                    "id": offer_id(full_url),
                    "company": company,
                    "title": title,
                    "location": location or "Paris/London",
                    "url": full_url,
                    "source": source["name"],
                })
            except Exception as e:
                print(f"[warn] {source['name']}: carte ignorée ({e})")
                continue

        time.sleep(source.get("rate_limit_seconds", 3))

    return results


def main():
    config = load_config()
    output_path = ROOT / config["output_file"]
    existing = load_existing(output_path)
    existing_by_id = {o["id"]: o for o in existing}

    session = requests.Session()
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    all_new = []
    for source in config["sources"]:
        if not source.get("enabled", False):
            print(f"[skip] {source['name']}: désactivée dans config.yaml")
            continue
        print(f"\n=== Source: {source['name']} ===")
        if source.get("type") == "efc_regex":
            found = scrape_efinancialcareers(source, config, session)
        else:
            found = scrape_source(source, config, session)
        print(f"[info] {source['name']}: {len(found)} offre(s) matchant les critères")
        all_new.extend(found)

    # Fusion : on garde firstSeen pour les offres déjà connues, on ajoute
    # scrapedAt = date du run pour toutes (permet de trier par fraîcheur).
    merged = dict(existing_by_id)
    for offer in all_new:
        if offer["id"] in merged:
            offer["firstSeen"] = merged[offer["id"]].get("firstSeen", now_iso)
        else:
            offer["firstSeen"] = now_iso
        offer["scrapedAt"] = now_iso
        merged[offer["id"]] = offer

    # Purge des offres trop anciennes (plus vues depuis max_age_days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=config["max_age_days"])
    final_list = [
        o for o in merged.values()
        if datetime.strptime(o.get("scrapedAt", now_iso), "%Y-%m-%d").replace(tzinfo=timezone.utc) >= cutoff
    ]
    final_list.sort(key=lambda o: o.get("scrapedAt", ""), reverse=True)

    output_path.write_text(json.dumps(final_list, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] {len(final_list)} offre(s) au total dans {output_path.name}")


if __name__ == "__main__":
    main()
