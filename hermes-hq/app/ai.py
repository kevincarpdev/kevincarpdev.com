"""Anthropic-powered chat, drafting, and job-fit scoring."""
import json
import logging

from .config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL
from . import honcho_client as hc

log = logging.getLogger("hq.ai")

OFFLINE_MSG = ("AI is offline: set ANTHROPIC_API_KEY in .env and restart "
               "(docker compose up -d).")

_client = None


def enabled() -> bool:
    return bool(ANTHROPIC_API_KEY)


def client():
    global _client
    if _client is None and enabled():
        import anthropic
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _complete(system: str, messages: list, max_tokens: int = 1500) -> str:
    if not enabled():
        return OFFLINE_MSG
    try:
        resp = client().messages.create(
            model=ANTHROPIC_MODEL, max_tokens=max_tokens,
            system=system, messages=messages)
        return "".join(b.text for b in resp.content if b.type == "text")
    except Exception as e:
        log.warning("anthropic call failed: %s", e)
        return f"AI error: {e}"


def _project_system(project, org, contacts, extra_memory=None) -> str:
    contact_lines = "\n".join(
        f"- {c.name} ({c.role or 'role unknown'}). Style: {c.style_notes or 'not recorded yet'}"
        for c in contacts)
    mem = f"\n\nLong-term memory (Honcho):\n{extra_memory}" if extra_memory else ""
    return f"""You are HQ, the working assistant for Kevin's dev team. You are currently scoped to ONE client project — stay in that context.

Organization: {org.name}
Project: {project.name} (status: {project.status})
Repo: {project.repo or 'n/a'}
Standing notes: {project.notes or 'none'}
Key people:
{contact_lines or '- none recorded'}

Ground rules: be concrete and concise; when discussing code changes reference the repo by name; when discussing communication, respect each person's documented style. Never invent facts about the client.{mem}"""


def project_chat(project, org, contacts, history, user_display: str,
                 user_peer: str, message: str) -> str:
    memory = None
    if hc.enabled():
        memory = hc.project_memory(
            project.slug,
            f"Summarize the most relevant context for this new request from {user_display}: {message[:400]}")
    system = _project_system(project, org, contacts, memory)
    msgs = [{"role": m.role, "content": m.content} for m in history[-20:]]
    msgs.append({"role": "user", "content": f"[{user_display}] {message}"})
    reply = _complete(system, msgs)
    if reply != OFFLINE_MSG and not reply.startswith("AI error"):
        hc.log_exchange(project.slug, user_peer, message, reply)
    return reply


def draft_message(project, org, contact, channel: str, intent: str,
                  user_display: str) -> dict:
    insight = None
    if hc.enabled() and contact.peer_id:
        insight = hc.peer_insight(
            contact.peer_id,
            f"How does {contact.name} communicate and what do they care about? "
            f"How should we write to them? Be specific and brief.")
    system = f"""You draft outbound {channel} messages for Kevin's dev team, written in {user_display}'s voice — plain, professional, no fluff, no corporate filler.

Recipient: {contact.name}, {contact.role or 'role unknown'} at {org.name}.
Project context: {project.name}. Notes: {project.notes or 'none'}
Documented style for this person: {contact.style_notes or 'none recorded'}
{f'What memory says about them: {insight}' if insight else ''}

Rules: match the recipient — technical depth for engineers, outcomes and timelines for stakeholders. {('Slack: short, casual, no greeting/signoff needed.' if channel == 'slack' else 'Email: subject line first ("Subject: ..."), brief greeting, tight paragraphs, simple signoff.')} Output ONLY the message, no commentary."""
    content = _complete(system, [{"role": "user", "content": f"Draft this: {intent}"}])
    return {"draft": content, "insight": insight}


def job_fit(job, resume: str, profile: str) -> dict:
    system = """You score freelance/contract job fit. Reply with strict JSON only:
{"score": 0-100, "notes": "3-5 sentences: why it fits or not, red flags, suggested angle"}"""
    user = f"""CANDIDATE PROFILE:
{profile}

RESUME:
{resume[:6000] or 'not provided'}

JOB:
Title: {job.title}
Platform: {job.platform} | Client: {job.client or 'unknown'} | Budget: {job.budget or 'unknown'}
Description: {job.description[:4000] or 'not provided'}"""
    raw = _complete(system, [{"role": "user", "content": user}], max_tokens=600)
    try:
        start, end = raw.find("{"), raw.rfind("}") + 1
        data = json.loads(raw[start:end])
        return {"score": float(data.get("score", 0)), "notes": str(data.get("notes", ""))}
    except Exception:
        return {"score": None, "notes": raw}


def job_proposal(job, resume: str, profile: str) -> str:
    system = """You write winning, human-sounding freelance proposals/cover letters. Short (150-250 words), specific to the job, leads with the client's problem, shows directly relevant experience, ends with a concrete next step. No "I am writing to express my interest" boilerplate. Output only the proposal."""
    user = f"""PROFILE: {profile}
RESUME: {resume[:6000]}
JOB: {job.title} on {job.platform}. Budget {job.budget or 'unknown'}.
DESCRIPTION: {job.description[:4000]}"""
    return _complete(system, [{"role": "user", "content": user}], max_tokens=800)
