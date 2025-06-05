import psycopg
import os
import json
from datetime import datetime
import sys
from collections import defaultdict
import re

sys.stdout.reconfigure(encoding='utf-8')

postgres_db = "postgres"
postgres_user = "postgres"
postgres_password = "ton_mot_de_passe"
postgres_host = "127.0.0.1"
postgres_port = "5432"

output_directory = "../data_collection/output"
# Chemins relatifs vers les fichiers JSON
json_all_cards = os.path.join("..", "data_collection", "all_cards.json")
json_extensions = os.path.join("..", "data_collection", "extensions.json")

# Helpers

def remove_non_encodable(text: str, encoding="cp1252") -> str:
    try:
        return text.encode(encoding).decode(encoding)
    except Exception:
        return text.encode(encoding, errors="ignore").decode(encoding)

def get_conn_str() -> str:
    return f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"

def parse_card_name(card: str) -> str:
    return re.sub(r"\s*\(.*\)$", "", card).strip()

def parse_card_code_from_url(url: str) -> str:
    parts = url.split('/cards/')
    return parts[1].split('/')[0] if len(parts) > 1 else ''

# Charge les extensions triées par date

def load_extensions() -> list[str]:
    if not os.path.isfile(json_extensions):
        return []
    raw = json.load(open(json_extensions, encoding='utf-8'))
    exts = []
    for e in raw:
        ds = e.get('release_date','').strip()
        if not ds:
            continue
        try:
            dt = datetime.strptime(ds, "%d %b %y")
        except:
            continue
        code = e.get('code','').strip()
        if code:
            exts.append((code, dt))
    exts.sort(key=lambda x: x[1])
    return [code for code, _ in exts]

# Charge tous les tournois JSON en mémoire

def load_all_tournaments() -> list[dict]:
    tournaments = []
    if not os.path.isdir(output_directory):
        return tournaments
    for fn in os.listdir(output_directory):
        if not fn.lower().endswith(".json"):
            continue
        path = os.path.join(output_directory, fn)
        try:
            t = json.load(open(path, encoding="utf-8"))
            if isinstance(t, dict):
                tournaments.append(t)
        except Exception:
            pass
    return tournaments

# Calcule les données à insérer, incluant deck_summary

def compute_all_inserts(all_tournaments: list[dict]):
    wrk_tourn_rows = []
    wrk_deck_rows = []
    card_to_decks = defaultdict(set)
    if not os.path.isfile(json_all_cards):
        raise FileNotFoundError(f"Fichier all_cards.json introuvable : {json_all_cards}")
    all_cards_json = json.load(open(json_all_cards, encoding="utf-8"))
    uniq_cards = {}
    # Construire maps pour stage et hp
    stage_map = {}
    hp_map = {}
    evolves_map = {}
    for c in all_cards_json:
        name = c.get('name','')
        full_url = c.get('full_url','')
        ext_code = parse_card_code_from_url(full_url)
        stage = c.get('stage','')
        hp_str = c.get('hp','').strip()
        try:
            hp_val = int(hp_str)
        except:
            hp_val = 0
        stage_map[(name, ext_code)] = stage
        hp_map[(name, ext_code)] = hp_val
        evolves_map[name] = c.get('evolves_from','').strip()
        key = (name, c.get('attack',''), c.get('extension',''))
        if key not in uniq_cards:
            uniq_cards[key] = c

    ext_order = load_extensions()

    tourn_pstats = {}
    tourn_latest_ext = {}
    for t in all_tournaments:
        tid = remove_non_encodable(t.get('id',''))
        name = remove_non_encodable(t.get('name',''))
        try:
            date = datetime.fromisoformat(t.get('date','').replace('Z','+00:00')).replace(tzinfo=None)
        except:
            date = None
        org = remove_non_encodable(t.get('organizer',''))
        fmt = remove_non_encodable(t.get('format',''))
        nb  = int(t.get('nb_players', 0))

        # Détermine latest extension pour ce tournoi
        ext_codes_in_tourn = set(parse_card_code_from_url(c.get('url',''))
                                for pl in t.get('players',[]) for c in pl.get('decklist', []))
        latest_ext = ''
        for code in ext_order:
            if code in ext_codes_in_tourn:
                latest_ext = code
        tourn_latest_ext[tid] = latest_ext

        wrk_tourn_rows.append((tid, name, date, org, fmt, nb))

        pstats = defaultdict(lambda: {'wins':0,'losses':0})
        for m in t.get('matches', []):
            res = m.get('match_results', [])
            if not res:
                continue
            scores = [r.get('score', 0) for r in res]
            maxs = max(scores)
            if scores.count(maxs) == 1:
                for r in res:
                    pid = r.get('player_id','')
                    if r.get('score',0) == maxs:
                        pstats[pid]['wins'] += 1
                    else:
                        pstats[pid]['losses'] += 1
        tourn_pstats[tid] = pstats

    user_map = {}
    next_user_id = 1
    for t in all_tournaments:
        tid = remove_non_encodable(t.get('id',''))
        pstats = tourn_pstats.get(tid, {})
        for pl in t.get('players', []):
            orig = pl.get('id','')
            if orig not in user_map:
                user_map[orig] = next_user_id
                next_user_id += 1
            pid_int = user_map[orig]
            w = pstats.get(orig, {}).get('wins', 0)
            l = pstats.get(orig, {}).get('losses', 0)
            total = w + l or 1
            wr = int(w * 100 / total)

            for c in pl.get('decklist', []):
                deck_type = remove_non_encodable(c.get('type',''))
                url        = remove_non_encodable(c.get('url',''))
                name_full  = remove_non_encodable(c.get('name',''))
                code       = remove_non_encodable(parse_card_code_from_url(url))

                wrk_deck_rows.append((
                    tid, str(pid_int), deck_type,
                    name_full, url, code, w, l, wr
                ))

                deck_id = f"{tid}_{orig}"
                card_to_decks[name_full].add(deck_id)

    card_usage_map = {nm: int(len(ds)*100 / max(len(card_to_decks),1))
                      for nm, ds in card_to_decks.items()}
    all_cards_rows = []
    for c in uniq_cards.values():
        nm       = remove_non_encodable(c.get('name',''))
        u        = card_usage_map.get(nm, 0)
        lbl_ext  = remove_non_encodable(c.get('extension',''))
        code_ext = remove_non_encodable(parse_card_code_from_url(c.get('full_url','')))
        all_cards_rows.append((
            remove_non_encodable(c.get('full_url','')),
            nm,
            remove_non_encodable(c.get('card_type','')),
            remove_non_encodable(c.get('stage','')),
            remove_non_encodable(c.get('evolves_from','')),
            remove_non_encodable(c.get('element_type','')),
            remove_non_encodable(c.get('hp','')),
            remove_non_encodable(c.get('attack','')),
            remove_non_encodable(c.get('attack_effect','')),
            remove_non_encodable(c.get('ability','')),
            remove_non_encodable(c.get('ability_effect','')),
            remove_non_encodable(c.get('weakness','')),
            remove_non_encodable(c.get('retreat','')),
            remove_non_encodable(c.get('illustrator','')),
            remove_non_encodable(c.get('flavor_text','')),
            lbl_ext,
            code_ext,
            max(0, min(u,100))
        ))

    # 4) Préparer deck_summary avec extension distincte
    stats_summary = {}
    for t in all_tournaments:
        tid = remove_non_encodable(t.get('id',''))
        ext = tourn_latest_ext.get(tid, '')
        pstats = tourn_pstats.get(tid, {})
        for pl in t.get('players', []):
            pid = pl.get('id','')
            w = pstats.get(pid, {}).get('wins', 0)
            l = pstats.get(pid, {}).get('losses', 0)
            total = w + l or 1
            wr = int(w * 100 / total)

            mons = []
            for c in pl.get('decklist', []):
                if c.get('type') != 'Pokémon':
                    continue
                nm  = parse_card_name(c.get('name',''))
                url = c.get('url','')
                card_ext = parse_card_code_from_url(url)
                stage_str = stage_map.get((nm, card_ext), '')
                st = 2 if 'Stage 2' in stage_str else 1 if 'Stage 1' in stage_str else 0
                hp_val = hp_map.get((nm, card_ext), 0)
                mons.append((nm, st, hp_val))
            if not mons:
                continue
            # Trier: priorité EX, puis stage décroissant, puis HP décroissant
            mons_sorted = sorted(
                mons,
                key=lambda x: (
                    0 if x[0].lower().endswith(' ex') else 1,
                    -x[1],
                    -x[2]
                )
            )
            key_cards = []
            for nm, st, hp_val in mons_sorted:
                conflict = False
                for sel in key_cards:
                    if evolves_map.get(nm,'') == sel or evolves_map.get(sel,'') == nm:
                        conflict = True
                        break
                if conflict:
                    continue
                key_cards.append(nm)
                if len(key_cards) == 2:
                    break
            if not key_cards:
                continue
            key_cards = sorted(key_cards)
            deck_name = " - ".join(key_cards)
            summary_key = (deck_name, ext)
            if summary_key not in stats_summary:
                stats_summary[summary_key] = {'wrs': [], 'cnt': 0}
            stats_summary[summary_key]['wrs'].append(wr)
            stats_summary[summary_key]['cnt'] += 1
    deck_summary_rows = []
    for (deck_name, ext), val in stats_summary.items():
        avg_wr = int(sum(val['wrs']) / len(val['wrs'])) if val['wrs'] else 0
        deck_summary_rows.append((deck_name, ext, avg_wr, val['cnt']))
    return wrk_tourn_rows, wrk_deck_rows, all_cards_rows, deck_summary_rows

# Création des tables

def create_tables():
    ddl = """
    DROP TABLE IF EXISTS public.wrk_tournaments;
    CREATE TABLE public.wrk_tournaments (
      tournament_id VARCHAR,
      tournament_name VARCHAR,
      tournament_date TIMESTAMP,
      tournament_organizer VARCHAR,
      tournament_format VARCHAR,
      tournament_nb_players INT
    );

    DROP TABLE IF EXISTS public.wrk_decklists;
    CREATE TABLE public.wrk_decklists (
      tournament_id VARCHAR,
      player_id VARCHAR,
      deck_type VARCHAR,
      card_name VARCHAR,
      card_url TEXT,
      card_code VARCHAR,
      win_count INT,
      loss_count INT,
      winrate_percent INT
    );

    DROP TABLE IF EXISTS public.dwh_cards;
    CREATE TABLE public.dwh_cards AS
      SELECT DISTINCT deck_type AS card_type, card_name, card_url
      FROM public.wrk_decklists;

    DROP TABLE IF EXISTS public.all_pokemon_cards;
    CREATE TABLE public.all_pokemon_cards (
        full_url TEXT,
        name TEXT,
        card_type TEXT,
        stage TEXT,
        evolves_from TEXT,
        element_type TEXT,
        hp TEXT,
        attack TEXT,
        attack_effect TEXT,
        ability TEXT,
        ability_effect TEXT,
        weakness TEXT,
        retreat TEXT,
        illustrator TEXT,
        flavor_text TEXT,
        extension_label TEXT,
        extension_code TEXT,
        usage_percent_set INT
    );

    DROP TABLE IF EXISTS public.deck_summary;
    CREATE TABLE public.deck_summary (
      deck_name TEXT,
      extension_label TEXT,
      avg_winrate INT,
      presence_count INT,
      PRIMARY KEY (deck_name, extension_label)
    );
    """
    with psycopg.connect(get_conn_str()) as conn:
        with conn.cursor() as cur:
            cur.execute("SET NAMES 'UTF8';")
            cur.execute(ddl)

# Exécution principale

if __name__ == "__main__":
    print("1) Chargement des tournois…")
    all_tourn = load_all_tournaments()

    print("2) Calcul des données…")
    wrk_tourn_rows, wrk_deck_rows, all_cards_rows, deck_summary_rows = compute_all_inserts(all_tourn)

    print("3) Création des tables…")
    create_tables()

    print("4a) Insertion wrk_tournaments…")
    sql_t = "INSERT INTO public.wrk_tournaments VALUES (%s,%s,%s,%s,%s,%s)"
    with psycopg.connect(get_conn_str()) as conn:
        with conn.cursor() as cur:
            cur.execute("SET NAMES 'UTF8';")
            cur.executemany(sql_t, wrk_tourn_rows)

    print("4b) Insertion wrk_decklists…")
    sql_d = "INSERT INTO public.wrk_decklists VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    with psycopg.connect(get_conn_str()) as conn:
        with conn.cursor() as cur:
            cur.execute("SET NAMES 'UTF8';")
            cur.executemany(sql_d, wrk_deck_rows)

    print("4c) Insertion all_pokemon_cards…")
    sql_c = "INSERT INTO public.all_pokemon_cards VALUES (" + ",".join(["%s"]*18) + ")"
    with psycopg.connect(get_conn_str()) as conn:
        with conn.cursor() as cur:
            cur.execute("SET NAMES 'UTF8';")
            cur.executemany(sql_c, all_cards_rows)

    print("4d) Insertion deck_summary…")
    sql_s = "INSERT INTO public.deck_summary VALUES (%s,%s,%s,%s)"
    with psycopg.connect(get_conn_str()) as conn:
        with conn.cursor() as cur:
            cur.execute("SET NAMES 'UTF8';")
            cur.executemany(sql_s, deck_summary_rows)

    print("Fini !")
