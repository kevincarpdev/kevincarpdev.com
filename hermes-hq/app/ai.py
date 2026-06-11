"""LLM-powered chat, drafting, and job-fit scoring.

Providers (checked in order):
  1. OpenAI-compatible endpoint (LLM_BASE_URL + LLM_API_KEY) — e.g. Nous Portal
  2. Anthropic (ANTHROPIC_API_KEY)
"""
import json
import logging

from .config import (ANTHROPIC_API_KEY, ANTHROPIC_MODEL, LLM_API_KEY,
                     LLM_BASE_URL, LLM_MODEL)
from . import honcho_client as hc

log = logging.getLogger("hq.ai")

OFFLINE_MSG = ("AI is offline: set LLM_API_KEY (+ LLM_BASE_URL) or "
               "ANTHROPIC_API_KEY in .env, then docker compose up -d.")

CHANNEL_RULES = {
    "email": 'Email: subject line first ("Subject: ..."), brief greeting, '
             "tight paragraphs, simple signoff.",
    "slack": "Slack: short, casual, no greeting/signoff needed.",
    "asana": "Asana task comment: no greeting/signoff, lead with status or "
             "the decision needed, structured and scannable (short bullets "
             "or checklist fine), tag-style references like @Name where natural.",
}

_client = None


def _openai_mode() -> bool:
    return bool(LLM_BASE_URL and LLM_API_KEY)


def enabled() -> bool:
    return _openai_mode() or bool(ANTHROPIC_API_KEY)


def provider_label() -> str:
    if _openai_mode():
        host = LLM_BASE_URL.split("//")[-1].split("/")[0]
        return f"{LLM_MODEL} @ {host.split('.')[0] if 'nousresearch' in host else host}"
    if ANTHROPIC_API_KEY:
        return ANTHROPIC_MODEL
    return "no key"


def client():
    global _client
    if _client is None and ANTHROPIC_API_KEY:
        import anthropic
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _complete_openai(system: str, messages: list, max_tokens: int) -> str:
    import httpx
    r = httpx.post(
        f"{LLM_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {LLM_API_KEY}"},
        json={"model": LLM_MODEL, "max_tokens": max_tokens,
              "messages": [{"role": "system", "content": system}] + messages},
        timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _complete(system: str, messages: list, max_tokens: int = 1500) -> str:
    if not enabled():
        return OFFLINE_MSG
    try:
        if _openai_mode():
            return _complete_openai(system, messages, max_tokens)
        resp = client().messages.create(
            model=ANTHROPIC_MODEL, max_tokens=max_tokens,
            system=system, messages=messages)
        return "".join(b.text for b in resp.content if b.type == "text")
    except Exception as e:
        log.warning("llm call failed: %s", e)
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

Rules: match the recipient — technical depth for engineers, outcomes and timelines for stakeholders. {CHANNEL_RULES.get(channel, CHANNEL_RULES['email'])} Output ONLY the message, no commentary."""
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
