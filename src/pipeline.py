import os
import re
import sqlite3
import json
import unicodedata
import chromadb
from sentence_transformers import SentenceTransformer
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from schema import DB_SCHEMA
from team_normalizer import normalize_team, normalize_teams_in_text

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

def normalize_season(text: str) -> str:
    """Convert any season format to YYYY-YY e.g. 2024/2025 → 2024-25, 24/25 → 2024-25"""
    from datetime import datetime
    now = datetime.now()
    # Determine current and last season based on current month
    # Football season: Aug-May, so if month >= 8, current season started this year
    if now.month >= 8:
        current_season = f"{now.year}-{str(now.year + 1)[2:]}"
        last_season = f"{now.year - 1}-{str(now.year)[2:]}"
    else:
        current_season = f"{now.year - 1}-{str(now.year)[2:]}"
        last_season = f"{now.year - 2}-{str(now.year - 1)[2:]}"

    # Replace relative season references
    text = re.sub(r'\bthis season\b', current_season, text, flags=re.IGNORECASE)
    text = re.sub(r'\bcurrent season\b', current_season, text, flags=re.IGNORECASE)
    text = re.sub(r'\blast season\b', last_season, text, flags=re.IGNORECASE)
    text = re.sub(r'\bprevious season\b', last_season, text, flags=re.IGNORECASE)

    # Convert explicit formats
    text = re.sub(r'(20\d{2})[/-](20\d{2})', lambda m: f"{m.group(1)}-{m.group(2)[2:]}", text)
    text = re.sub(r'\b(\d{2})[/-](\d{2})\b', lambda m: f"20{m.group(1)}-{m.group(2)}", text)
    return text

# Init — add max_tokens to control response length
llm_stats = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1, max_tokens=512, api_key=os.getenv("GROQ_API_KEY"))
llm_story = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.6, max_tokens=1024, api_key=os.getenv("GROQ_API_KEY"))
embed_model = SentenceTransformer("all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path=os.path.join(BASE_DIR, "vectordb"))
collection = chroma_client.get_collection("football_knowledge")

DB_PATH = os.path.join(BASE_DIR, "data/football.db")

# ── 0. Query Rewriter ────────────────────────────────────────────────────────
llm_rewrite = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0, max_tokens=100, api_key=os.getenv("GROQ_API_KEY"))

def rewrite_query(question: str) -> str:
    """Fix typos, grammar, abbreviations and normalize football-related questions."""
    prompt = f"""You are a football query normalizer. Fix the following in this question:
1. Spelling mistakes and typos (e.g. 'Seri A' → 'Serie A', 'Reall Madird' → 'Real Madrid')
2. League abbreviations (e.g. 'EPL' → 'Premier League', 'BL' → 'Bundesliga', 'SA' → 'Serie A', 'L1' → 'Ligue 1', 'UCL' → 'Champions League')
3. Player nicknames (e.g. 'CR7' → 'Cristiano Ronaldo', 'G.O.A.T' → 'Lionel Messi', 'Egyptian King' → 'Mohamed Salah', 'The Special One' → 'Jose Mourinho', 'R9' → 'Ronaldo', 'O Fenomeno' → 'Ronaldo')
4. Grammar errors and incomplete words (e.g. 'Whscored' → 'Who scored', 'gols' → 'goals')
5. Keep season references exactly as written (e.g. '23/24', 'last season', 'this season' — do NOT change these)

Return ONLY the corrected question, nothing else.

Question: {question}"""
    try:
        return invoke_with_retry(llm_rewrite, prompt)
    except Exception:
        return question


STATS_KEYWORDS = [
    "how many goals", "goals scored", "how many wins", "how many losses",
    "how many draws", "how many points", "most goals", "least goals",
    "average goals", "total goals", "shots", "yellow cards", "red cards",
    "corners", "match result", "beat", "won against", "lost to",
    "head to head", "h2h", "league table", "standings",
    "how many matches", "how many times did", "how many times has",
    "which team scored", "which team won the most", "which team lost",
    "most wins", "most losses", "most draws", "top team", "most corners",
    "most cards", "clean sheets",
    "top scorer", "top 5", "top five", "top scorers", "top assisters",
    "most assists", "who scored most", "who assisted most",
    "who scored more", "scored more goals", "more goals", "most goals scored",
    "who has more goals", "who has most goals",
    "highest xg", "most xg", "xg", "expected goals",
    "most penalties", "penalty goals", "non-penalty", "how many penalties",
    "key passes", "minutes played", "most shots",
    "goal breakdown", "goals breakdown", "scoring breakdown",
    "how many goals did", "how many assists did", "how many penalties did"
]

STORY_KEYWORDS = [
    "ucl", "champions league", "europa league", "trophy", "trophies",
    "history", "tell me about", "who is", "what is", "describe",
    "founded", "stadium", "rivalry", "legend", "greatest", "best",
    "fa cup", "world cup", "euro", "conference league",
    "manager", "coach", "head coach", "who manages", "owner", "ground",
    "about", "explain", "background", "story"
]

OUT_OF_SCOPE = [
    "transfer", "signing", "wage", "salary", "live score", "today",
    "tonight", "tomorrow", "next match", "upcoming", "prediction",
    "fantasy", "injury update", "latest news", "breaking"
]

def classify_query(question: str) -> str:
    q = question.lower()
    # Out of scope — live/transfer/news questions
    if any(kw in q for kw in OUT_OF_SCOPE):
        return "out_of_scope"
    # Stats keywords take priority for data questions
    if any(kw in q for kw in STATS_KEYWORDS):
        return "stats"
    # Story keywords for narrative questions
    if any(kw in q for kw in STORY_KEYWORDS):
        return "story"
    return "story"

# ── 2. Text-to-SQL Chain ─────────────────────────────────────────────────────
def invoke_with_retry(llm, prompt, retries=3):
    import time
    for i in range(retries):
        try:
            return llm.invoke(prompt).content.strip()
        except Exception as e:
            if "rate_limit" in str(e).lower() and i < retries - 1:
                time.sleep(5)
            else:
                raise e

def run_sql_chain(question: str) -> str:
    normalized = normalize_season(question)
    normalized = normalize_teams_in_text(normalized)

    # Detect if it's a team goals question to add top scorers
    q_lower = question.lower()
    is_team_goals = any(kw in q_lower for kw in ["how many goals did", "how many goals does", "goals scored by", "goals did", "goals does"])
    # Detect team for extra queries
    detected_team = None
    if is_team_goals:
        from team_normalizer import MATCHES_ALIASES
        # Check aliases first
        for alias, canonical in sorted(MATCHES_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
            if alias in q_lower:
                detected_team = canonical
                break
        # If no alias found, check if canonical name is directly in question
        if not detected_team:
            canonical_names = set(MATCHES_ALIASES.values())
            for name in sorted(canonical_names, key=len, reverse=True):
                if name.lower() in q_lower:
                    detected_team = name
                    break

    sql_prompt = f"""You are a SQL expert. Given this database schema:
{DB_SCHEMA}

Generate a valid SQLite SQL query to answer this question:
"{normalized}"

Rules:
- Return ONLY ONE SQL query, no explanation, no multiple statements
- Use exact column and table names from schema
- Use exact team names as they appear in the DB
- Season format MUST be 'YYYY-YY' e.g. '2024-25', '2020-21' — never '2024/2025'
- Limit results to 10 rows max
"""
    try:
        sql_query = invoke_with_retry(llm_stats, sql_prompt)
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

        conn = sqlite3.connect(DB_PATH)

        # Register accent-stripping function so SQL can match 'Mbappe' to 'Mbappé'
        def strip_accents(s):
            if s is None: return s
            return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('utf-8').lower()
        conn.create_function("strip_accents", 1, strip_accents)

        rows = conn.execute(sql_query).fetchall()
        cursor = conn.execute(sql_query)
        cols = [d[0] for d in cursor.description]

        # If team goals question, also fetch top scorers and penalty scorers
        extra_data = {}
        if is_team_goals and detected_team:
            season_match = re.search(r'\d{4}-\d{2}', normalized)
            if season_match:
                season = season_match.group()
                top_scorers = conn.execute(f"""
                    SELECT player, goals, penalty_goals FROM players
                    WHERE team LIKE '%{detected_team}%' AND season='{season}' AND goals > 0
                    ORDER BY goals DESC LIMIT 5
                """).fetchall()
                top_assisters = conn.execute(f"""
                    SELECT player, assists FROM players
                    WHERE team LIKE '%{detected_team}%' AND season='{season}' AND assists > 0
                    ORDER BY assists DESC LIMIT 5
                """).fetchall()
                penalty_scorers = conn.execute(f"""
                    SELECT player, penalty_goals FROM players
                    WHERE team LIKE '%{detected_team}%' AND season='{season}' AND penalty_goals > 0
                    ORDER BY penalty_goals DESC LIMIT 3
                """).fetchall()
                extra_data["top_scorers"] = [{"player": r[0], "goals": r[1], "penalties": r[2]} for r in top_scorers]
                extra_data["top_assisters"] = [{"player": r[0], "assists": r[1]} for r in top_assisters]
                extra_data["penalty_scorers"] = [{"player": r[0], "penalties": r[1]} for r in penalty_scorers]

        conn.close()

        if not rows:
            return "I couldn't find any data for that. Try rephrasing or check the team/season name."

        result_json = [dict(zip(cols, row)) for row in rows]
        if extra_data:
            result_json.append(extra_data)

        format_prompt = f"""
<instruction>
Convert this data into a direct, friendly answer for a football fan.
The data IS the answer — state it clearly and directly.
If top_scorers data is present, mention who scored the most goals.
If top_assisters data is present, mention who had the most assists.
If penalty_scorers data is present, mention who scored the most penalties.
Do not say "the data doesn't show" — the data is provided below.
</instruction>
<data>
{json.dumps(result_json, indent=2)}
</data>
<question>
{question}
</question>
"""
        return invoke_with_retry(llm_stats, format_prompt)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return "Sorry, I couldn't retrieve that stat. Try asking about team goals, wins, or head-to-head results."

# ── 3. RAG Chain ─────────────────────────────────────────────────────────────

# Map common club names to their Wikipedia title keywords for metadata filtering
CLUB_NAME_MAP = {
    "chelsea": "Chelsea F.C.", "arsenal": "Arsenal F.C.", "liverpool": "Liverpool F.C.",
    "man united": "Manchester United F.C.", "man utd": "Manchester United F.C.",
    "manchester united": "Manchester United F.C.",
    "man city": "Manchester City F.C.", "manchester city": "Manchester City F.C.",
    "tottenham": "Tottenham Hotspur F.C.", "spurs": "Tottenham Hotspur F.C.",
    "everton": "Everton F.C.", "newcastle": "Newcastle United F.C.",
    "aston villa": "Aston Villa F.C.", "leeds": "Leeds United F.C.",
    "brighton": "Brighton & Hove Albion F.C.", "fulham": "Fulham F.C.",
    "crystal palace": "Crystal Palace F.C.", "wolves": "Wolverhampton Wanderers F.C.",
    "west ham": "West Ham United F.C.", "leicester": "Leicester City F.C.",
    "real madrid": "Real Madrid CF", "barcelona": "FC Barcelona", "barca": "FC Barcelona",
    "atletico madrid": "Atlético Madrid", "atletico": "Atlético Madrid",
    "sevilla": "Sevilla FC", "valencia": "Valencia CF",
    "real betis": "Real Betis", "betis": "Real Betis",
    "villarreal": "Villarreal CF",
    "bayern": "FC Bayern Munich", "fc bayern": "FC Bayern Munich",
    "dortmund": "Borussia Dortmund", "bvb": "Borussia Dortmund",
    "rb leipzig": "RB Leipzig", "leipzig": "RB Leipzig",
    "leverkusen": "Bayer 04 Leverkusen",
    "schalke": "FC Schalke 04",
    "gladbach": "Borussia Mönchengladbach", "monchengladbach": "Borussia Mönchengladbach",
    "frankfurt": "Eintracht Frankfurt",
    "juventus": "Juventus FC", "juve": "Juventus FC",
    "ac milan": "AC Milan", "milan": "AC Milan",
    "inter milan": "Inter Milan", "inter": "Inter Milan",
    "as roma": "AS Roma", "roma": "AS Roma",
    "napoli": "SSC Napoli", "ssc napoli": "SSC Napoli",
    "lazio": "SS Lazio", "ss lazio": "SS Lazio",
    "fiorentina": "ACF Fiorentina", "atalanta": "Atalanta BC",
    "psg": "Paris Saint-Germain FC", "paris saint-germain": "Paris Saint-Germain FC",
    "marseille": "Olympique de Marseille",
    "lyon": "Olympique Lyonnais",
    "monaco": "AS Monaco FC",
    "lille": "Lille OSC",
}

def detect_club(question: str):
    q = question.lower()
    for alias, title in sorted(CLUB_NAME_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in q:
            return title
    return None

def run_rag_chain(question: str) -> str:
    q_lower = question.lower()
    club = detect_club(question)

    # Enhance query for manager/coach questions to find relevant chunks
    is_manager_question = any(kw in q_lower for kw in ["manager", "coach", "head coach", "who manages", "who is the manager"])
    if is_manager_question and club:
        search_query = f"{club} current manager head coach appointed"
    else:
        search_query = question

    query_embedding = embed_model.encode(search_query).tolist()

    # If club detected, filter by that club's metadata using partial match
    if club:
        # Try exact match first
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=12,
            where={"title": {"$eq": club}},
            include=["documents", "metadatas"]
        )
        # If no results, try without metadata filter (fallback)
        if not results["documents"][0]:
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=12,
                include=["documents", "metadatas"]
            )
    else:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=10,
            include=["documents", "metadatas"]
        )

    chunks = results["documents"][0]
    context = "\n\n".join(chunks)

    q_lower = question.lower()
    is_club_question = any(kw in q_lower for kw in ["tell me about", "history of", "about the club", "club history"])
    is_manager_question = any(kw in q_lower for kw in ["manager", "coach", "head coach", "who manages"])
    is_trophy_question = any(kw in q_lower for kw in ["trophy", "trophies", "honours", "titles won", "how many ucl", "how many league"])
    is_rivalry_question = any(kw in q_lower for kw in ["rivalry", "rivals", "derby", "vs", "against"])
    is_stadium_question = any(kw in q_lower for kw in ["stadium", "ground", "capacity", "home ground"])

    if is_manager_question:
        rag_prompt = f"""
<instruction>
Answer ONLY about the manager/coach. Include: name, when appointed, any notable achievements as manager.
Keep it concise — 3 to 5 sentences max. Do not include club history or trophies won before their tenure.
</instruction>
<context>{context}</context>
<question>{question}</question>
"""
    elif is_stadium_question:
        rag_prompt = f"""
<instruction>
Answer ONLY about the stadium. Include: name, location, capacity, when opened, any notable facts.
Keep it concise. Do not include unrelated club history.
</instruction>
<context>{context}</context>
<question>{question}</question>
"""
    elif is_trophy_question:
        rag_prompt = f"""
<instruction>
List the trophies/honours won by the club from the context. Include counts for each competition.
Be specific and structured. Do not include unrelated information.
</instruction>
<context>{context}</context>
<question>{question}</question>
"""
    elif is_rivalry_question:
        rag_prompt = f"""
<instruction>
Answer ONLY about the rivalry mentioned. Include history of the rivalry, notable matches if mentioned.
Keep focused on the rivalry. Do not include unrelated club history.
</instruction>
<context>{context}</context>
<question>{question}</question>
"""
    elif is_club_question:
        rag_prompt = f"""
<instruction>
Provide a comprehensive overview of the club including:
- Founded year, location, league
- Stadium name and capacity
- Current manager
- Major trophies (with counts)
- Key rivalries
- Any notable facts
Only include what is in the context.
</instruction>
<context>{context}</context>
<question>{question}</question>
"""
    else:
        rag_prompt = f"""
<instruction>
Answer the question using ONLY the context below. Be concise and focused.
If not in context, say "I don't have enough information about that."
</instruction>
<context>{context}</context>
<question>{question}</question>
"""
    return invoke_with_retry(llm_story, rag_prompt)

# ── 4. Main Router ───────────────────────────────────────────────────────────
def answer(question: str) -> str:
    # Step 1: Fix typos and grammar
    clean_question = rewrite_query(question)

    query_type = classify_query(clean_question)
    if query_type == "out_of_scope":
        return "I cover historical match stats and club history from the Big 5 European leagues. I don't have live scores, transfer news, or injury updates. Try asking about match results, goals, trophies, or club history."
    if query_type == "stats":
        return run_sql_chain(clean_question)
    return run_rag_chain(clean_question)

if __name__ == "__main__":
    test_questions = [
        "How many goals did Arsenal score in the 2020-21 season?",
        "Tell me about the history of FC Barcelona",
        "How many times did Liverpool beat Man United?",
        "What makes Real Madrid a legendary club?",
    ]
    for q in test_questions:
        print(f"\nQ: {q}")
        print(f"A: {answer(q)}")
        print("-" * 60)
