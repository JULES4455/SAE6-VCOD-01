import aiohttp
import asyncio
import os
import json
from dataclasses import dataclass, asdict
from bs4 import BeautifulSoup

BASE_URL  = "https://pocket.limitlesstcg.com"
PROXY_URL = "http://ocytohe.univ-ubs.fr:3128"
HEADERS   = {'User-Agent': 'Mozilla/5.0'}
CACHE_DIR = "cache"

@dataclass
class Extension:
    code: str
    name: str
    release_date: str
    card_count: int
    url: str

async def async_soup_from_url(session: aiohttp.ClientSession, path: str, use_cache: bool = True):
    fn = os.path.join(CACHE_DIR, path.strip("/").replace("/", "_") + ".html")
    if use_cache and os.path.exists(fn):
        html = open(fn, encoding="utf-8").read()
    else:
        async with session.get(BASE_URL + path, headers=HEADERS, proxy=PROXY_URL) as resp:
            html = await resp.text()
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(fn, "w", encoding="utf-8") as f:
            f.write(html)
    return BeautifulSoup(html, "html.parser")

async def extract_extensions(session: aiohttp.ClientSession):
    soup = await async_soup_from_url(session, "/cards", use_cache=False)

    # cherche le tableau dont la classe contient "sets-table"
    table = soup.find("table", class_=lambda cl: cl and "sets-table" in cl)
    if not table:
        print("❌ Table sets-table introuvable")
        return []

    # récupère soit <tbody><tr>…</tr></tbody>, soit direct <tr> dans <table>
    body = table.find("tbody")
    rows = body.find_all("tr") if body else table.find_all("tr")

    exts = []
    for tr in rows:
        tds = tr.find_all("td")
        # on ne garde que les lignes à 3 colonnes
        if len(tds) < 3:
            continue

        # Col 1 : nom + code
        a = tds[0].find("a", href=True)
        href = a["href"]
        span = a.find("span", class_="code annotation")
        code = span.text.strip() if span else ""
        raw = a.get_text(" ", strip=True)
        name = raw.replace(code, "").strip()

        # Col 2 : date
        release_date = tds[1].get_text(" ", strip=True)

        # Col 3 : nombre
        cnt = tds[2].get_text(" ", strip=True).split()[0]
        try:
            card_count = int(cnt)
        except:
            card_count = 0

        exts.append(Extension(
            code=code,
            name=name,
            release_date=release_date,
            card_count=card_count,
            url=BASE_URL + href
        ))

    return exts

async def main():
    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        extensions = await extract_extensions(session)
        with open("extensions.json", "w", encoding="utf-8") as f:
            json.dump([asdict(e) for e in extensions],
                      f, ensure_ascii=False, indent=2)
        print(f"✅ {len(extensions)} extensions écrites dans output/extensions.json")

if __name__ == "__main__":
    asyncio.run(main())
