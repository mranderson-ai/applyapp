"""Exclusive file lock so LaunchAgent and a manual `applyapp run` cannot overlap.

Without this, two processes can claim the same queue row, write duplicate files,
and race Status writes. `fcntl.LOCK_NB` fails immediately instead of waiting —
the second process logs and exits 0 so launchd does not treat it as a crash.
The lock lives under `tmp/` (gitignored). Holding the open fd is what owns the lock;
deleting the file would not release it.
"""

import fcntl
import os
from pathlib import Path


class RunLock:
    """Non-blocking exclusive lock so two `applyapp run` processes cannot overlap."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        """Return True if this process now owns the lock."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return False
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        self._fh = handle
        return True

    def release(self) -> None:
        handle = self._fh
        if handle is None:
            return
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
        self._fh = None

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, *_exc) -> None:
        self.release()
