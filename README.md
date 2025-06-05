# SAE6-VCOD-01


This repository contains everything needed to reproduce a full metagame analysis of Pokémon TCG Pocket tournaments, from raw‐data scraping to final dashboards. The aim is to identify which cards and decks have the highest win rates, how popular strategies evolve over time, and which card combinations outperform others in each game “season” (expansion).

## Key steps:

Data Collection : scrape tournament & decklist JSONs from Limitless TCG

Data Transformation : clean, anonymize, load into PostgreSQL

Data Visualization : connect Power BI to PostgreSQL, build interactive dashboards



## Data Collection

- **`main.py`**: Scrapes Limitless TCG HTML and exports one JSON per tournament under `data_collection/output/`.
- **`Lists the following dependencies`**: 
  - `beautifulsoup4`
  - `aiohttp`
  - `dataclasses`
  - `aiofile`
  - `asyncio`
  - `os`
  - `json`
  - `re`

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

- **` Lists the following dependency`**: 
  - `psycopg`
  - `os`
  - `json`
  - `datetime`
  - `sys`
  - `collections`
  - `re`
- **List of steps to follow to run our project**

  - Extract the ZIP file containing our portable PostgreSQL database from this link : https://sourceforge.net/projects/pgsqlportable/.
  - In the extracted folder, run the batch file named `PostgreSQL-Start.bat` to start the server.
  - To get the data, run `main.py` in the `data_collection` folder.
  - To perform the transformation, run `main.py` in the `data_transformation` folder.
  - Once all of the above steps are complete, open the Power BI project.


---

## Powerbi Dashboard

Contains:
- The Power BI file with a dashboard (`.pbix`)
