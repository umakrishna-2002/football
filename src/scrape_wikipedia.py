import wikipediaapi
import json
import os

wiki = wikipediaapi.Wikipedia(language='en', user_agent='football-rag-bot/1.0')

CLUBS = [
    # England
    "Manchester City F.C.", "Liverpool F.C.", "Arsenal F.C.",
    "Chelsea F.C.", "Manchester United F.C.", "Tottenham Hotspur F.C.",
    "Everton F.C.", "Leicester City F.C.", "West Ham United F.C.",
    "Newcastle United F.C.", "Aston Villa F.C.", "Leeds United F.C.",
    "Wolverhampton Wanderers F.C.", "Brighton & Hove Albion F.C.",
    "Crystal Palace F.C.", "Southampton F.C.", "Fulham F.C.",
    "Burnley F.C.", "Brentford F.C.", "Nottingham Forest F.C.",
    "Blackburn Rovers F.C.", "Bolton Wanderers F.C.", "Stoke City F.C.",
    "Sunderland A.F.C.", "Swansea City A.F.C.", "Watford F.C.",
    "West Bromwich Albion F.C.", "Norwich City F.C.",
    # Spain
    "Real Madrid CF", "FC Barcelona", "Atletico Madrid",
    "Sevilla FC", "Valencia CF", "Real Sociedad",
    "Athletic Club", "Villarreal CF", "Real Betis",
    "Getafe CF", "Celta Vigo", "RCD Espanyol",
    "Levante UD", "Malaga CF", "UD Almeria",
    # Germany
    "FC Bayern Munich", "Borussia Dortmund", "RB Leipzig",
    "Bayer 04 Leverkusen", "Borussia Monchengladbach", "Eintracht Frankfurt",
    "Schalke 04", "Hamburger SV", "VfB Stuttgart",
    "Werder Bremen", "TSG 1899 Hoffenheim", "VfL Wolfsburg",
    "FC Augsburg", "Hertha BSC", "1. FC Koln",
    # Italy
    "Juventus FC", "AC Milan", "Inter Milan", "AS Roma",
    "SSC Napoli", "ACF Fiorentina", "SS Lazio", "Atalanta BC",
    "Torino FC", "UC Sampdoria", "Genoa CFC",
    "Udinese Calcio", "Bologna FC 1909", "Cagliari Calcio",
    # France
    "Paris Saint-Germain FC", "Olympique de Marseille",
    "Olympique Lyonnais", "AS Monaco FC", "LOSC Lille",
    "Stade Rennais FC", "OGC Nice", "RC Lens",
    "Girondins de Bordeaux", "AS Saint-Etienne"
]

CHECKPOINT_FILE = "data/checkpoint.json"
OUTPUT_DIR = "data/wikipedia"

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"done": []}

def save_checkpoint(name, checkpoint):
    checkpoint["done"].append(name)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(checkpoint, f)

def scrape(name, category, checkpoint):
    if name in checkpoint["done"]:
        print(f"Skipping {name} — already done")
        return

    page = wiki.page(name)
    if not page.exists():
        print(f"Not found: {name}")
        save_checkpoint(name, checkpoint)
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"{OUTPUT_DIR}/{category}_{name.replace(' ', '_').replace('/', '_')}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"TITLE: {page.title}\n")
        f.write(f"CATEGORY: {category}\n\n")
        f.write(page.text)

    save_checkpoint(name, checkpoint)
    print(f"Saved: {name}")

if __name__ == "__main__":
    checkpoint = load_checkpoint()
    for club in CLUBS:
        scrape(club, "club", checkpoint)
    print(f"\nDone. {len([f for f in os.listdir(OUTPUT_DIR) if f.endswith('.txt')])} club files in {OUTPUT_DIR}/")
