"""Gunicorn configuration for the CAPRI container (see the repo-root Dockerfile).

More than one worker is safe here, unlike APEX: sessions, the CSRF token and
the in-flight SSO flow all live in the signed session cookie, and nothing
per-process decides whether a user is signed in. Every worker must see the same
SECRET_KEY, which they do because it comes from the environment.
"""
bind = "0.0.0.0:8000"
workers = 2
threads = 4
worker_class = "gthread"
timeout = 120              # record PDFs and xlsx exports are built in-request
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"
