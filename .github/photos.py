"""Picks the best photo for every Premier League player and writes photos.json.

The official Premier League photos miss some players and keep transferred
players in their old shirts. TheSportsDB (a free, community-kept database)
usually has a current cutout, so for each FPL player, in order:

1. TheSportsDB's cutout, when it lists the player at his current club;
2. the official Premier League photo, when there is one;
3. TheSportsDB's cutout (or thumbnail) even from an old club;
4. nothing (the app shows an initial).

TheSportsDB's free API drops connections when asked too fast, so requests are
spaced out and each run only looks at players that are new, have moved club,
or were last checked over a week ago (up to a limit per run).

photos.json: {"generatedAt": ..., "players": {"<FPL code>": {"u": url, "s": source, "t": team, "c": checked}}}
The app only reads "u".
"""
import json
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

FPL = "https://fantasy.premierleague.com/api/bootstrap-static/"
TSDB = "https://www.thesportsdb.com/api/v1/json/123/searchplayers.php?p="
PL = [
    "https://resources.premierleague.com/premierleague25/photos/players/110x140/{code}.png",
    "https://resources.premierleague.com/premierleague/photos/players/110x140/p{code}.png",
]
OUT = "photos.json"
PER_RUN = 450
RECHECK = timedelta(days=7)
GAP = 2.2

# A word TheSportsDB's club name contains, by FPL short name.
CLUBS = {
    "ARS": "arsenal", "AVL": "aston villa", "BHA": "brighton", "BOU": "bournemouth", "BRE": "brentford",
    "BUR": "burnley", "CHE": "chelsea", "COV": "coventry", "CRY": "crystal palace", "EVE": "everton",
    "FUL": "fulham", "HUL": "hull", "IPS": "ipswich", "LEE": "leeds", "LEI": "leicester", "LIV": "liverpool",
    "MCI": "manchester city", "MUN": "manchester united", "NEW": "newcastle", "NFO": "nottingham",
    "SOU": "southampton", "SUN": "sunderland", "TOT": "tottenham", "WHU": "west ham", "WOL": "wolverhampton",
}


def fetch(url, method="GET", tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": "Mozilla/5.0 (pl-widget-news)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read() if method == "GET" else b""
        except urllib.error.HTTPError as e:
            return e.code, b""
        except Exception:
            time.sleep(5 * (attempt + 1))
    return 0, b""


def plain(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).lower().strip()


def official(code):
    for u in PL:
        status, _ = fetch(u.format(code=code), method="HEAD")
        if status == 200:
            return u.format(code=code)
    return None


def tsdb(first, second, web):
    """TheSportsDB footballers matching the player's name."""
    for name in (f"{first} {second}", web if web != second else None):
        if not name:
            continue
        status, body = fetch(TSDB + urllib.parse.quote(name))
        time.sleep(GAP)
        if status != 200 or not body:
            continue
        try:
            found = json.loads(body).get("player") or []
        except ValueError:
            continue
        found = [p for p in found if p.get("strSport") == "Soccer" and (p.get("strCutout") or p.get("strThumb"))]
        if found:
            return found
    return []


def main():
    now = datetime.now(timezone.utc)
    boot = json.load(urllib.request.urlopen(urllib.request.Request(FPL, headers={"User-Agent": "Mozilla/5.0"}), timeout=60))
    teams = {t["id"]: t["short_name"] for t in boot["teams"]}
    try:
        state = json.load(open(OUT, encoding="utf-8")).get("players", {})
    except (OSError, ValueError):
        state = {}

    def due(e):
        old = state.get(str(e["code"]))
        if not old or old.get("t") != e["team"]:
            return 0  # new or moved: first
        if old.get("s") != "tsdb" and now - datetime.fromisoformat(old["c"]) > RECHECK:
            return 1
        return None

    waiting = [(p, e) for e in boot["elements"] if e.get("status") != "u" and (p := due(e)) is not None]
    queue = [e for _, e in sorted(waiting, key=lambda pe: pe[0])][:PER_RUN]
    print(f"{len(queue)} players to check")

    for e in queue:
        code, club = str(e["code"]), CLUBS.get(teams[e["team"]], "")
        found = tsdb(e["first_name"], e["second_name"], e["web_name"])
        here = [p for p in found if club and club in plain(p.get("strTeam") or "")]
        if here and here[0].get("strCutout"):
            url, source = here[0]["strCutout"], "tsdb"
        elif (pl := official(code)):
            url, source = pl, "pl"
        elif found:
            url, source = found[0].get("strCutout") or found[0].get("strThumb"), "tsdb-old"
        else:
            url, source = None, "none"
        state[code] = {"u": url, "s": source, "t": e["team"], "c": now.isoformat()}

    # Players no longer in the game drop out.
    codes = {str(e["code"]) for e in boot["elements"]}
    state = {k: v for k, v in state.items() if k in codes}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"generatedAt": now.isoformat(), "players": state}, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    counts = {}
    for v in state.values():
        counts[v["s"]] = counts.get(v["s"], 0) + 1
    print(counts)


if __name__ == "__main__":
    main()
