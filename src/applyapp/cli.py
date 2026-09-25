"""CLI for the unattended worker: `run`, `auth`, `doctor`.

`run` is what LaunchAgent calls at 7am. It takes a file lock, loads pending
(and stuck `processing`) rows from the Sheet or jobs.xlsx, optionally `--limit`s
them, and invokes the graph per row. Failures write a real exception into the
Error column.

`doctor` is the preflight: per-step models, queue, document store, OAuth when
Google is in use, and whether the 7am LaunchAgent plist exists. A missing
scheduler is a warning, not a hard fail, so first-time setup can still pass.
"""

import argparse
import logging
import sys
from pathlib import Path

from applyapp.config import PROJECT_ROOT, Settings, get_settings
from applyapp.documents import storage_checks, storage_errors
from applyapp.queue import fetch_pending_jobs, needs_google, queue_checks, queue_errors
from applyapp.errors import error_message, redact_secrets
from applyapp.google.auth import credentials, token_health
from applyapp.graph import build_job_graph
from applyapp.llm import STEPS, ModelConfigError, resolve_model
from applyapp.lock import RunLock
from applyapp.nodes import claim_job, mark_error
from applyapp.setup_home import ensure_configured, init_home

logger = logging.getLogger("applyapp")


class _RedactingFormatter(logging.Formatter):
    """Logs can include provider exceptions. Strip keys before they hit daily.log."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_secrets(super().format(record))
LAUNCH_AGENT = Path.home() / "Library/LaunchAgents/com.applyapp.daily.plist"
LOCK_PATH = PROJECT_ROOT / "tmp" / "applyapp.run.lock"


def main(argv: list[str] | None = None) -> int:
    """Entry point for `applyapp` and `python -m applyapp`. Returns a process exit code."""
    parser = argparse.ArgumentParser(prog="applyapp", description="ApplyApp daily application agent")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Process new queue rows (Sheet or local xlsx)")
    run.add_argument(
        "--limit",
        type=int,
        metavar="N",
        default=None,
        help="Process only the first N pending rows (sheet order). Default: all.",
    )
    sub.add_parser("auth", help="Sign in to Google, when the queue or documents use it")
    init = sub.add_parser("init", help="Create a local home with seeds, agent project docs, and an empty queue")
    init.add_argument(
        "--home",
        type=Path,
        default=Path.home() / "ApplyApp",
        help="Folder for seeds, Agent Project Docs, output, and jobs.xlsx. Default: ~/ApplyApp",
    )
    init.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Env file to write when it does not already exist. Default: the project .env",
    )
    sub.add_parser("doctor", help="Check models, queue, document store, and credentials")
    args = parser.parse_args(argv)

    handler = logging.StreamHandler()
    handler.setFormatter(_RedactingFormatter("%(asctime)s %(levelname)s %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    if args.command == "init":
        for line in init_home(args.home, env_file=args.env_file):
            print(line)
        return 0
    if args.command in {"run", "doctor"} and not ensure_configured():
        return 1
    settings = get_settings()

    if args.command == "auth":
        credentials(settings)
        print(f"Google token saved to {settings.google_token_path}")
        return 0
    if args.command == "doctor":
        return _doctor(settings)
    if args.command == "run":
        if args.limit is not None and args.limit < 1:
            parser.error("--limit must be at least 1")
        return _run(settings, limit=args.limit)
    return 1


def _run(settings: Settings, limit: int | None = None) -> int:
    """Acquire the run lock, then process jobs. Exit 0 if another run already holds the lock."""
    missing = _missing_runtime(settings)
    if missing:
        for item in missing:
            logger.error("Missing %s", item)
        return 1

    lock = RunLock(LOCK_PATH)
    if not lock.acquire():
        logger.info("Another ApplyApp run is already in progress.")
        return 0
    try:
        return _run_jobs(settings, limit=limit)
    finally:
        lock.release()


def _run_jobs(settings: Settings, limit: int | None = None) -> int:
    """Claim each job, invoke the graph, mark errors with the exception text."""
    jobs = fetch_pending_jobs(settings)
    if limit is not None:
        jobs = jobs[:limit]
        logger.info("Limiting to %s pending row(s).", limit)
    if not jobs:
        logger.info("No new job rows to process.")
        return 0

    for step, spec in _model_specs(settings):
        logger.info("Model %s: %s", step, spec.label())

    graph = build_job_graph(settings)
    failures = 0
    for job in jobs:
        if job.status == "processing":
            logger.info("Reclaiming stuck row %s", job.sheet_row)
        claimed = claim_job(job, settings)
        logger.info("Processing row %s: %s", claimed.sheet_row, claimed.job_url)
        try:
            graph.invoke({"job": claimed, "revision_count": 0})
            logger.info("Ready for review: row %s", claimed.sheet_row)
        except Exception as exc:
            failures += 1
            message = error_message(exc)
            logger.exception("Failed row %s: %s", claimed.sheet_row, message)
            try:
                mark_error(claimed, settings, message)
            except Exception:
                logger.exception("Could not write Error cell for row %s", claimed.sheet_row)
    return 1 if failures else 0


def _doctor(settings: Settings) -> int:
    """Print ok/missing/warn lines. Exit 1 only when required runtime pieces are absent."""
    checks: list[tuple[str, bool, str]] = [
        *queue_checks(settings),
        *storage_checks(settings),
        (f".env ({PROJECT_ROOT / '.env'})", (PROJECT_ROOT / ".env").exists(), ""),
    ]
    token_code, token_detail = "ok", ""
    if needs_google(settings):
        checks.append(
            (
                f"OAuth client ({settings.google_credentials_path})",
                Path(settings.google_credentials_path).exists(),
                "",
            )
        )
        token_code, token_detail = token_health(settings)
        checks.append(("Google OAuth token", token_code == "ok", token_detail))
    else:
        checks.append(("Google OAuth", True, "not used; queue and documents are local"))
    for step, spec, error in _model_checks(settings):
        if error:
            checks.append((f"model {step}", False, error))
        elif not spec.api_key:
            checks.append((f"model {step}", False, "API key missing"))
        else:
            checks.append((f"model {step}", True, spec.label()))

    ok = True
    for name, passed, detail in checks:
        mark = "ok" if passed else "missing"
        if not passed:
            ok = False
        line = f"{mark:7} {name}"
        if detail:
            line += f" — {detail}"
        print(line)

    if LAUNCH_AGENT.exists():
        print(f"ok      LaunchAgent (7am) — {LAUNCH_AGENT}")
    else:
        print("warn    LaunchAgent (7am) — not installed; run ./scripts/install_scheduler.sh")
        print("hint:    ./scripts/install_scheduler.sh  # 7:00 local time, logs/daily.log")
    if token_code == "refresh_failed":
        print(
            "hint:    publish the OAuth client (or keep Testing and re-auth every 7 days). "
            "Audience → test users must include the Google account you sign in with."
        )
    if Path(settings.google_credentials_path).exists() and token_code == "missing":
        print("hint:    run `python -m applyapp auth` after installing credentials.json")
    return 0 if ok else 1


def _model_checks(settings: Settings):
    """Resolve every step. A config error is reported; an empty key is reported separately."""
    found = []
    for step in STEPS:
        try:
            found.append((step, resolve_model(settings, step), ""))
        except ModelConfigError as exc:
            found.append((step, None, str(exc)))
    return found


def _model_specs(settings: Settings):
    specs = []
    for step, spec, error in _model_checks(settings):
        if error or spec is None:
            raise ModelConfigError(error or f"{step}: model is not configured.")
        if not spec.api_key:
            raise ModelConfigError(f"{step}: API key missing.")
        specs.append((step, spec))
    return specs


def _missing_runtime(settings: Settings) -> list[str]:
    missing = []
    for step, spec, error in _model_checks(settings):
        if error:
            missing.append(error)
        elif spec is None or not spec.api_key:
            missing.append(f"{step} API key")
    missing.extend(queue_errors(settings))
    missing.extend(storage_errors(settings))
    if needs_google(settings) and not Path(settings.google_credentials_path).exists():
        missing.append("credentials.json")
    return missing


if __name__ == "__main__":
    sys.exit(main())
