"""ApplyApp: daily human-in-the-loop job-application agent.

The queue is a Google Sheet or a local jobs.xlsx. Each pending row is a public
posting URL. The LangGraph pipeline fetches that posting, loads seeds and
Agent Project Docs from Drive or local folders, and writes a truthful resume
and cover letter.
Analyze, resume, cover letter, format, and critique each use the model
configured for that step (Claude, or any OpenAI-compatible API). Finished files
are Google Docs or formatted .docx files for a human to proofread. Nothing is
submitted to an ATS automatically.

This package is meant to run unattended (`python -m applyapp run` or the 7am
LaunchAgent), not from Cursor chat.
"""

__version__ = "0.1.0"
