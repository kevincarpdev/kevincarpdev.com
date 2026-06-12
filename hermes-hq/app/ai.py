"""LLM-powered chat, drafting, and job-fit scoring.

Providers (checked in order):
  1. OpenAI-compatible endpoint (LLM_BASE_URL + LLM_API_KEY) — e.g. Nous Portal
  2. Anthropic (ANTHROPIC_API_KEY)
"""
import json
import logging
import re

from .config import (ANTHROPIC_API_KEY, ANTHROPIC_MODEL, LLM_API_KEY,
                     LLM_BASE_URL, LLM_MODEL)
from . import honcho_client as hc, repo_context

log = logging.getLogger("hq.ai")

OFFLINE_MSG = ("AI is offline: set LLM_API_KEY (+ LLM_BASE_URL) or "
               "ANTHROPIC_API_KEY in .env, then docker compose up -d.")

CHANNEL_RULES = {
    "email": 'Email: subject line first ("Subject: ..."), brief greeting, '
             "tight paragraphs, simple signoff. Plain text only — never "
             "markdown symbols like ** or ##.",
    "slack": "Slack: short, casual, no greeting/signoff needed. Plain text "
             "only — never markdown symbols like ** or ##.",
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
    repo_ctx = repo_context.build_context(project.repo, message)
    if repo_ctx:
        system += "\n\n" + repo_ctx
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


def job_fit(job, resume: str, profile: str, past_work: str = "") -> dict:
    system = """You score freelance/contract job fit. Reply with strict JSON only:
{"score": 0-100, "notes": "3-5 sentences: why it fits or not, red flags, suggested angle"}"""
    user = f"""CANDIDATE PROFILE:
{profile}

PAST WORK:
{past_work[:3500] or 'not provided'}

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


_LINKEDIN_RE = re.compile(r"\S*linkedin\.com\S*", re.I)
_LINKEDIN_WORD_RE = re.compile(r"linkedin", re.I)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")


def scrub_offplatform(text: str) -> str:
    """Hard-remove LinkedIn URLs/mentions, emails, and phone numbers.

    Upwork prohibits off-platform contact info pre-contract. This runs on
    every INPUT and on the generated OUTPUT for upwork jobs — prompt rules
    alone are not a guarantee.
    """
    text = _LINKEDIN_RE.sub("", text)
    text = _EMAIL_RE.sub("", text)
    text = _PHONE_RE.sub("", text)
    # drop any sentence fragment still naming linkedin ("fuller background at .")
    text = "\n".join(l for l in text.splitlines()
                     if not _LINKEDIN_WORD_RE.search(l)) if _LINKEDIN_WORD_RE.search(text) else text
    return re.sub(r"[ \t]{2,}", " ", text)


def job_proposal(job, resume: str, profile: str, portfolio: str = "",
                 past_work: str = "") -> str:
    platform = (job.platform or "other").lower()
    is_upwork = platform == "upwork"
    if is_upwork:
        profile = scrub_offplatform(profile)
        resume = scrub_offplatform(resume)
        portfolio = scrub_offplatform(portfolio)
        past_work = scrub_offplatform(past_work)
        compliance = ("- PLATFORM COMPLIANCE (absolute): NEVER mention LinkedIn in any form, "
                      "and never include email addresses, phone numbers, calendar links, or any "
                      "off-platform contact method - Upwork prohibits these before a contract and "
                      "flags violations. Only URLs that appear in PAST WORK or PORTFOLIO are allowed")
    else:
        # Indeed / builtin / hiring.cafe / direct: applications go through the
        # platform or company ATS — portfolio and LinkedIn links are fine.
        compliance = ("- Portfolio and LinkedIn links are allowed on this platform; still keep "
                      "email/phone out of the letter body (the application form carries them)")
    system = f"""You are an expert proposal and cover-letter writer for {platform} applications, writing for Kevin Carpenter, a Senior Full-Stack Architect with 14 years of enterprise experience.

COVER LETTER RULES
Formatting:
- No emojis, no bullet points, no headers inside the letter
- No AI punctuation: no smart quotes, no em dashes, no double dashes, no curly apostrophes
- Open with "Hello" (add the client's first name if visible in the post)
- Close with "Best regards," then a line break, then "Kevin"
- Stay strictly under 1500 characters including spaces

Tone and voice:
- Confident, specific, and warm - never generic or robotic
- Write as if Kevin personally read this job post and is replying human-to-human
- No filler openers: never "I am excited to apply", "I believe I am a great fit", "I came across your posting", or any variation
- No self-congratulatory language - let results and specifics do the work

Content strategy:
- Lead with immediate, relevant value or a concrete result from past work - not an introduction
- Mirror the exact language and priorities of the job post
- Pull role/project descriptions from Kevin's profile verbatim where relevant - lift directly to establish domain authority fast
- Select the 2-4 MOST RELEVANT entries from the PAST WORK library and cite them directly: name the project, what was built, and the outcome (with real numbers when the entry has them). Clients want proof of having solved their exact problem - describing the work beats linking to it
- ALWAYS include 2 real URLs woven into the letter: the most relevant cited past-work entry's public URL, plus the portfolio site. Attach each URL to a concrete claim ("I was lead architect on X (url)"), never as a bare link dump
- ALWAYS include 1-2 real past-work URLs from PAST WORK or PORTFOLIO (clients want verifiable samples) - choose the most relevant, never more than 2
{compliance}
- Every sentence must earn its place

What converts: the client should feel Kevin has already solved their exact problem. Specificity beats enthusiasm. One sharp insight about their stack, industry, or challenge beats three generic capability claims.

SCREENER QUESTIONS: if a SCREENER QUESTIONS section is provided (or the description contains them), output the letter, then a line with only "---", then each question followed by a short, direct answer grounded in Kevin's real experience. Never fabricate, never include off-platform contact info in answers.

OUTPUT: the cover letter only (plus Q&A if screeners present) - no labels, no commentary."""
    user = f"""PROFILE: {profile}
PORTFOLIO (top links):
{portfolio or 'none provided'}
PAST WORK LIBRARY (pick the most relevant entries for THIS job):
{past_work[:9000] or 'none provided'}
RESUME: {resume[:6000]}
JOB: {job.title} on {job.platform}. Client: {job.client or 'unknown'}. Budget {job.budget or 'unknown'}.
DESCRIPTION: {job.description[:5000]}
SCREENER QUESTIONS (answer after the letter, separated by ---):
{(getattr(job, 'screener', '') or 'none')[:3000]}"""
    out = _complete(system, [{"role": "user", "content": user}], max_tokens=1400)
    if is_upwork and not out.startswith("AI error") and out != OFFLINE_MSG:
        out = scrub_offplatform(out)
    return out
