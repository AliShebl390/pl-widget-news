# pl-widget-news

Team news for the PL Widget Android app.

A scheduled Claude Code routine follows [ROUTINE.md](ROUTINE.md) twice a week
(Friday and Monday evenings) and rewrites [news.json](news.json). The app reads
the file from `raw.githubusercontent.com`.

A GitHub Action writes `fixtures.json` (upcoming FPL fixtures) an hour before
each run, because the routine's sandbox can't reach the FPL API.

`teams.json` maps Fantasy Premier League team ids to names for the current
season.
