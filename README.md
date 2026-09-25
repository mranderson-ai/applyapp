# ApplyApp

Daily human-in-the-loop agent that turns job posting links into ATS-aware resumes and cover letters.

A human adds public job URLs to a queue (a Google Sheet, or a local Excel file). At 7:00am, or on demand with `python -m applyapp run`, ApplyApp processes **new and stuck rows**: fetch the posting, compare it to your seeds and Agent Project Docs, write a truthful resume and cover letter, run a critic pass, and save the files for you to proofread and submit. Each model step can use Claude or any OpenAI-compatible API. Finished files are Google Docs, or formatted Word documents in a local folder.

V1 does not auto-submit applications and does not have a web UI.

## How the pieces connect

```
Job queue (Sheet or jobs.xlsx)
        │
        ▼
  ingest pending rows
        │
        ├─► fetch posting text
        ├─► load seeds and Agent Project Docs (Drive or local folders)
        ▼
     analyze          ┐
     resume           │ each step: its own model
     cover letter     │ (Claude or OpenAI-compatible)
     critique ↺ revise┘
        ▼
     format (ApplyApp Document Design)
        ▼
  Google Docs  or  formatted .docx + QA notes
        ▼
  queue status → ready_for_review
```

| Piece | Role |
| --- | --- |
| Job queue | You add links; ApplyApp writes status. Google Sheet, or a local `.xlsx`. |
| Seed documents | Writing samples and prior resumes. The applicant's own material. |
| Agent Project Docs | Optimization paper, document design, and Job Roles. Not seeds. |
| LangGraph | Fixed pipeline, not a free-form chat agent. |
| Models | Analyze, resume, cover letter, format, and critique. Each step can use Claude or an OpenAI-compatible API. |
| Output folder | HITL proofread + submit. Google Docs, or formatted Word files in a local folder. |
| launchd | 7:00am local time on this Mac. |

## Queue columns

The Google Sheet and `jobs.xlsx` use the same headers. Row 1 is created if the file is empty. A local workbook also freezes that header and gives Status a dropdown.

| Job Postings | Company | Role | Posting Text | Organization | Level | Resume | Cover Letter | Status | Error | Output | Processed |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

You only have to fill Job Postings with a URL when the page can be read. Company and Role are optional in that case; ApplyApp fills them from the posting when it can. When the page is JavaScript-only, paste the full description into Posting Text and fill Company and Role yourself. Company is the employer. Role is the official title, copied exactly. Those two cells are what the resume and cover letter use for that row. Status blank, `pending`, or `processing` (a crashed run) means “process this.” After a run: `ready_for_review` or `error` with the real exception in the Error column. Resume and Cover Letter receive the file links. Set a row back to `pending` to retry.

## Seeds and Agent Project Docs

Seeds are the applicant's own material. In an agent, that is the personal context the model must not invent past: how you write, and resumes you have already used. The optimization paper, the document design spec, and Job Roles are not seeds. They are the agent's project docs: how to write, how to format, and the role-by-role facts.

| Seed (`LOCAL_SEED_DIR`, or the Drive seed folder) | How the agent uses it |
| --- | --- |
| `Human Writings` | Voice and tone for cover letters (emails, outreach, letters). Not a fact source. |
| Other resumes (PDF, Word, Google Docs) | Starting points only. Produce a stronger, posting-specific version, do not clone them. |

| Agent Project Docs | How the agent uses it |
| --- | --- |
| `Job Roles` | Canonical career facts. A spreadsheet tab, or a markdown section, is one role. A file in a folder named Job Roles counts, as does a file whose name contains `accomplishment`. |
| `Resume & Cover Letter Optimization Paper` | Craft rules for ATS-friendly resumes and cover letters. Follow this; it is not a biography. Shipped in full with the app. |
| `ApplyApp Document Design` | Visual system for the resume and cover letter. Applied in a format step before the file is written. Shipped in full with the app. |

The unoptimized accomplishments spreadsheet is ignored when the OPTIMIZED file is present. Google Docs, Word, Excel, Markdown, and PDFs are loaded. If the Agent Project Docs folder is missing, a run still uses the optimization paper and design spec shipped with the app. It does not invent Job Roles.

## Where a newcomer should start

Google is optional. A local folder, a local spreadsheet, and one model key are enough.

1. Install this project (`pip install -e ".[dev]"` from a checkout).
2. Run `python -m applyapp run`. The first time, it asks where seeds live, where Agent Project Docs live, where finished files go, where the job spreadsheet is, and which model should write and critique. Press Enter to take the suggested local folders and Claude. `python -m applyapp init` writes those same defaults without asking. An existing `.env` is left alone, including a scheduled 7am run.
3. Replace the fictional sample with your own files. Human Writings and prior resumes go in the seed folder. Keep `human writings` in that filename. Other PDF and Word files in the seed folder are treated as prior resumes. Job Roles go in `Agent Project Docs/Job Roles`. Leave `Resume & Cover Letter Optimization Paper` and `ApplyApp Document Design` in Agent Project Docs. Those two are the app's craft and visual specs, not a sample career. If you edit them, keep `optimization paper` and `document design` in the filenames.
4. Put your model key in `.env`. See Models below. A run makes several calls per job, so check the provider's price first.
5. Paste one public job URL into column A of `jobs.xlsx` and leave Status blank.
6. Run `python -m applyapp doctor`, then `python -m applyapp run --limit 1`.
7. Proofread the Word files in `~/ApplyApp/output` before you submit anything.

The sample resume, Job Roles, and Human Writings are a fictional person, Alex Rivera. They are not a real career. The optimization paper and the document design spec ship with the app in full, and a run still uses those packaged copies when Agent Project Docs does not already contain them. `applyapp init` does not copy anyone's private documents into the repo.

Google Drive and a Google Sheet still work. Set `JOB_QUEUE=google` and `DOCUMENT_STORE=google`, add `credentials.json`, and run `python -m applyapp auth`. The 7:00am Mac schedule is optional.

## Setup

Needs Python 3.11+ and [Apple Command Line Tools](https://developer.apple.com/download/more/) (`xcode-select --install`). If `python3` still asks you to agree to a license, run `sudo xcodebuild -license` in Terminal.

```bash
cd ~/Projects/applyapp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

### Google

1. Create a Google Cloud project.
2. Enable **Google Sheets API**, **Google Drive API**, and **Google Docs API**.
3. Configure an OAuth consent screen (your own Google account as a test user).
4. Create an OAuth client of type **Desktop app**, download JSON, save it as `credentials.json` in this folder.
5. Create a Sheet for the job queue and Drive folders for seeds, Agent Project Docs, and output, unless those are local. Paste their URLs or IDs into `.env`. Leave the Agent Project Docs folder blank to use the papers shipped with the app.
6. Put writing samples and prior resumes in the seed folder. Put Job Roles, the optimization paper, and the design spec in Agent Project Docs.
7. On the OAuth **Audience** screen, add your Google account as a test user. For unattended 7am runs, publish the app (or accept re-auth every 7 days while it stays in Testing).

```bash
python -m applyapp auth      # opens a browser once
python -m applyapp doctor
python -m applyapp run       # processes new queue rows
```

### 7:00am schedule

```bash
chmod +x scripts/install_scheduler.sh
./scripts/install_scheduler.sh
```

That installs a macOS LaunchAgent. Logs go to `logs/daily.log`. Cloud Scheduler can wait until this is running reliably on the Mac.

## Document location

`DOCUMENT_STORE=google` reads the Drive seed folder and the Agent Project Docs folder, and writes Google Docs. `DOCUMENT_STORE=local` reads `LOCAL_SEED_DIR` and `LOCAL_AGENT_DOCS_DIR`, and writes formatted `.docx` files into `LOCAL_OUTPUT_DIR` (Calibri, navy, 0.75 in margins, the same block styles as the Docs). File names and folder layout still decide each file's role.

`JOB_QUEUE=google` is the Sheet. `JOB_QUEUE=local` is an Excel workbook (`LOCAL_JOBS_PATH`, default `jobs.xlsx`) with the same columns: Job Postings, Company, Role, Posting Text, Organization, Level, Resume, Cover Letter, Status, Error, Output, Processed. The header row is frozen and Status is a dropdown. Put a URL in Job Postings and leave Status blank. When a page cannot be read, paste the description into Posting Text and fill Company and Role. `jobs.xlsx` stays out of git. Google sign-in is skipped only when both the queue and the document store are local.

## Models

Each LLM step has its own model. Leave the step unset and it uses `LLM_*`, then the Anthropic defaults, so an existing `.env` with only `ANTHROPIC_API_KEY` keeps running Claude everywhere.

| Step | Env prefix | Role |
| --- | --- | --- |
| `analyze` | `ANALYZE_` | Posting vs Job Roles, writings, and prior resumes |
| `resume` | `RESUME_` | Resume draft |
| `cover` | `COVER_` | Cover letter draft |
| `format` | `FORMAT_` | Block schema for the Docs and Word renderer. Keep this on a model that supports structured output. |
| `critique` | `CRITIQUE_` | Grammar, accuracy, relevance, and tone |

`LLM_PROVIDER` is `anthropic` or `openai`. `openai` means any OpenAI-compatible chat API. Set `LLM_BASE_URL` for OpenRouter, Groq, Ollama, or vLLM. Official OpenAI and Anthropic leave the URL blank.

A model value may include a provider prefix: `CRITIQUE_MODEL=openai:llama3.1`.

Claude writes, a local model critiques:

```bash
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-5
CRITIQUE_PROVIDER=openai
CRITIQUE_MODEL=llama3.1
CRITIQUE_BASE_URL=http://localhost:11434/v1
```

A localhost URL does not need a real key. `applyapp doctor` prints the resolved provider and model for every step, and never prints the key. The model must support structured JSON output.

## Secrets and safety

`.env`, `credentials.json`, and `token.json` stay out of git. `applyapp init` and `applyapp auth` write `.env` and `token.json` so only your user can read them. The Google token can read and change Drive files that account can open, because seed, Agent Project Docs, and output folders are chosen by URL. Do not share that file.

Job links must be public `http` or `https` pages. Links to this machine, private networks, or cloud metadata addresses are refused, including after a redirect. Text from a posting is treated as data for the model, not as instructions.

## Commands

| Command | What it does |
| --- | --- |
| `python -m applyapp init` | Create `~/ApplyApp` with example seeds, Agent Project Docs, an empty queue, and a local `.env` |
| `python -m applyapp run` | Process new and stuck (`processing`) queue rows |
| `python -m applyapp run --limit 3` | Same, but only the first 3 pending rows |
| `python -m applyapp auth` | Google sign-in, when the queue or documents use Google |
| `python -m applyapp doctor` | Check models, queue, document store, OAuth, LaunchAgent |
| `pytest` | Polish, queue ingest, local files, model routing, and the run lock (`pip install -e ".[dev]"`) |

## V1 out of scope

- HTML UI (later phase)
- Submitting the application for you
- Playwright for JavaScript-only ATS pages. Those rows land in `error`. Paste the description into Posting Text, fill Company and Role, and run the row again.
- Cloud Scheduler / GCP hosting
