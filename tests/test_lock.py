from pathlib import Path

from applyapp.lock import RunLock


def test_second_acquire_fails_until_release(tmp_path: Path):
    path = tmp_path / "applyapp.run.lock"
    first = RunLock(path)
    second = RunLock(path)
    assert first.acquire() is True
    assert second.acquire() is False
    first.release()
    assert second.acquire() is True
    second.release()
