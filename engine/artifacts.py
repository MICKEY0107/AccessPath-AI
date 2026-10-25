"""Local evidence storage adapter used until object storage is introduced."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


@dataclass(frozen=True)
class StoredArtifact:
    kind: str
    relative_path: str
    sha256: str


class LocalArtifactStore:
    def __init__(self, root: Path, run_id: UUID) -> None:
        self._root = root
        self._run_id = run_id

    def screenshot_path(self, step_number: int, moment: str) -> Path:
        path = self._root / "runs" / str(self._run_id) / f"step-{step_number:02d}-{moment}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def describe(self, path: Path, kind: str) -> StoredArtifact:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return StoredArtifact(
            kind=kind,
            relative_path=path.relative_to(self._root).as_posix(),
            sha256=digest,
        )
