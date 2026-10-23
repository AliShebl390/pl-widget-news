# pl-widget-news

Team news for the PL Widget Android app.

Once per gameweek, a Claude Code routine follows [ROUTINE.md](ROUTINE.md) and
rewrites [news.json](news.json). The app reads the file from
`raw.githubusercontent.com`.

The routine is started by the "Team news trigger" GitHub Action, which checks
the FPL API hourly. About two hours before each FPL deadline it writes the
gameweek's fixtures to `fixtures.json` (the routine's sandbox can't reach the
FPL API), records the gameweek in `state.json` so it fires only once, and
sends a `repository_dispatch` event that starts the routine. To run it by
hand, use "Run workflow" on the Action with "force" ticked.

`teams.json` maps Fantasy Premier League team ids to names for the current
season.
