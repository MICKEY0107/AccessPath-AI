"""Production-only settings for an HTTPS deployment behind a trusted proxy.

This module intentionally fails closed when deployment-critical configuration is
missing. Local development continues to use ``config.settings.local``.
"""

from __future__ import annotations

import os

from .base import *  # noqa: F403


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set in production.")
    return value


DEBUG = False
ALLOWED_HOSTS = [
    host.strip() for host in _required("DJANGO_ALLOWED_HOSTS").split(",") if host.strip()
]
if "*" in ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must name explicit production hosts.")

# The load balancer must remove inbound X-Forwarded-Proto and set it itself.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Production is deliberately strict: only use this profile after every production
# hostname and subdomain is HTTPS-only. A separate staging profile should be used
# while certificates and redirects are being verified.
SECURE_HSTS_SECONDS = int(_required("SECURE_HSTS_SECONDS"))
if SECURE_HSTS_SECONDS < 31_536_000:
    raise RuntimeError("SECURE_HSTS_SECONDS must be at least one year in production.")
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Public-site evaluation must never be allowed to reach private infrastructure.
ALLOW_PRIVATE_NETWORKS = False
if os.environ.get("ALLOW_PRIVATE_NETWORKS", "false").lower() == "true":
    raise RuntimeError("ALLOW_PRIVATE_NETWORKS cannot be enabled in production.")

# Keep long-lived HTTP workers healthy and make database connections recyclable.
DATABASES["default"]["CONN_MAX_AGE"] = int(os.environ.get("DB_CONN_MAX_AGE", "60"))  # noqa: F405
