# SAE6-VCOD-01


This repository contains everything needed to reproduce a full metagame analysis of Pokémon TCG Pocket tournaments, from raw‐data scraping to final dashboards. The aim is to identify which cards and decks have the highest win rates, how popular strategies evolve over time, and which card combinations outperform others in each game “season” (expansion).

## Key steps:

Data Collection : scrape tournament & decklist JSONs from Limitless TCG

Data Transformation : clean, anonymize, load into PostgreSQL

Data Visualization : connect Power BI to PostgreSQL, build interactive dashboards



## Data Collection

- **`main.py`**: Scrapes Limitless TCG HTML and exports one JSON per tournament under `data_collection/output/`.
- **`requirements.txt`**: Lists the following dependencies:
  - `beautifulsoup4`
  - `aiohttp`
  - `aiofile`

---

## Data Transformation

- **`main.py`**: 
  - Reads every JSON file in `../data_collection/output/`
  - Anonymizes player IDs
  - Computes intermediate tables (working tables, deduplicated card metadata, deck summaries)
  - Writes four final tables into PostgreSQL:
    - `public.wrk_tournaments`
    - `public.wrk_decklists`
    - `public.all_pokemon_cards`
    - `public.deck_summary`

- **`requirements.txt`**: Lists the following dependency:
  - `psycopg[binary]`

- **`sql/schema.sql`**: DDL that drops and recreates tables exactly as the Python script expects.

---

## Powerbi Dashboard

Contains:
- An optional Power BI Desktop file (`.pbix`)
- A guide on how to connect it to your PostgreSQL instance
