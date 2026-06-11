"""Phase-2 integration layer (stubs).

Each integration declares the env vars it needs; the Settings page shows
status. Wiring points are marked WIRE-HERE so they're easy to find later.
"""
import os

REGISTRY = [
    {"key": "slack", "name": "Slack", "env": ["SLACK_BOT_TOKEN"],
     "purpose": "Send drafted messages to client channels; ingest threads into Honcho."},
    {"key": "gmail", "name": "Gmail", "env": ["GMAIL_CREDENTIALS_JSON"],
     "purpose": "Send drafted emails; ingest client email into per-contact memory."},
    {"key": "asana", "name": "Asana", "env": ["ASANA_PAT"],
     "purpose": "Show project tasks in the workspace; create tasks from chat."},
    {"key": "git", "name": "Git / GitHub", "env": ["GITHUB_TOKEN"],
     "purpose": "Let the workspace agent read the project repo and open PRs."},
]


def statuses():
    out = []
    for item in REGISTRY:
        configured = all(os.getenv(k) for k in item["env"])
        out.append({**item, "configured": configured})
    return out


# WIRE-HERE: def send_slack(channel, text): ...
# WIRE-HERE: def send_gmail(to, subject, body): ...
# WIRE-HERE: def asana_tasks(project_gid): ...
# WIRE-HERE: def repo_clone_or_pull(repo): ...   (then hand path to the agent)
