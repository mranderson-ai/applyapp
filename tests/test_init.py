from applyapp.seeds import classify
from applyapp.setup_home import EXAMPLE_SEEDS, ensure_configured, init_home, interview, needs_interview


def test_init_creates_a_local_home_without_touching_an_existing_env(tmp_path):
    existing = tmp_path / "project.env"
    existing.write_text("ANTHROPIC_API_KEY=keep-me\n", encoding="utf-8")
    notes = init_home(tmp_path / "home", env_file=existing)
    assert (tmp_path / "home" / "jobs.xlsx").is_file()
    assert (tmp_path / "home" / "output").is_dir()
    assert (tmp_path / "home" / "seeds" / "Career_Accomplishments_OPTIMIZED.md").is_file()
    assert "keep-me" in existing.read_text(encoding="utf-8")
    assert any("left existing file" in line for line in notes)


def test_init_writes_env_when_missing_and_example_names_classify(tmp_path):
    env_file = tmp_path / ".env"
    init_home(tmp_path / "home", env_file=env_file)
    text = env_file.read_text(encoding="utf-8")
    assert "JOB_QUEUE=local" in text
    assert "DOCUMENT_STORE=local" in text
    assert "ANTHROPIC_API_KEY=" in text
    assert (env_file.stat().st_mode & 0o777) == 0o600
    names = [path.name for path in EXAMPLE_SEEDS.iterdir() if path.is_file()]
    roles = {classify(name, []) for name in names}
    assert {"accomplishments", "human_writings", "ats_guidance", "document_design", "prior_resume"} <= roles


def test_first_run_asks_for_folders_and_models(tmp_path):
    env_file = tmp_path / ".env"
    answers = iter(
        [
            "",
            "",
            "",
            "",
            "y",
            "claude-sonnet-5",
            "sk-ant-example",
            "llama3.1",
        ]
    )
    notes = interview(env_file, input_func=lambda _prompt: next(answers), home=tmp_path / "home")
    text = env_file.read_text(encoding="utf-8")
    assert "JOB_QUEUE=local" in text
    assert "LOCAL_SEED_DIR=" in text
    assert "ANTHROPIC_API_KEY=sk-ant-example" in text
    assert "CRITIQUE_MODEL=llama3.1" in text
    assert (tmp_path / "home" / "seeds" / "Human Writings.md").is_file()
    assert any("Queue:" in line for line in notes)
    assert needs_interview(env_file) is False


def test_a_filled_in_env_skips_the_questions(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=sk-ant-example\nGOOGLE_SHEET_ID=sheet\nGOOGLE_SEED_FOLDER_ID=folder\n",
        encoding="utf-8",
    )
    assert needs_interview(env_file) is False
    assert ensure_configured(env_file, stdin_is_tty=False) is True


def test_unattended_run_does_not_prompt_when_unset(tmp_path):
    missing = tmp_path / ".env"
    assert needs_interview(missing) is True
    assert ensure_configured(missing, stdin_is_tty=False) is False
