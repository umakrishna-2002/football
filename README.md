# Football Fan Q&A Bot

A hybrid RAG + Text-to-SQL chatbot for football fans covering the Big 5 European leagues.

## Features
- Match stats, team goals, head-to-head records (Text-to-SQL)
- Player goals, assists, xG, penalties (Understat data)
- Club history, trophies, managers, rivalries (RAG + Wikipedia)
- Query rewriting — handles typos, abbreviations (EPL, BL), nicknames (CR7, Juve)
- Season inference — understands "this season", "last season"

## Data Sources
- **football-data.co.uk** — 27,141 match records (2010–2025)
- **Understat** — 29,799 player records (2014–2025)
- **Wikipedia** — 128 club articles in ChromaDB

## Leagues Covered
England, Spain, Germany, Italy, France (2010-11 to 2024-25)

## Stack
`Python` `LangChain` `Groq (Llama 3.3 70B)` `ChromaDB` `SQLite` `sentence-transformers` `Understat`

## Setup

```bash
# Install dependencies
pip install langchain langchain-groq chromadb sentence-transformers pandas understat wikipedia-api python-dotenv langchain-text-splitters

# Add Groq API key
echo "GROQ_API_KEY=your_key_here" > .env

# Download match data
python3 src/download_data.py

# Scrape Wikipedia clubs
python3 src/scrape_wikipedia.py

# Load into ChromaDB
python3 src/load_chromadb.py

# Scrape player stats
python3 src/scrape_understat.py

# Run the bot
python3 src/chat.py
```

## Sample Questions
- "Who scored most goals in Premier League 2023-24?"
- "How many goals did Liverpool score in 2023-24?"
- "Tell me about Real Madrid"
- "How many UCLs did Barcelona win?"
- "Top 5 assisters in Serie A 2022-23?"
- "How many penalties did Haaland score in 2022-23?"
