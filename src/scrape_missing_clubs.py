import wikipediaapi
import json
import os

wiki = wikipediaapi.Wikipedia(language='en', user_agent='football-rag-bot/1.0')

# Only notable missing clubs worth scraping
MISSING_CLUBS = [
    # England
    "AFC Bournemouth", "Sheffield United F.C.", "Middlesbrough F.C.",
    "Birmingham City F.C.", "Hull City A.F.C.", "Cardiff City F.C.",
    "Queens Park Rangers F.C.", "Reading F.C.", "Wigan Athletic F.C.",
    "Huddersfield Town A.F.C.", "Ipswich Town F.C.", "Luton Town F.C.",
    "Blackpool F.C.",
    # Spain
    "Deportivo de La Coruna", "RCD Mallorca", "CA Osasuna",
    "Girona FC", "UD Las Palmas", "CD Leganes",
    "Cadiz CF", "Elche CF", "SD Eibar",
    # Germany
    "SC Freiburg", "1. FSV Mainz 05", "Hannover 96",
    "Fortuna Dusseldorf", "FC St. Pauli", "Union Berlin",
    "SpVgg Greuther Furth", "1. FC Nurnberg",
    # Italy
    "Parma Calcio 1913", "US Sassuolo Calcio", "Hellas Verona FC",
    "Empoli FC", "US Lecce", "Spezia Calcio",
    "AC Monza", "Frosinone Calcio",
    # France
    "Montpellier HSC", "FC Nantes", "Stade de Reims",
    "RC Strasbourg Alsace", "Toulouse FC", "Stade Brestois 29",
    "FC Lorient", "SM Caen"
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
    for club in MISSING_CLUBS:
        scrape(club, "club", checkpoint)
    total = len([f for f in os.listdir(OUTPUT_DIR) if f.endswith('.txt')])
    print(f"\nDone. {total} total club files in {OUTPUT_DIR}/")
