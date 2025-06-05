
import aiohttp
import asyncio
import aiofile
import os
import json
from bs4 import BeautifulSoup
import re

BASE_URL = "https://pocket.limitlesstcg.com"
PROXY = "http://ocytohe.univ-ubs.fr:3128"
HEADERS = {'User-Agent': 'Mozilla/5.0'}

EXTENSIONS = [
    "/cards/A3", "/cards/A2b", "/cards/A2a", "/cards/A2",
    "/cards/A1a", "/cards/A1", "/cards/P-A"
]

async def fetch_soup(session, url):
    async with session.get(url, headers=HEADERS, proxy=PROXY) as resp:
        html = await resp.text()
    return BeautifulSoup(html, "html.parser")

async def extract_card_urls(session, extension_url):
    soup = await fetch_soup(session, extension_url)
    return [a["href"] for a in soup.select(f"a[href^='{extension_url}/']") if a.has_attr("href")]

async def extract_card_details(session, card_url):
    soup = await fetch_soup(session, card_url)

    def get_text(selector, class_name):
        tag = soup.find(selector, class_=class_name)
        return tag.text.strip().replace("\n", " ").replace("\r", " ") if tag else ""

    name = get_text("span", "card-text-name")
    raw_type = get_text("p", "card-text-type")
    if " - " in raw_type:
        card_type, raw_stage = raw_type.split(" - ", 1)
    else:
        card_type = raw_type
        raw_stage = ""

    stage_match = re.search(r"(Basic|Stage 1|Stage 2)", raw_stage)
    evolves_match = re.search(r"Evolves from\s+(.*)", raw_stage)
    stage = stage_match.group(1) if stage_match else ""
    evolves_from = evolves_match.group(1).strip() if evolves_match else ""

    raw_info = get_text("p", "card-text-title")
    parts = [p.strip() for p in raw_info.split(" - ")]
    element_type = parts[1] if len(parts) > 1 else ""
    hp = parts[2].replace("HP", "").strip() if len(parts) > 2 else ""

    attack_block = get_text("p", "card-text-attack-info")
    if "\n" in attack_block:
        attack = attack_block.split("\n", 1)[1].strip()
    else:
        attack = attack_block.strip()
    attack = re.sub(r"^\s*\S+\s+", "", attack)

    attack_effect = get_text("p", "card-text-attack-effect")

    # Ability
    ability_name = get_text("p", "card-text-ability-info").replace("Ability:", "").strip()
    ability_effect = get_text("p", "card-text-ability-effect")

    # Weakness & Retreat
    weakness, retreat = "", ""
    wr_tag = soup.find("p", class_="card-text-wrr")
    if wr_tag:
        wr_lines = list(wr_tag.stripped_strings)
        for line in wr_lines:
            if "Weakness:" in line:
                weakness = line.replace("Weakness:", "").strip()
            elif "Retreat:" in line:
                retreat = line.replace("Retreat:", "").strip()

    # Extension (set name)
    ext_div = soup.find("div", class_="prints-current-details")
    extension = ext_div.find("span", class_="text-lg").text.strip() if ext_div else ""

    artist_tag = soup.find("div", class_="card-text-section card-text-artist")
    illustrator = artist_tag.text.strip().replace("Illustrated by", "").strip() if artist_tag else ""
    flavor_tag = soup.find("div", class_="card-text-section card-text-flavor")
    flavor_text = flavor_tag.text.strip() if flavor_tag else ""

    return {
        "full_url": BASE_URL + card_url,
        "name": name,
        "card_type": card_type.strip(),
        "stage": stage,
        "evolves_from": evolves_from,
        "element_type": element_type,
        "hp": hp,
        "attack": attack,
        "attack_effect": attack_effect,
        "ability": ability_name,
        "ability_effect": ability_effect,
        "weakness": weakness,
        "retreat": retreat,
        "illustrator": illustrator,
        "flavor_text": flavor_text,
        "extension": extension
    }

async def main():
    connector = aiohttp.TCPConnector(limit=10)
    all_cards = []

    async with aiohttp.ClientSession(base_url=BASE_URL, connector=connector) as session:
        for ext in EXTENSIONS:
            print(f"🔍 Extension : {ext}")
            card_urls = await extract_card_urls(session, ext)
            print(f"  → {len(card_urls)} cartes détectées")
            details = await asyncio.gather(*[extract_card_details(session, url) for url in card_urls])
            all_cards.extend(details)

    os.makedirs("output", exist_ok=True)
    async with aiofile.async_open("output/all_cards.json", "w", encoding="utf-8") as f:
        await f.write(json.dumps(all_cards, ensure_ascii=False, indent=2))

    print(f"✅ {len(all_cards)} cartes enregistrées dans output/all_cards.json")

if __name__ == "__main__":
    asyncio.run(main())
