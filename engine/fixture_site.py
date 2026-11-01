"""The bundled fixture site: a fallback server and a copy for the demo repository.

Fixture journeys point at ``FIXTURE_ALLOWED_ORIGINS`` (``http://127.0.0.1:8001`` by
default), normally the Compose ``fixture`` service. Inside a container, or when that
service is not running, nothing answers there. ``serve_if_missing`` then serves the
project's own ``fixtures/clinic`` folder on that loopback address for the length of
one run, so fixture journeys and the demo work with or without the extra service.
Only that folder is ever served, only on a loopback address, and only when the port
is free.
"""

from __future__ import annotations

import functools
import shutil
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

LOOPBACK_HOSTS = {"127.0.0.1", "localhost"}


class _FixtureHandler(SimpleHTTPRequestHandler):
    """Static files only: no directory listings and no hidden files."""

    def list_directory(self, path):  # noqa: ANN001
        self.send_error(404)
        return None

    def send_head(self):  # noqa: ANN201
        path = unquote(self.path.split("?", 1)[0].split("#", 1)[0])
        if any(part.startswith(".") for part in path.replace("\\", "/").split("/") if part):
            self.send_error(404)
            return None
        target = Path(self.translate_path(self.path)).resolve()
        root = Path(self.directory).resolve()
        if target != root and root not in target.parents:
            self.send_error(404)
            return None
        return super().send_head()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


def _host_port(origin: str) -> tuple[str, int] | None:
    parsed = urlparse(origin)
    if parsed.scheme != "http" or (parsed.hostname or "") not in LOOPBACK_HOSTS:
        return None
    return ("127.0.0.1", parsed.port or 80)


def is_reachable(origin: str, timeout: float = 0.5) -> bool:
    """Whether something accepts connections at ``origin`` (any http or https host)."""
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    target = (parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    if parsed.hostname in LOOPBACK_HOSTS:
        target = ("127.0.0.1", target[1])
    try:
        with socket.create_connection(target, timeout=timeout):
            return True
    except OSError:
        return False


_SERVERS: dict[tuple[str, int], list] = {}  # target -> [server, thread, users]
_LOCK = threading.Lock()


@contextmanager
def serve_if_missing(origin: str, root: Path) -> Iterator[bool]:
    """Serve ``root`` at ``origin`` while the block runs, if nothing answers there.

    Yields True when this process is serving the site, False when something else
    already answers or the origin is not a loopback http address. Overlapping runs
    in one process share one server, which stops when the last of them finishes.
    """
    target = _host_port(origin)
    if target is None or not root.is_dir():
        yield False
        return
    with _LOCK:
        entry = _SERVERS.get(target)
        if entry is not None:
            entry[2] += 1
        elif is_reachable(origin):
            entry = None
        else:
            handler = functools.partial(_FixtureHandler, directory=str(root))
            try:
                server = ThreadingHTTPServer(target, handler)
            except OSError:
                server = None
            if server is not None:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                entry = _SERVERS[target] = [server, thread, 1]
    if entry is None:
        yield False
        return
    try:
        yield True
    finally:
        with _LOCK:
            entry[2] -= 1
            if entry[2] == 0:
                _SERVERS.pop(target, None)
                entry[0].shutdown()
                entry[0].server_close()
                entry[1].join(timeout=2)


def copy_bundled_site(base_dir: Path, destination: Path) -> tuple[int, int]:
    """Copy ``fixtures/clinic`` into ``destination`` as a demo repository snapshot."""
    source = base_dir / "fixtures" / "clinic"
    if destination.exists():
        shutil.rmtree(destination)
    target = destination / "fixtures" / "clinic"
    shutil.copytree(
        source, target, symlinks=False, ignore=shutil.ignore_patterns(".*", "__pycache__")
    )
    files = [path for path in destination.rglob("*") if path.is_file()]
    return len(files), sum(path.stat().st_size for path in files)


@contextmanager
def serve_directory(root: Path) -> Iterator[str]:
    """Serve a local static site (read-only, no hidden files) on a free loopback port.

    Used by the CLI for journeys on a site folder in a repository, so CI can evaluate a
    static build without deploying it. Yields the origin, e.g. ``http://127.0.0.1:53817``.
    """
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"site folder not found: {root}")
    handler = functools.partial(_FixtureHandler, directory=str(root))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
