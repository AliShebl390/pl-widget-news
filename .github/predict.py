"""Builds predicted.json: a predicted XI for both teams in every fixture of fixtures.json.

Rules, per team:
  1. Start from the team's starting XI and formation in its last league match.
  2. "Regulars" are players who started at least 3 of the last 5 league matches.
  3. A regular who missed the last match but is available again returns to his
     usual position, replacing whoever played there.
  4. A starter who is now injured, suspended or unlikely (FPL chance <= 25%)
     drops out; the player who played that position most in the last 5
     matches takes his place (or, failing that, whoever came on for him).
  5. Doubtful players (FPL chance 50-75%) stay in, flagged with their chance.

Lineups come from ESPN's public API, availability from the FPL API.
"""
import json
import sys
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

FPL = "https://fantasy.premierleague.com/api"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1"
ABBR_ALIASES = {"MCI": "MNC", "MUN": "MAN"}
HISTORY = 5
REGULAR_STARTS = 3
UNLIKELY_CHANCE = 25
# FPL's element_type as an ESPN position.
FPL_POSITION = {1: "G", 2: "D", 3: "M", 4: "F"}

_cache = {}


def get(url):
    if url not in _cache:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (pl-widget-news)"})
        _cache[url] = json.load(urllib.request.urlopen(req, timeout=60))
    return _cache[url]


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower().replace("-", " ").strip()


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------------------------------------------------------- formation

def depth(pos):
    p = pos.upper()
    if p in ("G", "GK"): return 0
    if p == "SW": return 2
    if p.startswith("CD") or p in ("LB", "RB", "D"): return 1
    if "WB" in p: return 3
    if p.startswith("DM") or p.startswith("CDM"): return 4
    if p.startswith("CM") or p in ("LM", "RM", "M"): return 5
    if p.startswith("AM") or p in ("LW", "RW"): return 6
    # A paired forward (CF-L/CF-R) sits behind a lone central striker (F) when both are listed.
    if p in ("CF-L", "CF-R", "LF", "RF"): return 7
    if p.startswith("CF") or p in ("F", "ST"): return 8
    return 5


def across(pos):
    """Left to right: wide left, inside left, centre, inside right, wide right."""
    p = pos.upper()
    if p.endswith("-L"): return 1
    if p.endswith("-R"): return 3
    if p.startswith("L") and len(p) <= 3: return 0
    if p.startswith("R") and len(p) <= 3: return 4
    return 2


def lines(formation, starters):
    """Same grouping as the app: goalkeeper, then formation lines, each left to right."""
    ordered = sorted(starters, key=lambda p: (depth(p["position"]), p["place"]))
    keeper = next((p for p in ordered if depth(p["position"]) == 0), ordered[0])
    outfield = [p for p in ordered if p is not keeper]
    sizes = [int(x) for x in formation.split("-") if x.strip().isdigit()]
    if sizes and sum(sizes) == len(outfield):
        groups, start = [], 0
        for n in sizes:
            groups.append(outfield[start:start + n])
            start += n
    else:
        by_depth = defaultdict(list)
        for p in outfield:
            by_depth[depth(p["position"])].append(p)
        groups = [by_depth[k] for k in sorted(by_depth)]
    return [[keeper]] + [sorted(g, key=lambda p: (across(p["position"]), p["place"])) for g in groups]


# ---------------------------------------------------------------- data

def espn_event_id(fixture, teams):
    home = ABBR_ALIASES.get(teams[fixture["team_h"]]["short_name"], teams[fixture["team_h"]]["short_name"])
    away = ABBR_ALIASES.get(teams[fixture["team_a"]]["short_name"], teams[fixture["team_a"]]["short_name"])
    day = parse_time(fixture["kickoff_time"]).date()
    for d in (day, day - timedelta(days=1), day + timedelta(days=1)):
        board = get(f"{ESPN}/scoreboard?dates={d.strftime('%Y%m%d')}")
        for e in board.get("events", []):
            sides = {c["homeAway"]: c["team"]["abbreviation"] for c in e["competitions"][0]["competitors"]}
            if sides.get("home") == home and sides.get("away") == away:
                return e["id"]
    return None


def team_sheet(event_id, espn_abbr):
    """The team's roster in one match: starters, formation, and who came on for whom."""
    summary = get(f"{ESPN}/summary?event={event_id}")
    for r in summary.get("rosters", []):
        if r["team"].get("abbreviation") != espn_abbr:
            continue
        players = []
        for p in r.get("roster", []):
            a = p["athlete"]
            players.append({
                "id": a["id"],
                "name": a["displayName"],
                "shortName": a.get("shortName", a["displayName"]),
                "jersey": p.get("jersey", ""),
                "position": (p.get("position") or {}).get("abbreviation", ""),
                "place": int(p.get("formationPlace") or 0),
                "starter": bool(p.get("starter")),
            })
        replaced_by = {}
        for k in summary.get("keyEvents", []):
            if k["type"].get("type") == "substitution" and len(k.get("participants", [])) >= 2:
                on, off = (x["athlete"]["id"] for x in k["participants"][:2])
                replaced_by[off] = on
        if any(p["starter"] for p in players):
            return {"formation": r.get("formation", ""), "players": players, "replacedBy": replaced_by}
    return None


class Availability:
    def __init__(self, elements):
        self.by_team = defaultdict(list)
        for e in elements:
            self.by_team[e["team"]].append(e)

    def find(self, name, fpl_team):
        cands = self.by_team[fpl_team]
        n = norm(name)
        for e in cands:
            if norm(f"{e['first_name']} {e['second_name']}") == n or norm(e["web_name"]) == n:
                return e
        parts = n.split()
        m = [e for e in cands if parts[-1] in norm(e["second_name"]).split() or norm(e["web_name"]) == parts[-1]]
        if len(m) == 1:
            return m[0]
        first = [e for e in m if norm(e["first_name"]).split()[0] == parts[0]]
        if len(first) == 1:
            return first[0]
        # Names written in a different order, e.g. ESPN "Fatawu Issahaku" vs FPL "Abdul Fatawu".
        any_part = [e for e in cands if any(x in norm(e["second_name"]).split() or x == norm(e["web_name"]) for x in parts)]
        return any_part[0] if len(any_part) == 1 else None

    def status(self, name, fpl_team):
        """('available'|'doubtful'|'out', chance, news)."""
        e = self.find(name, fpl_team)
        if e is None:
            return "available", None, ""
        chance = e.get("chance_of_playing_next_round")
        if e["status"] in ("i", "s", "u", "n") or (chance is not None and chance <= UNLIKELY_CHANCE):
            return "out", chance, e.get("news", "")
        if e["status"] == "d" or (chance is not None and chance < 100):
            return "doubtful", chance, e.get("news", "")
        return "available", chance, ""


# ---------------------------------------------------------------- prediction

def predict(team_id, before, fixtures, teams, avail):
    abbr = teams[team_id]["short_name"]
    espn_abbr = ABBR_ALIASES.get(abbr, abbr)
    past = sorted(
        (f for f in fixtures
         if team_id in (f["team_h"], f["team_a"]) and f.get("finished") and f.get("kickoff_time")
         and parse_time(f["kickoff_time"]) < before),
        key=lambda f: f["kickoff_time"], reverse=True,
    )[:HISTORY]

    sheets = []
    for f in past:
        eid = espn_event_id(f, teams)
        sheet = team_sheet(eid, espn_abbr) if eid else None
        if sheet:
            sheets.append(sheet)
    if not sheets:
        return None

    starts = Counter()
    positions = defaultdict(Counter)
    squad = {}
    for s in sheets:
        for p in s["players"]:
            squad.setdefault(p["id"], p)
            if p["starter"]:
                starts[p["id"]] += 1
                positions[p["id"]][p["position"]] += 1

    # ESPN lists every substitute as "SUB". Give them a real position (where they start, or FPL's
    # GK/DEF/MID/FWD), or a goalkeeper on the bench never counts as one and an injured keeper is never replaced.
    for pid, p in squad.items():
        if p["position"] == "SUB":
            fpl = avail.find(p["name"], team_id)
            usual = positions[pid].most_common(1)[0][0] if positions[pid] else None
            squad[pid] = dict(p, position=usual or (FPL_POSITION.get(fpl["element_type"], "M") if fpl else "M"))

    last = sheets[0]
    xi = [dict(p) for p in last["players"] if p["starter"]]
    in_xi = {p["id"] for p in xi}
    changes = []

    def usual_position(pid):
        return positions[pid].most_common(1)[0][0] if positions[pid] else squad[pid]["position"]

    def take_slot(slot, player):
        """Put `player` into `slot`, keeping the slot's position so the shape holds."""
        new = dict(squad[player])
        new["position"], new["place"] = slot["position"], slot["place"]
        return new

    # Regulars who missed the last match and are available again.
    for pid, n in starts.most_common():
        if n < REGULAR_STARTS or pid in in_xi:
            continue
        p = squad[pid]
        state, chance, _ = avail.status(p["name"], team_id)
        if state == "out":
            continue
        pos = usual_position(pid)
        stand_ins = [s for s in xi if s["position"] == pos and starts[s["id"]] < n] or \
                    [s for s in xi if depth(s["position"]) == depth(pos) and starts[s["id"]] < n]
        if not stand_ins:
            continue
        slot = min(stand_ins, key=lambda s: starts[s["id"]])
        xi[xi.index(slot)] = take_slot(slot, pid)
        in_xi.discard(slot["id"]); in_xi.add(pid)
        changes.append({"in": p["name"], "out": slot["name"], "kind": "regular",
                        "reason": f"Usual starter ({n} of last {len(sheets)} matches)"})

    # Starters who are now unavailable.
    for slot in list(xi):
        state, chance, news = avail.status(slot["name"], team_id)
        if state != "out":
            continue
        def score(pid):
            q = squad[pid]
            return (
                positions[pid][slot["position"]],
                sum(c for pos, c in positions[pid].items() if depth(pos) == depth(slot["position"])),
                1 if last["replacedBy"].get(slot["id"]) == pid else 0,
                starts[pid],
            )
        candidates = [
            pid for pid, q in squad.items()
            if pid not in in_xi and avail.status(q["name"], team_id)[0] != "out"
            and (depth(q["position"]) == 0) == (depth(slot["position"]) == 0)
        ]
        if not candidates:
            continue
        pick = max(candidates, key=score)
        xi[xi.index(slot)] = take_slot(slot, pick)
        in_xi.discard(slot["id"]); in_xi.add(pick)
        changes.append({"in": squad[pick]["name"], "out": slot["name"], "kind": "unavailable",
                        "reason": news or "Unavailable"})

    out = []
    for line in lines(last["formation"], xi):
        row = []
        for p in line:
            state, chance, news = avail.status(p["name"], team_id)
            row.append({
                "espnId": p["id"], "name": p["name"], "shortName": p["shortName"], "jersey": p["jersey"],
                "doubtful": state == "doubtful", "chance": chance, "news": news if state == "doubtful" else "",
                "returning": any(c["in"] == p["name"] and c["kind"] == "regular" for c in changes),
            })
        out.append(row)
    return {"formation": last["formation"], "lineup": out, "changes": changes, "basedOn": len(sheets)}


def main():
    plan = json.load(open("fixtures.json", encoding="utf-8"))
    boot = get(f"{FPL}/bootstrap-static/")
    teams = {t["id"]: t for t in boot["teams"]}
    by_name = {t["name"]: t["id"] for t in boot["teams"]}
    fixtures = get(f"{FPL}/fixtures/")
    avail = Availability(boot["elements"])

    result = {"generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "event": plan.get("event"), "matches": {}}
    for f in plan["fixtures"]:
        before = parse_time(f["kickoff"])
        entry = {}
        for side in ("home", "away"):
            tid = by_name.get(f[side])
            try:
                entry[side] = predict(tid, before, fixtures, teams, avail) if tid else None
            except Exception as ex:  # one team failing shouldn't sink the rest
                print(f"  {f[side]}: failed ({ex})", file=sys.stderr)
                entry[side] = None
            p = entry[side]
            print(f"{f[side]:>16}: " + (f"{p['formation']} from {p['basedOn']} matches, {len(p['changes'])} change(s)" if p else "no prediction"))
        result["matches"][str(f["id"])] = entry

    # Runs every hour; only a real change (an injury, a returning player) rewrites the file.
    try:
        old = json.load(open("predicted.json", encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    if old.get("matches") == result["matches"] and old.get("event") == result["event"]:
        print("No change")
        return
    with open("predicted.json", "w", encoding="utf-8") as out:
        json.dump(result, out, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
