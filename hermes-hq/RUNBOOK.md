# Hermes HQ — Runbook

One-time setup on the Hostinger KVM-2 (`ssh root@2.24.223.193`), then everything is web-based.

## Architecture

```
                    ┌─────────────────────────── VPS (KVM-2) ───────────────────────────┐
 team browsers ───► │  Caddy (HTTPS) ──► HQ dashboard (FastAPI, this repo)              │
                    │                        │ chat · drafts · contacts · jobs          │
 team SSH ────────► │  Hermes CLI (plastic-labs/hermes-honcho, in tmux)                 │
                    └────────────│──────────────────────│──────────────────────────────┘
                                 ▼                      ▼
                       Anthropic API           Honcho cloud (app.honcho.dev)
                                            ONE shared workspace = shared memory
```

The dashboard and the Hermes CLI point at the **same Honcho workspace**, so what the team does in either place compounds into one memory: who Chad is, how Jim likes tickets written, what shipped on Stryker last week.

## Credentials checklist

| Credential | Where to get it | Used for |
|---|---|---|
| Honcho API key | app.honcho.dev → API KEYS | memory (you have this) |
| Anthropic API key | console.anthropic.com | chat + drafting + job scoring |
| Domain (optional but recommended) | point an A record, e.g. `hq.kevincarpdev.com` → `2.24.223.193` | HTTPS via Caddy |
| GitHub PAT or deploy keys | github.com → settings | phase 2: repo access for the agent |
| Slack bot token | api.slack.com app | phase 2 |
| Google OAuth client (Gmail API) | console.cloud.google.com | phase 2 |
| Asana PAT | app.asana.com → developer console | phase 2 |

> Your Honcho key was pasted in chat — fine for setup, but rotate it at app.honcho.dev once everything runs, and keep it only in `.env` on the VPS (gitignored).

## 1 · Deploy the dashboard (~10 min)

```bash
ssh root@2.24.223.193
git clone <your-repo-url> /opt/hermes-hq && cd /opt/hermes-hq   # or scp the folder up
bash setup-vps.sh        # installs docker, firewall, creates .env, then stops
nano .env                # set ANTHROPIC_API_KEY, HONCHO_API_KEY, optionally DOMAIN
bash setup-vps.sh        # builds, starts, seeds Qolos/Stryker + Fore Genomics
docker compose exec app python -m app.add_user kevin     # repeat per teammate
```

No repo yet? From your Mac: `rsync -av --exclude data --exclude .env hermes-hq/ root@2.24.223.193:/opt/hermes-hq/`

Open `http://2.24.223.193` (or `https://hq.kevincarpdev.com` if DOMAIN set). First visit with an empty user table offers a create-admin form, so `add_user` is optional for the first account.

## 2 · Honcho: clean slate

Honcho memory is scoped by **workspace**, so "clearing" is just starting a fresh workspace — no deletion needed:

1. Keep `HONCHO_WORKSPACE_ID=kc-hq-v1` in `.env` (already the default). Anything your old Hermes instance learned lives in its old workspace and never bleeds in.
2. To truly delete old data: app.honcho.dev → old workspace → delete (or leave it as an archive).
3. Future reset = bump to `kc-hq-v2` in `.env` on both the dashboard and Hermes, restart.

Peer naming convention (already wired into the app — keep Hermes consistent with it):
- `team-kevin`, `team-<name>` — teammates
- `contact-chad-qolos`, `contact-jim-qolos`, `contact-kyle-foregenomics`, `contact-suzanna-foregenomics`
- `assistant` — the agent itself

Sessions: `proj-stryker-bc`, `proj-fg-parent-portal` (work chat) and `comms-<contact-peer>` (logged emails/slack per person).

## 3 · Hermes CLI: fresh install on the VPS

```bash
ssh root@2.24.223.193

# clear any existing hermes state (memory, sessions, skills, config)
mv ~/.hermes ~/.hermes.backup.$(date +%F) 2>/dev/null || true

git clone https://github.com/plastic-labs/hermes-honcho /opt/hermes && cd /opt/hermes
# follow its README install (uv/python 3.11+), then in ~/.hermes/.env set:
#   ANTHROPIC_API_KEY=...            (same key as the dashboard)
#   HONCHO_API_KEY=...               (same key)
#   HONCHO_WORKSPACE_ID=kc-hq-v1     (MUST match the dashboard .env)
```

State lives in `~/.hermes/` (config.yaml, .env, sessions/, state.db, skills) — that `mv` is the "clear memory + skills" step. Local-only state like old skills won't carry over; Honcho-side learning is isolated by workspace as above.

Run it in tmux so sessions survive disconnects:

```bash
tmux new -s hermes
cd /opt/hermes && <its run command>    # per repo README, e.g. `hermes`
# detach: Ctrl+B then D · reattach: tmux attach -t hermes
```

### Team SSH model
Simplest (fine to start): everyone uses `root`, one shared `~/.hermes`, and tells Hermes who they are. Better once it sticks: one Linux user per teammate (`adduser jim`), each with their own `~/.hermes/.env` using the same workspace — then Honcho cleanly learns each person. Use SSH keys, not passwords (`ssh-copy-id`), and consider disabling password login in `/etc/ssh/sshd_config`.

## 4 · Day-to-day flow

1. Log into the dashboard → click the client project (e.g. Stryker BigCommerce).
2. **Workspace** tab: project-scoped AI chat. Every exchange feeds shared memory.
3. **Draft** tab: pick Chad vs Jim, say what the message must do → personalized email/slack draft. Edit inline, copy, send from your real client, then **mark as sent**. Paste replies into **Log inbound** — this is what makes drafts genuinely sound right per person over time.
4. **People** tab: keep style notes current; "What has memory learned?" queries Honcho directly.
5. **Jobs**: paste leads, SCORE against your resume (set it in Settings), PROPOSAL to draft. Statuses: lead → applied → interview → won/lost. No auto-apply by design — Upwork/LinkedIn ban automation; this keeps your accounts safe while killing the writing time.
6. Heavier dev work: SSH in, `tmux attach -t hermes`, work in the repo with Hermes — same memory.

## 5 · Phase 2 wiring order (recommended)

1. **Git** — set `GITHUB_TOKEN`, clone client repos to `/opt/repos/`, let Hermes work there; dashboard "repo" field already names them.
2. **Slack** — bot token; auto-ingest client channels into `comms-*` sessions (replaces manual inbound logging).
3. **Gmail** — same ingestion for email + send drafts directly.
4. **Asana** — task list inside each project workspace.

Stubs + env vars already exist in `app/integrations.py` (marked `WIRE-HERE`); Settings page shows live status per integration.

## Maintenance

```bash
cd /opt/hermes-hq
docker compose logs -f app        # logs
docker compose up -d --build      # deploy after code changes
cp data/hq.db data/hq.db.bak      # backup (db is sqlite, one file)
```
