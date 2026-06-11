# Hermes HQ

Team dashboard for client work: per-project AI workspace, per-contact message drafting, and a job pipeline — backed by [Honcho](https://honcho.dev) memory shared with a [Hermes](https://github.com/plastic-labs/hermes-honcho) CLI agent on the same VPS.

- **Clients** → org/project cards (Qolos → Stryker BigCommerce, Fore Genomics → Parent Portal)
- **Workspace** → project-scoped chat (Anthropic + Honcho context)
- **Draft** → email/slack drafts personalized per contact (Chad ≠ Jim ≠ Kyle ≠ Suzanna), inbound logging teaches memory
- **Jobs** → lead tracker, AI fit scoring vs your resume, proposal drafting
- **Settings** → resume/profile, team, phase-2 integration status (Slack, Gmail, Asana, Git)

Deploy: see **RUNBOOK.md**. Local dev:

```bash
pip install -r requirements.txt
cp .env.example .env   # fill keys (app runs without them, AI shows offline notice)
python -m app.seed
uvicorn app.main:app --reload
```

Stack: FastAPI · SQLite · Jinja · vanilla JS · Docker Compose · Caddy. Auth: scrypt + signed cookies, individual accounts (`python -m app.add_user <name>`).
