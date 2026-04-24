# Football Fan Q&A Bot - Technical Documentation

## Project Overview
A hybrid Retrieval-Augmented Generation (RAG) + Text-to-SQL system that answers natural language questions about football using historical match data, player statistics, and club information from the Big 5 European leagues.

---

## Data Sources & Volume

### 1. Match Statistics (football-data.co.uk)
- **Volume:** 27,141 match records
- **Coverage:** Big 5 leagues (England, Spain, Germany, Italy, France)
- **Time Range:** 2010-11 to 2024-25 (15 seasons)
- **Format:** CSV → SQLite
- **Columns:** Date, teams, goals (FT/HT), shots, shots on target, corners, yellow/red cards, league, season

### 2. Player Statistics (Understat)
- **Volume:** 29,799 player records
- **Coverage:** Big 5 leagues
- **Time Range:** 2014-15 to 2024-25 (11 seasons)
- **Format:** JSON API → SQLite
- **Columns:** Player name, team, goals, assists, xG, xA, shots, key passes, minutes, matches, yellow/red cards, non-penalty goals (npg), penalty goals (computed)

### 3. Club Knowledge Base (Wikipedia)
- **Volume:** 128 club articles
- **Coverage:** Major clubs from Big 5 leagues
- **Format:** Wikipedia API → Text chunks → ChromaDB vector embeddings
- **Chunks:** 11,499 text chunks (500 chars each, 50 char overlap)
- **Embedding Model:** sentence-transformers/all-MiniLM-L6-v2
- **Content:** Club history, founding year, stadium, trophies, managers, rivalries

---

## Architecture

```
User Question
      ↓
Query Rewriter (LLM) — fixes typos, abbreviations, nicknames
      ↓
Query Classifier — stats vs story vs out_of_scope
      ↓
   ┌──────────────┴──────────────┐
   ↓                              ↓
Text-to-SQL Path              RAG Path
   ↓                              ↓
Team/Season Normalizer      Club Detection
   ↓                              ↓
LLM generates SQL            Vector Search (ChromaDB)
   ↓                              ↓
Execute on SQLite            Retrieve top 12 chunks
   ↓                              ↓
Format result as JSON        Metadata filter by club
   ↓                              ↓
LLM formats answer           XML-structured prompt
   ↓                              ↓
   └──────────────┬──────────────┘
                  ↓
          Natural Language Answer
```

---

## RAG Pipeline Implementation

### Step 1: Data Collection
```python
# Wikipedia scraping
wiki = wikipediaapi.Wikipedia(language='en', user_agent='football-rag-bot/1.0')
page = wiki.page("Manchester City F.C.")
text = page.text
```

### Step 2: Text Chunking
```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,      # characters per chunk
    chunk_overlap=50     # overlap to preserve context at boundaries
)
chunks = splitter.split_text(text)
```

### Step 3: Embedding Generation
```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
embedding = model.encode(chunk).tolist()
```

### Step 4: Vector Storage
```python
import chromadb

client = chromadb.PersistentClient(path="vectordb")
collection = client.get_or_create_collection("football_knowledge")

collection.add(
    ids=[f"club_Chelsea_{chunk_id}"],
    embeddings=[embedding],
    documents=[chunk],
    metadatas=[{"title": "Chelsea F.C.", "category": "club"}]
)
```

### Step 5: Retrieval with Metadata Filtering
```python
# Detect club from question
club = detect_club("Tell me about Chelsea")  # Returns "Chelsea F.C."

# Query with metadata filter
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=12,
    where={"title": {"$eq": club}},  # Only retrieve Chelsea chunks
    include=["documents", "metadatas"]
)
```

### Step 6: Prompt Construction with XML Tags
```python
context = "\n\n".join(results["documents"][0])

prompt = f"""
<instruction>
You are a football expert. Provide comprehensive club information including:
- Founded year, stadium, capacity
- Current manager
- Major trophies (with counts)
- Notable managers, rivalries
Use ONLY the context below.
</instruction>

<context>
{context}
</context>

<question>
{question}
</question>
"""
```

### Step 7: LLM Generation with Dynamic Temperature
```python
# Story/narrative questions → higher temperature for engaging responses
llm_story = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.6, max_tokens=1024)

# Stats questions → low temperature for factual accuracy
llm_stats = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1, max_tokens=512)
```

---

## Text-to-SQL Pipeline Implementation

### Step 1: Query Preprocessing
```python
# Normalize season formats
"24/25" → "2024-25"
"2024/2025" → "2024-25"
"this season" → "2025-26" (based on current date)

# Normalize team names
"Barca" → "Barcelona"
"Juve" → "Juventus"
"BVB" → "Dortmund"
"Inter Milan" → "Inter"
```

### Step 2: Schema Description
```python
DB_SCHEMA = """
Table: matches
  - Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR, ...
  
Table: players
  - player, team, league, season, goals, assists, xG, penalty_goals, ...

Notes:
- Season format: 'YYYY-YY' (e.g. '2024-25')
- Team names: exact DB names (e.g. 'Man United', 'Inter', 'Milan')
- For team goals: SELECT SUM(goals), SUM(npg), SUM(penalty_goals) ...
"""
```

### Step 3: SQL Generation via LLM
```python
sql_prompt = f"""Given this database schema:
{DB_SCHEMA}

Generate a valid SQLite SQL query to answer: "{question}"

Rules:
- Return ONLY ONE SQL query
- Use exact column/table names
- Season format: 'YYYY-YY'
- Limit results to 10 rows
"""

sql_query = llm.invoke(sql_prompt).content.strip()
```

### Step 4: SQL Execution
```python
conn = sqlite3.connect("data/football.db")

# Register custom function for accent-insensitive search
def strip_accents(s):
    return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('utf-8')
conn.create_function("strip_accents", 1, strip_accents)

rows = conn.execute(sql_query).fetchall()
cols = [d[0] for d in cursor.description]
```

### Step 5: Result Formatting as JSON
```python
result_json = [dict(zip(cols, row)) for row in rows]

# Example output:
[
  {"player": "Erling Haaland", "goals": 27, "penalty_goals": 7},
  {"player": "Cole Palmer", "goals": 22, "penalty_goals": 9}
]
```

### Step 6: Enhanced Data for Team Queries
```python
# For team goal questions, automatically fetch:
# 1. Top 5 scorers
# 2. Top 5 assisters  
# 3. Top 3 penalty scorers

extra_data = {
    "top_scorers": [...],
    "top_assisters": [...],
    "penalty_scorers": [...]
}
result_json.append(extra_data)
```

### Step 7: Natural Language Formatting
```python
format_prompt = f"""
<instruction>
Convert this data into a friendly answer for a football fan.
If top_scorers present, mention who scored most.
If top_assisters present, mention who assisted most.
</instruction>

<data>
{json.dumps(result_json, indent=2)}
</data>

<question>
{question}
</question>
"""

answer = llm.invoke(format_prompt).content
```

---

## Query Rewriting & Error Handling

### Typo & Grammar Correction
```python
def rewrite_query(question: str) -> str:
    prompt = """Fix:
    1. Spelling mistakes (Seri A → Serie A, Reall Madird → Real Madrid)
    2. League abbreviations (EPL → Premier League, BL → Bundesliga)
    3. Player nicknames (CR7 → Cristiano Ronaldo, GOAT → Lionel Messi)
    4. Grammar errors (Whscored → Who scored, gols → goals)
    """
    return llm.invoke(prompt).content
```

### Team Name Normalization
```python
TEAM_ALIASES = {
    "barca": "Barcelona",
    "juve": "Juventus",
    "bvb": "Dortmund",
    "psg": "Paris SG",
    "inter milan": "Inter",
    ...
}

def normalize_teams_in_text(text: str) -> str:
    # Replace all aliases using word boundaries
    for alias, canonical in sorted(TEAM_ALIASES.items(), key=len, reverse=True):
        pattern = r'(?<!\w)' + re.escape(alias) + r'(?!\w)'
        text = re.sub(pattern, canonical, text, flags=re.IGNORECASE)
    return text
```

### Season Inference
```python
from datetime import datetime

now = datetime.now()
if now.month >= 8:  # Aug-May is football season
    current_season = f"{now.year}-{str(now.year + 1)[2:]}"
else:
    current_season = f"{now.year - 1}-{str(now.year)[2:]}"

# Replace relative references
text = text.replace("this season", current_season)
text = text.replace("last season", last_season)
```

---

## Prompt Engineering Techniques

### 1. XML-Structured Prompts
Separates instructions, context, and question for better grounding:
```xml
<instruction>
  Answer using ONLY the context below.
  If not in context, say "I don't have enough information."
</instruction>

<context>
  {retrieved_chunks}
</context>

<question>
  {user_question}
</question>
```

### 2. Dynamic Temperature Control
```python
# Factual stats → low temperature (0.1)
"How many goals did Arsenal score?" → temperature=0.1

# Narrative/history → higher temperature (0.6)
"Tell me about Real Madrid's history" → temperature=0.6
```

### 3. Intent-Specific Prompts
Different prompts for different question types:
- **Manager question** → "Answer ONLY about the manager. 3-5 sentences max."
- **Trophy question** → "List trophies with counts. Be specific."
- **Club history** → "Comprehensive overview including founded year, stadium, trophies, rivalries."

### 4. Explicit Instructions to Prevent Hallucination
```
"The data IS the answer — state it directly."
"Do NOT say 'the data doesn't show' — the data is provided."
"Do NOT add team/league filters unless explicitly mentioned."
```

---

## Evaluation & Quality Control

### Model-Based Grading (Implicit)
- Query rewriter validates and corrects input
- Format prompt ensures LLM stays grounded in retrieved data
- XML structure prevents context mixing

### Code-Based Validation
```python
# Verify SQL returns non-empty results
if not rows:
    return "I couldn't find any data for that."

# Verify ChromaDB returns chunks
if not results["documents"][0]:
    # Fallback to unfiltered search
```

### Metadata Filtering for Precision
```python
# When asking about Chelsea, only retrieve Chelsea chunks
where={"title": {"$eq": "Chelsea F.C."}}
```

### Retry Logic for Rate Limits
```python
def invoke_with_retry(llm, prompt, retries=3):
    for i in range(retries):
        try:
            return llm.invoke(prompt).content
        except RateLimitError:
            if i < retries - 1:
                time.sleep(5)
```

---

## Key Technical Decisions

| Decision | Rationale |
|---|---|
| Hybrid RAG + Text-to-SQL | Stats need SQL accuracy, narratives need RAG flexibility |
| ChromaDB over Pinecone | Free, local, no API limits |
| Groq over OpenAI | Free tier, faster inference, good quality |
| sentence-transformers | Free, runs on CPU, good for football text |
| SQLite over PostgreSQL | Lightweight, no server needed, sufficient for 50k+ rows |
| Recursive chunking | Preserves sentence boundaries better than fixed-size |
| 500 char chunks, 50 overlap | Balance between context and retrieval precision |
| Dynamic temperature | Factual accuracy for stats, engagement for stories |
| XML prompt structure | Clear separation prevents context bleeding |
| Query rewriting | Handles real-world typos and abbreviations |
| Metadata filtering | Prevents cross-club context pollution |

---

## Data Processing Pipeline

### Match Data
```
CSV download → pandas DataFrame → clean dates/nulls → normalize results → SQLite
```

### Player Data
```
Understat API → async fetch per league/season → compute penalty_goals → SQLite
```

### Club Data
```
Wikipedia API → extract text → clean citations → chunk (500/50) → embed → ChromaDB
```

---

## Performance Optimizations

1. **Checkpoint system** — resume scraping if interrupted
2. **Batch embedding** — process chunks in batches
3. **Metadata filtering** — reduces search space from 11k to ~150 chunks per club
4. **Max tokens limit** — prevents overly long responses
5. **Connection pooling** — reuse SQLite connections
6. **Lazy loading** — embedding model loads once, reused across queries

---

## Limitations & Future Enhancements

### Current Limitations
- No Champions League/cup match data (only league matches)
- No set piece vs open play breakdown (only penalty vs non-penalty)
- Player stats only from 2014-15 onwards
- No live/real-time data
- No player transfer history or market values

### Possible Enhancements
- Add shot-level data for goal situation breakdown (open play, set piece, counter)
- Add match-level xG for deeper tactical analysis
- Add player comparison features (Messi vs Ronaldo career stats)
- Add formation and tactical data
- Add injury history from Wikipedia narratives
- Add Streamlit web UI for better UX
- Add conversation memory across sessions
- Add multi-language support

---

## Tech Stack Summary

| Component | Technology |
|---|---|
| LLM | Groq (Llama 3.3 70B) |
| Orchestration | LangChain |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Relational DB | SQLite |
| Data Sources | football-data.co.uk, Understat, Wikipedia |
| Language | Python 3.10 |
| Environment | Ubuntu (WSL2) |

---

## Skills Demonstrated

- **RAG Pipeline Design** — chunking, embedding, retrieval, metadata filtering
- **Text-to-SQL** — schema design, SQL generation via LLM, result formatting
- **Prompt Engineering** — XML structuring, dynamic temperature, intent-specific prompts
- **Query Preprocessing** — typo correction, abbreviation expansion, season inference
- **Data Engineering** — ETL from 3 sources, normalization, computed columns
- **LLM Grounding** — preventing hallucination via structured prompts and explicit instructions
- **Hybrid Retrieval** — combining structured (SQL) and unstructured (RAG) data sources
