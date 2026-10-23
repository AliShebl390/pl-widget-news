# Team news routine

You keep `news.json` in this repo up to date. An Android app reads it to show
Premier League team news, coach quotes and predicted lineups for upcoming
matches.

**Goal: cover both teams in every fixture.** This runs on a personal
subscription, so don't waste searches, but thin coverage is the bigger
failure: a run that covers 4 of 20 teams has not done its job.

## 1. Find the matches

Read **all** of `fixtures.json` in this repo (use `cat` with no `head`, or
`python3 -m json.tool`; never truncate it). A GitHub Action writes it about two
hours before each FPL deadline and then starts this routine. It holds the
gameweek (`event`), its `deadline`, and every fixture in that gameweek: the
FPL fixture `id`, the `home` and `away` team names and the `kickoff` time
(UTC). Don't try to reach the FPL API yourself; this sandbox can't.

If `generatedAt` is more than 12 hours old, the Action didn't prepare this
run: say so in your final message and stop without committing.

**If `fixtures` is empty, stop here.** Don't search, don't commit.

## 2. Research

Searches easily return old seasons' articles. **Always put the current date
context in the query** — the gameweek number from `fixtures.json` plus the
month and year (e.g. "Gameweek 8 October 2026") — and discard any page not
published in the last 7 days.

Work in this order:

1. **Round-ups first.** Fetch these and take everything they say about the
   teams in `fixtures.json`:
   - Fantasy Football Scout's team news for the gameweek
     (fantasyfootballscout.co.uk)
   - premierleague.com's "Predicted line-ups for Premier League teams in
     Matchweek N" (also gives formations and full XIs)
   - Sky Sports or BBC Sport team news for the weekend, if found
2. **Then fill the gaps, team by team.** Make a list of teams the round-ups
   didn't cover (or covered without a predicted XI). For each, do one search
   like "<team> team news <opponent> press conference <month year>" and read
   the best recent result. Good per-club sources:
   - the club's official site (arsenal.com, chelseafc.com, liverpoolfc.com,
     mancity.com, …) for the manager's press conference
   - local outlets: Football London (Arsenal, Chelsea, Spurs, Fulham,
     Brentford, Palace, West Ham), Liverpool Echo (Liverpool, Everton),
     Manchester Evening News (Man City, Man Utd), Birmingham Live (Villa),
     Chronicle Live (Newcastle), and similar
   - Sports Mole and Sky Sports match previews, which usually give injuries
     and a predicted XI for both teams in one page
3. Stop searching for a team after two attempts that find nothing current.

Don't use social media (Facebook, X, Instagram): it needs a login and can't
be read reliably.

Never invent anything: every player item, quote and predicted lineup must
come from a page you actually read in this run.

## 3. Write news.json

Replace the whole file (old matches are dropped) with:

```json
{
  "generatedAt": "2026-10-23T16:00:00Z",
  "matches": {
    "<FPL fixture id>": {
      "home": TEAM,
      "away": TEAM
    }
  }
}
```

where `TEAM` is:

```json
{
  "summary": "One or two plain sentences on the team's situation.",
  "predictedFormation": "4-3-3",
  "predictedLineup": [
    ["David Raya"],
    ["Ben White", "William Saliba", "Gabriel Magalhães", "Riccardo Calafiori"],
    ["Declan Rice", "Martín Zubimendi", "Martin Ødegaard"],
    ["Bukayo Saka", "Viktor Gyökeres", "Gabriel Martinelli"]
  ],
  "players": [
    {
      "name": "Bukayo Saka",
      "status": "doubtful",
      "detail": "Hamstring; the manager said he'll be assessed on Friday.",
      "source": "BBC Sport",
      "url": "https://..."
    }
  ],
  "quotes": [
    {
      "speaker": "Mikel Arteta",
      "text": "A short direct quote, under 40 words.",
      "source": "Sky Sports",
      "url": "https://..."
    }
  ]
}
```

Rules:

- Keys of `matches` are the FPL fixture `id` as a string.
- Use players' full names as reported by the press.
- `predictedLineup`: 11 players, goalkeeper first, then one array per line
  from defence to attack; inside a line, order from the team's **left to
  right** (left-back first). It must match `predictedFormation`. Base it on
  the sources' predicted line-ups; if none exists, use the previous match's
  starting XI adjusted for the team news. Omit both fields if you can't
  support a prediction.
- `status` is one of `out`, `doubtful`, `suspended`, `returning`, `available`.
  Only list players with real news (injuries, suspensions, doubts, returns).
- At most 2 quotes per team, only genuine direct quotes.
- A team with no reliable news can be omitted.

Check the file parses (`python3 -m json.tool news.json > /dev/null`).

## 4. Publish

Commit only `news.json` with the message `News for <dates covered>` and push
to `main`.

End with a one-line coverage count, e.g. "Covered 18/20 teams, 14 predicted
lineups; missing: Hull (no current source), Coventry (no current source)".
