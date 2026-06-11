"""Thin, fault-tolerant wrapper around the Honcho v3 SDK.

Design:
  - one workspace (HONCHO_WORKSPACE_ID) shared by this dashboard AND the
    Hermes CLI on the VPS, so memory compounds across both surfaces
  - peers:  team-<username>   each teammate
            contact-<slug>    each client contact (Chad, Jim, Kyle, ...)
            assistant         the HQ assistant itself
  - sessions: proj-<slug>     project workspace chat
              comms-<contact> logged inbound/outbound comms per contact

Every call degrades gracefully: if Honcho is unreachable or unconfigured the
dashboard keeps working, just without long-term memory.
"""
import logging

from .config import HONCHO_API_KEY, HONCHO_WORKSPACE_ID

log = logging.getLogger("hq.honcho")
_client = None

ASSISTANT_PEER = "assistant"


def enabled() -> bool:
    return bool(HONCHO_API_KEY)


def client():
    global _client
    if _client is None and enabled():
        try:
            from honcho import Honcho
            _client = Honcho(api_key=HONCHO_API_KEY,
                             workspace_id=HONCHO_WORKSPACE_ID)
        except Exception as e:  # pragma: no cover
            log.warning("honcho init failed: %s", e)
    return _client


def _safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:
        log.warning("honcho call failed: %s", e)
        return None


def log_exchange(project_slug: str, author_peer: str, user_text: str,
                 assistant_text: str):
    """Record a workspace-chat exchange so Honcho learns the project + author."""
    c = client()
    if not c:
        return

    def _do():
        author = c.peer(author_peer)
        assistant = c.peer(ASSISTANT_PEER)
        session = c.session(f"proj-{project_slug}")
        session.add_peers([author, assistant])
        session.add_messages([author.message(user_text),
                              assistant.message(assistant_text)])
    _safe(_do)


def log_inbound(contact_peer: str, project_slug: str, text: str):
    """Record a real message RECEIVED from a client contact.

    This is the highest-signal way to teach Honcho who Chad/Jim/Kyle/Suzanna
    are and how they communicate.
    """
    c = client()
    if not c:
        return

    def _do():
        contact = c.peer(contact_peer)
        session = c.session(f"comms-{contact_peer}")
        session.add_peers([contact])
        session.add_messages([contact.message(f"[{project_slug}] {text}")])
    _safe(_do)


def log_outbound(contact_peer: str, author_peer: str, project_slug: str,
                 text: str):
    """Record a message we actually sent to a contact (marks our voice)."""
    c = client()
    if not c:
        return

    def _do():
        author = c.peer(author_peer)
        contact = c.peer(contact_peer)
        session = c.session(f"comms-{contact_peer}")
        session.add_peers([author, contact])
        session.add_messages([author.message(f"[{project_slug}] {text}")])
    _safe(_do)


def peer_insight(peer_id: str, question: str):
    """Ask Honcho's dialectic layer about a peer (contact or teammate)."""
    c = client()
    if not c:
        return None

    def _do():
        return c.peer(peer_id).chat(question)
    out = _safe(_do)
    return str(out) if out else None


def project_memory(project_slug: str, question: str):
    """Ask what Honcho knows in the context of a project session."""
    c = client()
    if not c:
        return None

    def _do():
        return c.peer(ASSISTANT_PEER).chat(
            f"(regarding session proj-{project_slug}) {question}")
    out = _safe(_do)
    return str(out) if out else None
