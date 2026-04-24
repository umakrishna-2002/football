import asyncio
import aiohttp
import sqlite3
import json
import os
from understat import Understat

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data/football.db")

LEAGUES = {
    "EPL": "England",
    "La_liga": "Spain",
    "Bundesliga": "Germany",
    "Serie_A": "Italy",
    "Ligue_1": "France"
}

# 2014-15 to 2024-25
SEASONS = list(range(2014, 2025))

CHECKPOINT_FILE = os.path.join(BASE_DIR, "data/understat_checkpoint.json")

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"done": []}

def save_checkpoint(key, checkpoint):
    checkpoint["done"].append(key)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f)

async def scrape():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player TEXT, team TEXT, league TEXT, season TEXT,
            goals INTEGER, assists INTEGER,
            xG REAL, xA REAL, shots INTEGER,
            key_passes INTEGER, minutes INTEGER, matches INTEGER,
            yellow_cards INTEGER, red_cards INTEGER,
            npg INTEGER, npxG REAL,
            PRIMARY KEY (player, team, league, season)
        )
    """)
    conn.commit()

    checkpoint = load_checkpoint()
    total = 0

    async with aiohttp.ClientSession() as session:
        understat = Understat(session)
        for league_code, league_name in LEAGUES.items():
            for season in SEASONS:
                key = f"{league_code}_{season}"
                if key in checkpoint["done"]:
                    print(f"Skipping {league_name} {season}")
                    continue

                try:
                    players = await understat.get_league_players(league_code, season)
                    rows = []
                    for p in players:
                        rows.append((
                            p.get("player_name", ""),
                            p.get("team_title", ""),
                            league_name,
                            f"{season}-{str(season+1)[2:]}",
                            int(p.get("goals", 0)),
                            int(p.get("assists", 0)),
                            float(p.get("xG", 0)),
                            float(p.get("xA", 0)),
                            int(p.get("shots", 0)),
                            int(p.get("key_passes", 0)),
                            int(p.get("time", 0)),
                            int(p.get("games", 0)),
                            int(p.get("yellow_cards", 0)),
                            int(p.get("red_cards", 0)),
                            int(p.get("npg", 0)),
                            float(p.get("npxG", 0)),
                        ))

                    conn.executemany("""
                        INSERT OR REPLACE INTO players
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, rows)
                    conn.commit()
                    total += len(rows)
                    save_checkpoint(key, checkpoint)
                    print(f"Saved: {league_name} {season} — {len(rows)} players")

                except Exception as e:
                    print(f"Error: {league_name} {season} — {e}")

    conn.close()
    print(f"\nDone. {total} player records saved to players table")

if __name__ == "__main__":
    asyncio.run(scrape())
