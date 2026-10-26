# ScholarTrack (WEB-02) – Windows commands (use `py`, run inside this folder)
    py -m pip install -r requirements.txt
    py -m pytest -q                  # 8 tests on offline samples
    py tracker.py                    # refresh from sample fixtures (offline)
    py save_pages.py                 # LIVE: download + parse the 2 real pages (checks robots.txt)
    set SCHOLAR_LIVE=1 && py tracker.py   # LIVE refresh into the database
    py app.py                        # open http://127.0.0.1:5000  (Operator: /operator)
    py tracker.py --every 360        # scheduler (every 6 h)
Tip: delete scholartrack.db before switching from sample data to live data.
Revision demo: refresh once, then run `py -c "import tracker;tracker.refresh(override={'nsp':'fixtures/nsp_v2.html'})"` -> 1 change + 1 alert.
Adapters: `parse_tn` (table rows) and `parse_nsp` (page-text based) in tracker.py. If `save_pages.py` shows 0 notices, the real HTML differs: inspect one block and adjust the selectors.
