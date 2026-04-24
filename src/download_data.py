import requests
import pandas as pd
import sqlite3
import os

LEAGUES = {
    "E0": "England",
    "SP1": "Spain",
    "D1": "Germany",
    "I1": "Italy",
    "F1": "France"
}

SEASONS = [
    "1011","1112","1213","1314","1415",
    "1516","1617","1718","1819","1920",
    "2021","2122","2223","2324","2425"
]

COLUMNS = [
    "Date","HomeTeam","AwayTeam",
    "FTHG","FTAG","FTR",
    "HTHG","HTAG","HTR",
    "HS","AS","HST","AST",
    "HC","AC","HY","AY","HR","AR"
]

def download_and_load():
    os.makedirs("data/raw", exist_ok=True)
    conn = sqlite3.connect("data/football.db")
    all_dfs = []

    for league_code, league_name in LEAGUES.items():
        for season in SEASONS:
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{league_code}.csv"
            try:
                df = pd.read_csv(url, usecols=lambda c: c in COLUMNS, on_bad_lines='skip')
                df["League"] = league_name
                df["Season"] = f"20{season[:2]}-{season[2:]}"
                all_dfs.append(df)
                print(f"Downloaded: {league_name} {season}")
            except Exception as e:
                print(f"Skipped: {league_name} {season} — {e}")

    final_df = pd.concat(all_dfs, ignore_index=True)
    final_df.to_sql("matches", conn, if_exists="replace", index=False)
    conn.close()
    print(f"\nDone. {len(final_df)} rows loaded into data/football.db")

if __name__ == "__main__":
    download_and_load()
