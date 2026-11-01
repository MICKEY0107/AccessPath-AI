"""AccessPath AI command line: run keyboard journeys anywhere, including CI.

    python -m accesspath run journeys/clinic-broken.json --repo . --format sarif,markdown

The CLI uses the same engine as the web app (keyboard executor, checks, confirm-before-
blaming probes, rule catalog, code locator) but needs no server or database.
"""

__version__ = "1.0.0"
