import re, sqlite3, hashlib, json, time, os, urllib.robotparser as rp
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dp

DB = os.environ.get("SCHOLAR_DB", "scholartrack.db")
UA = "ScholarTrackBot/1.0 (student project; contact: you@example.com)"
TZ = {"IST": 19800, "EST": -18000, "PST": -28800, "UTC": 0, "GMT": 0}
KEYWORDS = ["women", "citizen", "resident", "merit", "need-based", "stem", "disab"]
SCHEMA = """
CREATE TABLE IF NOT EXISTS notices(notice_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
 notice_type TEXT, title TEXT NOT NULL, provider TEXT, education_level TEXT, discipline TEXT, region TEXT,
 residency_rule TEXT, benefit_text TEXT, eligibility_excerpt TEXT, due_at TEXT, timezone TEXT,
 captured_at TEXT NOT NULL, verified_at TEXT NOT NULL, content_hash TEXT NOT NULL,
 notice_status TEXT NOT NULL DEFAULT 'active' CHECK(notice_status IN('active','withdrawn')));
CREATE TABLE IF NOT EXISTS changes(change_id INTEGER PRIMARY KEY AUTOINCREMENT, notice_id TEXT NOT NULL REFERENCES notices,
 previous_deadline TEXT, updated_deadline TEXT, detected_at TEXT, UNIQUE(notice_id, updated_deadline));
CREATE TABLE IF NOT EXISTS alerts(alert_id INTEGER PRIMARY KEY AUTOINCREMENT, change_id INTEGER UNIQUE REFERENCES changes,
 message TEXT, created_at TEXT, delivered_at TEXT);
CREATE TABLE IF NOT EXISTS scrape_log(id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, ran_at TEXT, status TEXT, items INT, error TEXT);
"""
now = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")

def db(path=None):
    c = sqlite3.connect(path or DB); c.row_factory = sqlite3.Row; c.executescript(SCHEMA); return c

def parse_deadline(text):
    """Return (utc ISO or None, tz label). Unknown/unparseable -> None, never a guessed date."""
    t = (text or "").strip()
    if not t or t.upper() in {"TBA", "TBD", "N/A", "-"}: return None, None
    try:
        d = dp.parse(t, tzinfos=TZ)
    except (ValueError, OverflowError): return None, None
    if d.tzinfo is None: return None, None   # no timezone stated -> treat as unconfirmed
    return d.astimezone(timezone.utc).isoformat(timespec="minutes"), (t.split()[-1] if t.split()[-1].isalpha() else "UTC")

def parse_table(html):
    for tr in BeautifulSoup(html, "html.parser").select("tr.notice"):
        td = [x.get_text(strip=True) for x in tr.find_all("td")]
        if len(td) < 6 or not tr.find("a"): continue
        yield dict(title=td[0], provider=td[1], education_level=td[2], residency_rule=td[3], deadline=td[4], url=tr.find("a")["href"], eligibility_excerpt=td[3])

def parse_cards(html):
    for c in BeautifulSoup(html, "html.parser").select("div.card"):
        g = lambda s: (c.select_one(s).get_text(strip=True) if c.select_one(s) else "")
        if not c.find("a") or not g("h3"): continue
        yield dict(title=g("h3"), provider=g(".provider"), education_level=g(".level"), eligibility_excerpt=g(".elig"),
                   residency_rule="", deadline=g("time"), url=c.find("a")["href"])


TN = "https://tndce.tn.gov.in/Home/scholarship"
NSP = "https://scholarships.gov.in/All-Scholarships"
def slug(s): return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]
def level_of(t):
    t = " " + t.lower() + " "
    for k, v in (("phd", "PhD"), ("postgraduate", "Postgraduate"), (" pg ", "Postgraduate"), ("diploma", "Diploma"),
                 ("undergraduate", "Undergraduate"), (" ug ", "Undergraduate"), ("college", "Undergraduate"), ("school", "School"), ("class", "School")):
        if k in t: return v
    return "Not stated"

def parse_tn(html):
    """Tamil Nadu DCE page: table rows  # | scheme | provider | eligibility | benefit | how to apply. No deadlines published -> unknown."""
    for tr in BeautifulSoup(html, "html.parser").select("tr"):
        td = [c.get_text(" ", strip=True) for c in tr.find_all("td")]
        if len(td) < 5 or not td[1] or not td[2]: continue
        yield dict(title=td[1], provider=td[2], eligibility_excerpt=td[3][:400], benefit_text=td[4], residency_rule="",
                   education_level=level_of(td[1] + " " + td[3]), deadline="", url=TN + "#" + slug(td[1]))

def parse_nsp(html):
    """NSP scheme list, parsed from page text so it does not depend on exact tags.
    Block: [department] title / 'Scheme Open till : DD-MM-YYYY' / ...  Deadline has no time/zone: ASSUMED 23:59 IST."""
    L = [x.strip() for x in BeautifulSoup(html, "html.parser").get_text("\n").split("\n") if x.strip()]
    dept = ""
    for i, l in enumerate(L):
        m = re.match(r"Scheme (Open till|Closed on)\s*:\s*(\d{2})-(\d{2})-(\d{4})", l)
        if not m or i < 1: continue
        if i >= 2 and L[i - 2] != "FAQ" and not L[i - 2].startswith("Scheme"): dept = L[i - 2]
        yield dict(title=L[i - 1], provider=dept, eligibility_excerpt="", benefit_text="", residency_rule="",
                   education_level=level_of(L[i - 1]), deadline=f"{m[4]}-{m[3]}-{m[2]} 23:59 IST", url=NSP + "#" + slug(L[i - 1]))

ADAPTERS = {"table": parse_table, "cards": parse_cards, "tn": parse_tn, "nsp": parse_nsp}

def fetch(src, override=None):
    """Fixture mode reads local files. Live mode checks robots.txt, uses timeout + retry/backoff."""
    if override or src.get("fixture") and not os.environ.get("SCHOLAR_LIVE"):
        return open(override or src["fixture"], encoding="utf-8").read()
    u = src["approved_url"]; p = urlparse(u)
    r = rp.RobotFileParser(f"{p.scheme}://{p.netloc}/robots.txt"); r.read()
    if not r.can_fetch(UA, u): raise PermissionError("blocked by robots.txt")
    for i in range(3):
        try:
            x = requests.get(u, headers={"User-Agent": UA}, timeout=10); x.raise_for_status(); return x.text
        except requests.RequestException:
            if i == 2: raise
            time.sleep(2 ** i)

def upsert(c, src, n):
    nid = hashlib.sha1((src["id"] + n["url"]).encode()).hexdigest()[:12]
    due, tz = parse_deadline(n["deadline"])
    status = "withdrawn" if "withdrawn" in (n["eligibility_excerpt"] + n["title"]).lower() else "active"
    h = hashlib.sha256(json.dumps([n["title"], due, status, n["eligibility_excerpt"]]).encode()).hexdigest()
    t = now(); old = c.execute("SELECT * FROM notices WHERE notice_id=?", (nid,)).fetchone()
    vals = dict(source_id=src["id"], url=n["url"], notice_type=src["notice_type"], title=n["title"], provider=n["provider"],
                education_level=n["education_level"], residency_rule=n["residency_rule"], eligibility_excerpt=n["eligibility_excerpt"], benefit_text=n.get("benefit_text", ""), region=src.get("region"),
                due_at=due, timezone=tz, content_hash=h, notice_status=status)
    if not old:
        c.execute("INSERT INTO notices(notice_id,captured_at,verified_at,%s) VALUES(?,?,?,%s)" % (",".join(vals), ",".join("?" * len(vals))), (nid, t, t, *vals.values()))
        return
    if old["content_hash"] != h:
        ev = [("DEADLINE", old["due_at"], due)] if old["due_at"] != due else []
        if status == "withdrawn" and old["notice_status"] != "withdrawn": ev.append(("WITHDRAWN", old["due_at"], "WITHDRAWN"))
        for kind, prev, new in ev:   # UNIQUE(notice_id, updated_deadline) => one alert per meaningful revision
            cur = c.execute("INSERT OR IGNORE INTO changes(notice_id,previous_deadline,updated_deadline,detected_at) VALUES(?,?,?,?)", (nid, prev, str(new), t))
            if cur.rowcount:
                c.execute("INSERT INTO alerts(change_id,message,created_at) VALUES(?,?,?)", (cur.lastrowid, f"{kind} change: {n['title']} ({prev or 'unknown'} -> {new or 'unknown'}) | source: {n['url']}", t))
        c.execute("UPDATE notices SET %s WHERE notice_id=?" % ",".join(f"{k}=?" for k in vals), (*vals.values(), nid))
    c.execute("UPDATE notices SET verified_at=? WHERE notice_id=?", (t, nid))

def refresh(sources_file="sources.json", path=None, override=None):
    c = db(path)
    for src in json.load(open(sources_file)):
        try:
            items = list(ADAPTERS[src["adapter"]](fetch(src, (override or {}).get(src["id"]))))
            if not items: raise ValueError("parsed 0 notices (layout changed?)")
            for n in items: upsert(c, src, n)
            c.execute("INSERT INTO scrape_log(source_id,ran_at,status,items) VALUES(?,?,?,?)", (src["id"], now(), "ok", len(items)))
        except Exception as e:   # flagged, never silently skipped
            c.execute("INSERT INTO scrape_log(source_id,ran_at,status,items,error) VALUES(?,?,?,?,?)", (src["id"], now(), "FAILED", 0, repr(e)))
        c.commit()

if __name__ == "__main__":
    import sys
    every = int(sys.argv[sys.argv.index("--every") + 1]) if "--every" in sys.argv else 0
    while True:
        refresh()
        if not every: break
        time.sleep(every * 60)   # scheduled refresh (or use cron)
