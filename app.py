from datetime import datetime, timezone, timedelta
from flask import Flask, request, render_template_string, redirect
import tracker as st
app = Flask(__name__)
PAGE = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><title>ScholarTrack</title>
<style>body{font:16px system-ui;margin:auto;max-width:960px;padding:1rem}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ccc;padding:.4rem;text-align:left}
.stale{color:#b00020;font-weight:600}.ok{color:#116611}.w{background:#fff3cd;padding:.5rem;margin:.3rem 0}@media(max-width:640px){td,th{display:block}}</style>
<h1>ScholarTrack</h1><nav><a href="/">Dashboard</a> | <a href="/operator">Operator</a></nav>
<p><small>Keyword tags are hints only, not eligibility decisions. Always confirm on the official page.</small></p>
<form>Search <input name=q value="{{q}}"> Level <select name=level><option value="">All{% for l in levels %}<option {{'selected' if l==level}}>{{l}}{% endfor %}</select>
Category <select name=cat><option value="">All<option {{'selected' if cat=='scholarship'}}>scholarship<option {{'selected' if cat=='fellowship'}}>fellowship</select><button>Filter</button></form>
<h2>Alerts</h2>{% for a in alerts %}<div class=w role=alert>{{a.message}}</div>{% else %}<p>No alerts.</p>{% endfor %}
<h2>Deadline timeline (soonest first)</h2><table aria-label="Notices"><tr><th>Title<th>Provider<th>Level<th>Deadline<th>Countdown<th>Status<th>Last checked<th>Tags</tr>
{% for n in rows %}<tr><td><a href="{{n.url}}" rel=noopener>{{n.title}}</a><td>{{n.provider}}<td>{{n.education_level}}<td>{{n.due or 'Unknown (not published)'}}<td>{{n.count}}<td>{{n.notice_status}}
<td class="{{'stale' if n.stale else 'ok'}}">{{n.verified_at}} {{'STALE snapshot' if n.stale else 'recent snapshot'}}<td>{{n.tags}}</tr>{% endfor %}</table>"""
OP = """<!doctype html><title>Operator</title><h1>Operator</h1><a href="/">Back</a><form method=post action=/refresh><button>Manual refresh</button></form>
<table border=1 cellpadding=4><tr><th>Time<th>Source<th>Status<th>Items<th>Error</tr>{% for l in logs %}<tr><td>{{l.ran_at}}<td>{{l.source_id}}<td>{{l.status}}<td>{{l['items']}}<td>{{l.error or ''}}</tr>{% endfor %}</table>"""

def countdown(due):
    if not due: return "No confirmed deadline"
    s = datetime.fromisoformat(due) - datetime.now(timezone.utc)
    return "Closed" if s.total_seconds() < 0 else f"{s.days}d {s.seconds // 3600}h left"

@app.route("/")
def index():
    q, level, cat = (request.args.get(k, "") for k in ("q", "level", "cat")); c = st.db()
    rows = []
    for r in c.execute("SELECT * FROM notices WHERE title LIKE ? AND (?='' OR education_level=?) AND (?='' OR notice_type=?) ORDER BY due_at IS NULL, due_at", (f"%{q}%", level, level, cat, cat)):
        d = dict(r); due = r["due_at"]
        d["due"] = f"{datetime.fromisoformat(due).astimezone(timezone(timedelta(seconds=st.TZ.get(r['timezone'], 0)))):%Y-%m-%d %H:%M} {r['timezone']}" if due else None
        d["count"] = countdown(due); d["stale"] = datetime.now(timezone.utc) - datetime.fromisoformat(r["verified_at"]) > timedelta(hours=24)
        d["tags"] = ", ".join(k for k in st.KEYWORDS if k in (r["eligibility_excerpt"] or "").lower()); rows.append(d)
    levels = [r[0] for r in c.execute("SELECT DISTINCT education_level FROM notices")]
    return render_template_string(PAGE, rows=rows, q=q, level=level, cat=cat, levels=levels, alerts=c.execute("SELECT * FROM alerts ORDER BY alert_id DESC LIMIT 10").fetchall())

@app.route("/operator")
def operator(): return render_template_string(OP, logs=st.db().execute("SELECT * FROM scrape_log ORDER BY id DESC LIMIT 30").fetchall())

@app.route("/refresh", methods=["POST"])
def do_refresh(): st.refresh(); return redirect("/operator")

if __name__ == "__main__": app.run(debug=False)
