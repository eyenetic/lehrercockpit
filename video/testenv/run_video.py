"""Local multi-user runner for recording the explainer video. Test data only. Never used in production."""
import json, os, sys, threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:55442/postgres?sslmode=disable"
os.environ["CORS_ORIGIN"] = "http://localhost:8095"
os.environ["PUBLIC_APP_URL"] = "http://localhost:8095"
os.environ.setdefault("SCHOOL_NAME", "Beispiel-Schule")

import psycopg
_orig = psycopg.Connection.connect.__func__
def _connect(cls, *a, **kw):
    kw["prepare_threshold"] = None
    return _orig(cls, *a, **kw)
psycopg.Connection.connect = classmethod(_connect)
psycopg.connect = psycopg.Connection.connect

import backend.db as db
_lock = threading.RLock()
_orig_ctx = db.db_connection
@contextmanager
def serial():
    with _lock:
        with _orig_ctx() as conn:
            yield conn
db.db_connection = serial

import backend.persistence as persistence
if hasattr(persistence, "DbStore"):
    _pc = persistence.DbStore._connect
    @contextmanager
    def _serial_store(self):
        with _lock:
            with _pc(self) as conn:
                yield conn
    persistence.DbStore._connect = _serial_store

# ── Test timetable instead of a real WebUntis download ─────────────────────
P = {1: ("0800", "0845"), 2: ("0850", "0935"), 3: ("0955", "1040"), 4: ("1045", "1130"),
     5: ("1150", "1235"), 6: ("1240", "1325"), 7: ("1345", "1430")}
WEEK = {
    0: [(1, "Mathematik", "8b", "R 204"), (2, "Mathematik", "8b", "R 204"), (4, "Physik", "10a", "Physik 1"), (5, "Mathematik", "7c", "R 112")],
    1: [(2, "Physik", "9a", "Physik 1"), (3, "Mathematik", "10a", "R 204"), (4, "Mathematik", "10a", "R 204"), ("A", "0935", "0955", "Hof")],
    3: [(1, "Mathematik", "7c", "R 112"), (3, "Physik", "8b", "Physik 2"), (5, "Mathematik", "8b", "R 204"), (6, "Mathematik", "8b", "R 204")],
    2: [(1, "Mathematik", "10a", "R 204"), (2, "Mathematik", "10a", "R 204"), (3, "Physik", "9a", "Physik 1"), ("A", "1130", "1150", "Hof"), (5, "Mathematik", "7c", "R 112"), (6, "Physik", "10a", "Physik 1")],
    4: [(2, "Mathematik", "7c", "R 112"), (3, "Physik", "8b", "Physik 2"), (4, "Physik", "8b", "Physik 2")],
}


def test_ics() -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Test//DE"]
    monday = date(2026, 11, 2)
    for week in range(4):
        for wd, items in WEEK.items():
            day = monday + timedelta(days=7 * week + wd)
            ds = day.strftime("%Y%m%d")
            for n, it in enumerate(items):
                if it[0] == "A":
                    start, end, summary, desc, loc = it[1], it[2], "", "", it[3]
                else:
                    start, end = P[it[0]]
                    summary, desc, loc = it[1], it[2], it[3]
                lines += ["BEGIN:VEVENT", f"UID:test-{ds}-{n}", f"DTSTART;TZID=Europe/Berlin:{ds}T{start}00",
                          f"DTEND;TZID=Europe/Berlin:{ds}T{end}00", f"SUMMARY:{summary}", f"DESCRIPTION:{desc}",
                          f"LOCATION:{loc}", "STATUS:CONFIRMED", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


import backend.webuntis_adapter as wa
wa._download_ical = lambda url: test_ics()
import backend.ical_utils as iu
_orig_fetch = iu.fetch_calendar_text
def _fake_fetch(url, *a, **kw):
    return test_ics() if "webuntis" in str(url) else _orig_fetch(url, *a, **kw)
iu.fetch_calendar_text = _fake_fetch

import app as appmod
sys.path.insert(0, HERE)
import fake_sources
fake_sources.install()
from backend.api.helpers import set_session_cookie
from backend.auth.session import create_session
from flask import redirect, request, jsonify

flask_app = appmod.app


@flask_app.route("/__dev/login/<int:user_id>")
def dev_login(user_id):
    with db.db_connection() as conn:
        session = create_session(conn, user_id)
    resp = redirect("/")
    set_session_cookie(resp, session.id)
    return resp


@flask_app.route("/__dev/invite")
def dev_invite():
    from backend import invitations
    with db.db_connection() as conn:
        invite = invitations.create(conn, kind="personal", name=request.args.get("name", "Frau Beispiel"), email="")
    view = invitations.public_view(invite, "http://localhost:8095")
    return jsonify(view)


# ── Fixed clock in the browser: Thursday morning ───────────────────────────
FAKE_NOW = os.environ.get("VIDEO_FAKE_NOW", "2026-11-11T07:42:00+01:00")
CLOCK = ("<script>(function(){var off=new Date('%s').getTime()-Date.now();var D=Date;"
         "function F(){var a=[].slice.call(arguments);if(!(this instanceof F))return new D(D.now()+off).toString();"
         "return a.length?new (Function.prototype.bind.apply(D,[null].concat(a)))():new D(D.now()+off);}"
         "F.prototype=D.prototype;F.now=function(){return D.now()+off};F.parse=D.parse;F.UTC=D.UTC;window.Date=F;})();</script>") % FAKE_NOW

OVERLAY = os.path.join(HERE, "overlay.json")


def _merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _merge(dst[k], v)
        else:
            dst[k] = v


@flask_app.after_request
def _video_tweaks(resp):
    try:
        if resp.mimetype == "text/html":
            resp.direct_passthrough = False
            body = resp.get_data(as_text=True)
            if "<head>" in body:
                resp.set_data(body.replace("<head>", "<head>" + CLOCK, 1))
        elif resp.mimetype == "application/json" and request.path.startswith("/api/v2/dashboard/data") and os.path.exists(OVERLAY):
            data = json.loads(resp.get_data(as_text=True))
            with open(OVERLAY, encoding="utf-8") as fh:
                overlay = json.load(fh)
            target = data.get("data", data) if isinstance(data.get("data"), dict) else data
            _merge(target, overlay)
            resp.set_data(json.dumps(data, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        print("video tweak failed:", exc, file=sys.stderr)
    return resp


flask_app.run(host="127.0.0.1", port=8095, threaded=True, debug=False)
