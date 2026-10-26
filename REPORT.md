# ScholarTrack – Final Report (template, fill in bracketed fields)
**Cover:** ScholarTrack | [Student/Team IDs] | Mentor: [name] | Academic year 2026
## 1. Abstract & Context
Problem: scholarship info is scattered; students miss or trust stale deadlines. Stakeholders: students, advisors, operator. Success: every notice source-linked, unknown deadlines never guessed, revisions alerted once, failures visible.
Personas: (1) *Ananya*, final-year B.Tech student in Chennai, wants deadlines for postgraduate funding sorted by date. (2) *Rahul*, university scholarship advisor, needs to see which notices changed or were withdrawn. Usefulness: one searchable timeline with citations. Limitations: scheduled snapshots are not real-time; the tool never decides eligibility; keywords are hints.
## 2. Source Selection
| | Source 1 | Source 2 |
|---|---|---|
| URL | [approved URL, table layout] | [approved URL, card layout] |
| robots.txt / terms | [date reviewed, result] | [date reviewed, result] |
| Fields | title, provider, level, residency, deadline, link | same plus eligibility text |
| Schedule | every 6h, backoff on failure | same |
| Risk / alternative | layout change -> operator flagged; use RSS/API if offered | same |
Crawl policy: robots.txt honoured, identified User-Agent, no login/CAPTCHA bypass, only public notice data (no personal data).
## 3. SRS
Use cases: browse timeline, search/filter, view alert, operator reviews failed scrapes. Requirements: see sections 05–07 of the brief; all implemented except where listed in Limitations.
Architecture: Adapters (table, cards) -> normalizer -> SQLite upsert + change detector -> alerts -> Flask dashboard/operator.
ER: `notices 1--* changes 1--0..1 alerts`; `scrape_log` per source run.
## 4. Implementation
Collection: `fetch()` + adapter per layout. Normalization: `parse_deadline()` converts to UTC and keeps the original timezone label; missing/unparseable/no-timezone -> NULL. Idempotency: `notice_id = sha1(source+url)`, content hash skips unchanged rows. Change detection: hash differs -> compare due_at/status -> `changes` with UNIQUE(notice_id, updated_deadline) so one alert per revision. Scheduling: `--every N` loop or cron.
## 5. Testing
| Test | Input | Expected | Actual |
|---|---|---|---|
| Unknown deadline | "TBA" | NULL | [pass] |
| Correction | source_a_v2 | update + 1 change, still 4 notices | [pass] |
| Alert dedupe | refresh v2 twice | 1 alert per revision | [pass] |
| Inaccessible source | missing file | FAILED log | [pass] |
| Timezone | 17:00 IST | 11:30 UTC | [pass] |
Add screenshots of dashboard, alerts, operator page. TODO: malformed-HTML and duplicate fixtures.
## 6. Evaluation
Collection quality [fields captured / total], alert precision [true alerts / alerts], refresh time [seconds]. Limitations: depends on page layouts, timezone abbreviations table is small.
## 7. Deployment
Setup per README; configuration via env vars; monitor `/operator` and scrape_log.
## 8. Ethics & Conclusion
Only public notices, rate limited, no personal data, keyword tags are not eligibility decisions. Gaps: no email delivery (alerts logged in DB), no auth on operator page. Future: email/Telegram alerts, RSS/API adapters, login for operator.
## Appendix
[Screenshots, sample rows, `git log --oneline`]
