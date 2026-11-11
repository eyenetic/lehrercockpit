"""Test data for the explainer video (no real school, no real people)."""
from datetime import datetime, timezone

NOW = datetime(2026, 11, 11, 6, 42, tzinfo=timezone.utc)


def _org(iso, wd, general="", middle="", upper=""):
    parts = [p for p in (("Allgemein: " + general) if general else "", ("Mittelstufe: " + middle) if middle else "",
                         ("Oberstufe: " + upper) if upper else "") if p]
    return {"dateLabel": f"{iso[8:10]}.{iso[5:7]}.", "isoDate": iso, "weekday": wd, "general": general, "middle": middle,
            "middleNotes": "", "upper": upper, "upperNotes": "", "text": " | ".join(parts),
            "title": general or middle or upper}


ORG = [
    _org("2026-11-11", "Mi", general="Fachkonferenz Mathematik, 15:30 Uhr, R 204"),
    _org("2026-11-13", "Fr", middle="Wandertag Jahrgang 7"),
    _org("2026-11-18", "Mi", general="Gesamtkonferenz, 15:00 Uhr, Aula"),
    _org("2026-11-19", "Do", general="Elternsprechtag, 16–19 Uhr"),
    _org("2026-11-26", "Do", general="Tag der offenen Tür, 10–14 Uhr"),
    _org("2026-12-18", "Fr", general="Weihnachtskonzert, 18 Uhr, Aula"),
]


def orgaplan():
    return {"ok": True, "configured": True, "data": {
        "checkedAt": NOW.isoformat(), "detail": f"{len(ORG)} Einträge in den nächsten sechs Wochen.", "entries": ORG,
        "error": None, "highlights": [], "mode": "auto", "monthLabel": "November", "publishedAt": "2026-10-15T17:16:30",
        "schoolYear": "", "site": "", "sourceName": "Orgaplan-November.pdf", "sourceUrl": "", "stand": "",
        "status": "ok", "title": "Orgaplan", "today_entries": [ORG[0]], "upcoming": ORG, "week_entries": ORG[:2]}}


KA = [("8b", "2026-11-17", "Mathematik"), ("10a", "2026-11-19", "Physik"), ("7c", "2026-11-24", "Mathematik"),
      ("9a", "2026-11-26", "Physik"), ("10a", "2026-12-03", "Mathematik"), ("8b", "2026-12-08", "Physik")]


def klassenarbeitsplan():
    from backend.classwork_sync import plan_view
    entries = [{"classLabel": c, "isoDate": d, "dateLabel": f"{d[8:10]}.{d[5:7]}.", "title": f"KA {s}",
                "summary": f"Klassenarbeit: {s}", "subject": s, "kind": "Klassenarbeit"} for c, d, s in KA]
    cache = {"entries": entries, "sourceName": "Klassenarbeitsplan 2026-27.xlsx", "status": "ok",
             "title": "Klassenarbeitsplan", "detail": f"{len(entries)} Klassenarbeiten", "url": "", "sourceUrl": "",
             "updatedAt": "07:30"}
    return {"ok": True, "configured": True, "data": plan_view(cache, NOW), "sync": {"needs_browser": False, "onedrive": False}}


def _ev(uid, title, start, end=None, all_day=False):
    return {"all_day": all_day, "attachments": [], "description": None, "description_html": None,
            "end": end or start, "location": None, "running": False, "start": start,
            "time_label": None if all_day else f"{start[11:16]}–{(end or start)[11:16]}", "title": title,
            "uid": uid, "url": ""}


SCHOOL = [
    _ev("t1", "Fachkonferenz Mathematik", "2026-11-11T15:30:00+01:00", "2026-11-11T17:00:00+01:00"),
    _ev("t2", "Elternsprechtag", "2026-11-19T16:00:00+01:00", "2026-11-19T19:00:00+01:00"),
    _ev("t3", "Tag der offenen Tür", "2026-11-26T10:00:00+01:00", "2026-11-26T14:00:00+01:00"),
]


def wichtige_termine():
    return {"ok": True, "data": {"mode": "live", "error": None, "today_events": SCHOOL[:1], "upcoming_events": SCHOOL[1:],
                                 "events": SCHOOL, "feed_url": "", "fetched_at": NOW.isoformat()}}


MAILS = [
    ("1", "Schulleitung", "Einladung zur Gesamtkonferenz am 18.11.", "2026-11-11T06:31:00+00:00", True),
    ("2", "Sekretariat", "Raumänderung: Physik 9a heute in Physik 2", "2026-11-11T06:05:00+00:00", True),
    ("3", "Fachbereich Mathematik", "Protokoll der Fachkonferenz", "2026-11-10T15:12:00+00:00", False),
    ("4", "Förderverein", "Weihnachtsbasar – wer hilft mit?", "2026-11-10T11:48:00+00:00", False),
    ("5", "IT-Team", "Neue Beamer in R 112 und R 204", "2026-11-09T13:20:00+00:00", False),
]


def dienstmail():
    msgs = [{"id": i, "from": f, "from_address": "", "subject": s, "date": d, "unread": u} for i, f, s, d, u in MAILS]
    return {"ok": True, "configured": True, "data": {"address": "anna.beispiel@schule.example", "webmail_url": "",
                                                     "messages": msgs, "error": None, "fetched_at": NOW.isoformat()}}


def _task(i, title, start, detail, kind="event", all_day=False):
    return {"id": f"itslearning-cal-{i}", "kind": kind, "title": title, "start": start, "end": start,
            "allDay": all_day, "location": "", "url": "", "detail": detail, "detailHtml": "", "attachments": []}


def itslearning():
    events = [
        _task("a1", "Abgabe: Versuchsprotokoll Pendel (9a Physik)", "2026-11-13T23:59:00+01:00", "Physik 9a"),
        _task("a2", "Abgabe: Übungsblatt Lineare Funktionen (8b)", "2026-11-16T23:59:00+01:00", "Mathematik 8b"),
        _task("a3", "Referate Energie (10a Physik)", "2026-11-18T09:55:00+01:00", "Physik 10a"),
    ]
    return {"ok": True, "configured": True, "data": {
        "source": {"id": "itslearning", "name": "itslearning", "type": "Kalender", "status": "ok", "cadence": "Kalender-Abo",
                   "lastSync": "07:40", "nextStep": "", "detail": "Termine und Abgaben kommen über das Kalender-Abo aus itslearning."},
        "messages": [], "priorities": [], "mode": "calendar", "note": "",
        "calendar": {"ok": True, "events": events, "error": None, "fetched_at": NOW.isoformat()}}}


def install():
    import backend.api.dashboard_routes as dr
    dr._fetch_orgaplan_data = orgaplan
    dr._fetch_klassenarbeitsplan_data = klassenarbeitsplan
    dr._fetch_wichtige_termine_data = lambda user_id, force=False: wichtige_termine()
    dr._fetch_dienstmail_data = lambda user_id, force=False: dienstmail()
    dr._fetch_itslearning_data = lambda user_id, force=False: itslearning()
