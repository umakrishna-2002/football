DB_SCHEMA = """
Table: matches
Columns:
  - Date        : Match date (YYYY-MM-DD format)
  - HomeTeam    : Home team name (e.g. 'Arsenal', 'Barcelona', 'Bayern Munich')
  - AwayTeam    : Away team name
  - FTHG        : Full time home goals (integer)
  - FTAG        : Full time away goals (integer)
  - FTR         : Full time result — 'H' = home win, 'A' = away win, 'D' = draw
  - HTHG        : Half time home goals
  - HTAG        : Half time away goals
  - HTR         : Half time result — 'H', 'A', or 'D'
  - HS          : Home team shots
  - AS          : Away team shots (use "AS" in quotes in SQL)
  - HST         : Home team shots on target
  - AST         : Away team shots on target
  - HC          : Home team corners
  - AC          : Away team corners
  - HY          : Home team yellow cards
  - AY          : Away team yellow cards
  - HR          : Home team red cards
  - AR          : Away team red cards
  - League      : League name — 'England', 'Spain', 'Germany', 'Italy', 'France'
  - Season      : Season string in format 'YYYY-YY' (e.g. '2020-21', '2019-20', '2024-25')
                  IMPORTANT: Never use '2024/2025' format, always use '2024-25'

Notes:
- To get goals scored by a team, sum FTHG where HomeTeam = team OR FTAG where AwayTeam = team
- To get wins, count rows where (HomeTeam = team AND FTR = 'H') OR (AwayTeam = team AND FTR = 'A')
- Head-to-head: filter WHERE (HomeTeam = team1 AND AwayTeam = team2) OR (HomeTeam = team2 AND AwayTeam = team1)
- Always use exact team names from the DB (e.g. 'Man United', 'Inter', 'Milan', 'Roma', 'Napoli', 'Juventus', 'Lazio', 'Fiorentina', 'Atalanta' for Italian teams)
- For Italian teams: Inter Milan = 'Inter', AC Milan = 'Milan', AS Roma = 'Roma', SSC Napoli = 'Napoli'
- IMPORTANT: For team goal questions, prefer using the players table with breakdown query, not the matches table

Table: players
Columns:
  - player      : Player full name
  - team        : Team name (e.g. 'Manchester City', 'Real Madrid')
  - league      : League name — 'England', 'Spain', 'Germany', 'Italy', 'France'
  - season      : Season string in format 'YYYY-YY' (e.g. '2023-24')
  - goals       : Total goals scored
  - assists     : Total assists
  - xG          : Expected goals (decimal)
  - xA          : Expected assists (decimal)
  - shots       : Total shots
  - key_passes  : Key passes made
  - minutes     : Minutes played
  - matches     : Matches played
  - yellow_cards: Yellow cards received
  - red_cards   : Red cards received
  - npg         : Non-penalty goals
  - npxG        : Non-penalty expected goals
  - penalty_goals: Goals scored from penalties (= goals - npg)

Notes:
- Use players table for: top scorers, most assists, xG leaders, player comparisons
- Team names in players table use full names (e.g. 'Manchester City', 'Real Madrid', 'Barcelona', 'Arsenal', 'Chelsea', 'Liverpool', 'Manchester United', 'Tottenham Hotspur', 'Juventus', 'AC Milan', 'Inter Milan', 'AS Roma', 'SSC Napoli', 'Bayern Munich', 'Borussia Dortmund', 'Paris Saint-Germain')
- Use LIKE with full name: WHERE team LIKE '%Manchester City%' not '%Man City%'
- NOTE: Players who transferred mid-season have team stored as 'Club1,Club2' (e.g. 'Chelsea,QPR'). Using LIKE '%Chelsea%' will correctly match these players.
- Use LIKE for player name search but be specific to avoid false matches: WHERE player LIKE '%Mohamed Salah%' not '%Salah%', WHERE player LIKE '%Erling Haaland%' not '%Haaland%'
- IMPORTANT: Do NOT add team or league filters for player queries unless the user explicitly mentions a team or league in the question
- If a club is mentioned in the question, add team filter: WHERE player LIKE '%Salah%' AND team LIKE '%Liverpool%'
- If no club mentioned and multiple players share a name, return ALL matching players with team and stats: SELECT player, team, season, goals FROM players WHERE player LIKE '%name%'
- For single player stats always include player name and team: SELECT player, team, goals, assists, penalty_goals FROM players WHERE player LIKE '%Mohamed Salah%' AND season='2023-24'
- NEVER use SUM() for single player queries — use direct SELECT with player name in WHERE clause
- IMPORTANT: When asked about total goals in a league, show per-team breakdown:
  SELECT team, SUM(goals) as total_goals, SUM(npg) as open_play_goals, SUM(penalty_goals) as penalty_goals FROM players WHERE league='LeagueName' AND season='YYYY-YY' GROUP BY team ORDER BY total_goals DESC LIMIT 20
- To get team penalties scored: SUM(penalty_goals) WHERE team LIKE '%Arsenal%' AND season=Y
- To get team non-penalty goals: SUM(npg) WHERE team LIKE '%Arsenal%' AND season=Y
- penalty_goals = goals - npg (already computed, use directly)
- For goal breakdown query: SELECT SUM(goals) as total, SUM(npg) as open_play_goals, SUM(penalty_goals) as penalty_goals FROM players WHERE team LIKE '%TeamName%' AND season='YYYY-YY'
"""
