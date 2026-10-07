# Read automatically by gunicorn (Render/Railway start "gunicorn app:app ...").
#
# One worker keeps the in-process caches (feeds, sessions, recent modules) in one
# place; threads let the browser's parallel requests at startup (dashboard data,
# layout, links, feedback, vault …) run side by side instead of queueing behind
# the slowest one.
worker_class = "gthread"
threads = 8
