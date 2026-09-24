"""Create a local ApplyApp home: example seeds, an empty queue, and a `.env`.

Used by `applyapp init`. Paths point at folders the user owns. Example seeds are
fictional. An existing `.env` is left alone so a working install is not overwritten.
"""

import sys
from pathlib import Path

from applyapp.config import PROJECT_ROOT, write_private_text
from applyapp.queue import _create_workbook

EXAMPLE_SEEDS = Path(__file__).resolve().parent / "examples" / "seeds"


def init_home(home: Path, env_file: Path | None = None) -> list[str]:
    """Create `home` and return the lines a person should read next."""
    home = home.expanduser().resolve()
    seed_dir = home / "seeds"
    output_dir = home / "output"
    jobs_path = home / "jobs.xlsx"
    seed_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    copied = _copy_examples(seed_dir)
    if not jobs_path.exists():
        _create_workbook(jobs_path)

    env_path = env_file if env_file is not None else PROJECT_ROOT / ".env"
    env_note = _write_env(env_path, seed_dir, output_dir, jobs_path)
    return [
        f"Seeds:  {seed_dir} ({copied} example file(s) copied)",
        f"Output: {output_dir}",
        f"Queue:  {jobs_path}",
        env_note,
        "Paste a public job URL in column A of the queue and leave Status blank.",
        "Each row makes several model calls. Check the provider's price before a long run.",
        "Then run: python -m applyapp doctor",
        "Then run: python -m applyapp run --limit 1",
    ]


def _copy_examples(seed_dir: Path) -> int:
    if not EXAMPLE_SEEDS.is_dir():
        raise RuntimeError(f"Example seeds are missing at {EXAMPLE_SEEDS}")
    copied = 0
    for source in sorted(EXAMPLE_SEEDS.iterdir()):
        if not source.is_file() or source.name.startswith("."):
            continue
        target = seed_dir / source.name
        if target.exists():
            continue
        target.write_bytes(source.read_bytes())
        copied += 1
    return copied


def ensure_configured(env_path: Path | None = None, stdin_is_tty: bool | None = None) -> bool:
    """Ask first-run questions when `.env` is missing. Return False if setup cannot continue.

    The 7am launchd job is not a terminal. It must not block on questions, and it
    skips them entirely once `.env` is filled in.
    """
    path = env_path if env_path is not None else PROJECT_ROOT / ".env"
    if not needs_interview(path):
        return True
    interactive = sys.stdin.isatty() if stdin_is_tty is None else stdin_is_tty
    if not interactive:
        print("ApplyApp is not set up. Run `python -m applyapp run` in a terminal and answer the setup questions.")
        return False
    for line in interview(path):
        print(line)
    return not needs_interview(path)


def needs_interview(env_path: Path) -> bool:
    """True when a first run still has to ask where files and models live.

    A filled-in `.env` (this machine's 7am setup, or a completed init) skips the questions.
    """
    if not env_path.exists():
        return True
    values = _parse_env(env_path)
    if not _has_model_key(values):
        return True
    queue = (values.get("JOB_QUEUE") or "google").strip().lower()
    store = (values.get("DOCUMENT_STORE") or "google").strip().lower()
    if queue == "local" and not values.get("LOCAL_JOBS_PATH") and not values.get("LOCAL_SEED_DIR"):
        return True
    if store == "local" and not values.get("LOCAL_SEED_DIR"):
        return True
    if queue == "google" and not values.get("GOOGLE_SHEET_ID"):
        return True
    if store == "google" and not values.get("GOOGLE_SEED_FOLDER_ID"):
        return True
    return False


def interview(env_path: Path, input_func=input, home: Path | None = None) -> list[str]:
    """Ask for folders and models, then write `.env`. Returns the summary lines."""
    home = (home or (Path.home() / "ApplyApp")).expanduser().resolve()
    print("ApplyApp needs a few paths and a model before the first run.")
    print("Press Enter to accept the value in brackets.")
    location = _ask(
        input_func,
        "Keep files on this computer, or use Google Drive? [local/google]: ",
        "local",
    ).lower()
    use_google = location.startswith("g")
    if use_google:
        return _interview_google(env_path, input_func)
    return _interview_local(env_path, input_func, home)


def _interview_local(env_path: Path, input_func, home: Path) -> list[str]:
    seed_dir = Path(_ask(input_func, f"Seed folder [{home / 'seeds'}]: ", str(home / "seeds"))).expanduser()
    output_dir = Path(_ask(input_func, f"Output folder [{home / 'output'}]: ", str(home / "output"))).expanduser()
    jobs_path = Path(_ask(input_func, f"Job spreadsheet [{home / 'jobs.xlsx'}]: ", str(home / "jobs.xlsx"))).expanduser()
    copy_examples = _ask_yes(input_func, "Copy the fictional example seeds into that folder? [Y/n]: ", default=True)
    model, base_url, api_key, critic = _ask_models(input_func)
    seed_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    copied = _copy_examples(seed_dir) if copy_examples else 0
    if not jobs_path.exists():
        _create_workbook(jobs_path)
    _write_env_lines(env_path, _local_env_lines(seed_dir, output_dir, jobs_path, model, base_url, api_key, critic))
    return [
        f"Seeds:  {seed_dir} ({copied} example file(s) copied)",
        f"Output: {output_dir}",
        f"Queue:  {jobs_path}",
        f"Env:    wrote {env_path}",
        "Paste a public job URL in column A and leave Status blank, then run again.",
    ]


def _interview_google(env_path: Path, input_func) -> list[str]:
    sheet = _ask(input_func, "Google Sheet URL or ID: ", "")
    seed = _ask(input_func, "Drive seed folder URL or ID: ", "")
    output = _ask(input_func, "Drive output folder URL or ID: ", "")
    model, base_url, api_key, critic = _ask_models(input_func)
    lines = [
        "# Created by the first-run questions. Documents stay in Google Drive.",
        "JOB_QUEUE=google",
        "DOCUMENT_STORE=google",
        f"GOOGLE_SHEET_ID={sheet}",
        f"GOOGLE_SEED_FOLDER_ID={seed}",
        f"GOOGLE_OUTPUT_FOLDER_ID={output}",
        *_model_env_lines(model, base_url, api_key, critic),
    ]
    _write_env_lines(env_path, lines)
    return [
        f"Env: wrote {env_path}",
        "Add credentials.json, then run: python -m applyapp auth",
    ]


def _ask_models(input_func) -> tuple[str, str, str, str]:
    model = _ask(input_func, "Writing model [claude-sonnet-5]: ", "claude-sonnet-5")
    base_url = ""
    api_key = ""
    if _is_claude(model):
        api_key = _ask(input_func, "Anthropic API key: ", "")
    else:
        base_url = _ask(input_func, "Model base URL [http://localhost:11434/v1]: ", "http://localhost:11434/v1")
        api_key = _ask(input_func, "API key (leave blank for a local model): ", "")
    critic = _ask(input_func, "Critic model (blank = same as writing): ", "")
    return model, base_url, api_key, critic


def _local_env_lines(seed_dir, output_dir, jobs_path, model, base_url, api_key, critic) -> list[str]:
    return [
        "# Created by the first-run questions. Local files, no Google account required.",
        "JOB_QUEUE=local",
        "DOCUMENT_STORE=local",
        f"LOCAL_SEED_DIR={seed_dir}",
        f"LOCAL_OUTPUT_DIR={output_dir}",
        f"LOCAL_JOBS_PATH={jobs_path}",
        *_model_env_lines(model, base_url, api_key, critic),
    ]


def _model_env_lines(model: str, base_url: str, api_key: str, critic: str) -> list[str]:
    lines = ["# Each row makes several model calls. Check the provider's price before a long run."]
    if _is_claude(model):
        lines.extend([f"ANTHROPIC_API_KEY={api_key}", f"ANTHROPIC_MODEL={model}"])
    else:
        lines.extend(
            [
                "LLM_PROVIDER=openai",
                f"LLM_MODEL={model}",
                f"LLM_BASE_URL={base_url}",
                f"LLM_API_KEY={api_key}",
            ]
        )
    if critic.strip():
        lines.extend(
            [
                "CRITIQUE_PROVIDER=openai" if not _is_claude(critic) else "CRITIQUE_PROVIDER=anthropic",
                f"CRITIQUE_MODEL={critic.strip()}",
            ]
        )
        if not _is_claude(critic):
            lines.append(f"CRITIQUE_BASE_URL={base_url or 'http://localhost:11434/v1'}")
    return lines


def _is_claude(model: str) -> bool:
    token = model.strip().lower()
    return token in {"", "claude"} or token.startswith("claude")


def _ask(input_func, prompt: str, default: str) -> str:
    answer = input_func(prompt)
    if answer is None:
        return default
    text = str(answer).strip()
    return text or default


def _ask_yes(input_func, prompt: str, default: bool) -> bool:
    answer = input_func(prompt)
    if answer is None or not str(answer).strip():
        return default
    return str(answer).strip().lower() in {"y", "yes"}


def _parse_env(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _has_model_key(values: dict[str, str]) -> bool:
    if values.get("ANTHROPIC_API_KEY") or values.get("OPENAI_API_KEY") or values.get("LLM_API_KEY"):
        return True
    base = (values.get("LLM_BASE_URL") or values.get("CRITIQUE_BASE_URL") or "").lower()
    return "localhost" in base or "127.0.0.1" in base


def _write_env_lines(env_path: Path, lines: list[str]) -> None:
    write_private_text(env_path, "\n".join(lines) + "\n")


def _write_env(env_path: Path, seed_dir: Path, output_dir: Path, jobs_path: Path) -> str:
    """Write a local-only `.env` when the file is absent."""
    if env_path.exists():
        return f"Env:    left existing file in place ({env_path})"
    write_private_text(
        env_path,
        "\n".join(
            [
                "# Created by `applyapp init`. Local files, no Google account required.",
                "ANTHROPIC_API_KEY=",
                "ANTHROPIC_MODEL=claude-sonnet-5",
                "JOB_QUEUE=local",
                "DOCUMENT_STORE=local",
                f"LOCAL_SEED_DIR={seed_dir}",
                f"LOCAL_OUTPUT_DIR={output_dir}",
                f"LOCAL_JOBS_PATH={jobs_path}",
                "",
                "# Optional: send only the critique step to another model.",
                "# CRITIQUE_PROVIDER=openai",
                "# CRITIQUE_MODEL=llama3.1",
                "# CRITIQUE_BASE_URL=http://localhost:11434/v1",
                "",
            ]
        )
        + "\n",
    )
    return f"Env:    wrote {env_path}. Add an API key before doctor."
