import sqlite3
import pandas as pd

conn = sqlite3.connect("data/football.db")
df = pd.read_sql("SELECT * FROM matches", conn)

print(f"Before cleaning: {len(df)} rows")

# Fix date format to YYYY-MM-DD
df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")

# Drop rows with no teams or date
df = df.dropna(subset=["HomeTeam", "AwayTeam", "Date"])

# Fill missing numeric stats with 0
stat_cols = ["FTHG","FTAG","HTHG","HTAG","HS","AS","HST","AST","HC","AC","HY","AY","HR","AR"]
df[stat_cols] = df[stat_cols].fillna(0).astype(int)

# Normalize result column
df["FTR"] = df["FTR"].str.strip().str.upper()
df["HTR"] = df["HTR"].str.strip().str.upper()

print(f"After cleaning: {len(df)} rows")

df.to_sql("matches", conn, if_exists="replace", index=False)
conn.close()
print("Saved cleaned data to football.db")
