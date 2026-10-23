# Team news routine

You keep `news.json` in this repo up to date. An Android app reads it to show
Premier League team news, coach quotes and predicted lineups for upcoming
matches. Work economically: this runs on a personal subscription, so use as
few searches and page fetches as you can.

## 1. Find the matches

Read `fixtures.json` in this repo. A GitHub Action refreshes it shortly before
each run with the FPL fixtures kicking off in the next 4 days: each has the
FPL fixture `id`, the `home` and `away` team names and the `kickoff` time
(UTC). Don't try to reach the FPL API yourself; this sandbox can't.

If `generatedAt` is more than a day old, the Action didn't run: say so in your
final message and stop without committing.

**If `fixtures` is empty, stop here.** Don't search, don't commit.

## 2. Research

Start with round-up articles that cover many matches at once, for example
BBC Sport's "Premier League team news" or premierleague.com's "team news"
round-up. Only then search for specific teams that the round-ups don't cover,
or for a team's pre-match press conference. Aim for about one search per
match beyond the round-ups, and fetch only the pages you need.

Use reputable sources (BBC Sport, Sky Sports, premierleague.com, club sites,
The Athletic, the Guardian, the Evening Standard and similar). Never invent
anything: every player item and quote must come from a page you actually read.

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
