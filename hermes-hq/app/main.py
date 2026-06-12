import os

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import ai, honcho_client as hc, integrations
from .auth import current_user, hash_password, make_session_cookie, verify_password
from .config import HONCHO_WORKSPACE_ID
from .db import (ChatMessage, Contact, Draft, Job, Org, Project, SessionLocal,
                 User, get_setting, init_db, set_setting)

app = FastAPI(title="Hermes HQ")
BASE = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
init_db()


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_user(request: Request):
    user = current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="login required")
    return user


def page_ctx(request, user, db, **extra):
    return {"request": request, "user": user,
            "honcho_on": hc.enabled(), "ai_on": ai.enabled(),
            "ai_label": ai.provider_label(),
            "workspace_id": HONCHO_WORKSPACE_ID, **extra}


# ---------- auth ----------

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    db = SessionLocal()
    bootstrap = db.query(User).count() == 0
    db.close()
    return templates.TemplateResponse(request, "login.html", {
        "bootstrap": bootstrap, "error": None})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter_by(username=username.strip().lower()).first()
    ok = user and verify_password(password, user.pw_hash)
    db.close()
    if not ok:
        return templates.TemplateResponse(request, "login.html", {
            "bootstrap": False,
            "error": "Wrong username or password."}, status_code=401)
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie("hq_session", make_session_cookie(user.id),
                    httponly=True, samesite="lax", max_age=60 * 60 * 24 * 14)
    return resp


@app.post("/bootstrap")
def bootstrap(request: Request, username: str = Form(...),
              display_name: str = Form(""), password: str = Form(...)):
    db = SessionLocal()
    if db.query(User).count() > 0:
        db.close()
        raise HTTPException(403, "already initialized")
    username = username.strip().lower()
    user = User(username=username, display_name=display_name or username.title(),
                pw_hash=hash_password(password), peer_id=f"team-{username}")
    db.add(user)
    db.commit()
    uid = user.id
    db.close()
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie("hq_session", make_session_cookie(uid),
                    httponly=True, samesite="lax", max_age=60 * 60 * 24 * 14)
    return resp


@app.post("/logout")
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("hq_session")
    return resp


# ---------- pages ----------

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db=Depends(db_session)):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    orgs = db.query(Org).all()
    job_counts = {}
    for j in db.query(Job).all():
        job_counts[j.status] = job_counts.get(j.status, 0) + 1
    return templates.TemplateResponse(request, "home.html", page_ctx(
        request, user, db, orgs=orgs, job_counts=job_counts))


@app.get("/project/{slug}", response_class=HTMLResponse)
def project_page(slug: str, request: Request, db=Depends(db_session)):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    project = db.query(Project).filter_by(slug=slug).first()
    if not project:
        raise HTTPException(404)
    org = project.org
    contacts = org.contacts
    history = (db.query(ChatMessage).filter_by(project_id=project.id)
               .order_by(ChatMessage.created).all())
    drafts = (db.query(Draft).filter_by(project_id=project.id)
              .order_by(Draft.created.desc()).limit(10).all())
    links = []
    for line in (project.links or "").splitlines():
        if "|" in line:
            label, url = line.split("|", 1)
            links.append({"label": label.strip(), "url": url.strip()})
    return templates.TemplateResponse(request, "project.html", page_ctx(
        request, user, db, project=project, org=org, contacts=contacts,
        history=history, drafts=drafts, links=links,
        contact_by_id={c.id: c for c in contacts}))


@app.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request, db=Depends(db_session)):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    jobs = db.query(Job).order_by(Job.created.desc()).all()
    return templates.TemplateResponse(request, "jobs.html", page_ctx(
        request, user, db,
        freelance_jobs=[j for j in jobs if (j.kind or "freelance") != "job"],
        app_jobs=[j for j in jobs if (j.kind or "") == "job"],
        resume_set=bool(get_setting(db, "resume_text"))))


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db=Depends(db_session)):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "settings.html", page_ctx(
        request, user, db,
        profile=get_setting(db, "profile"),
        portfolio_links=get_setting(db, "portfolio_links"),
        past_work=get_setting(db, "past_work"),
        resume_text=get_setting(db, "resume_text"),
        integrations=integrations.statuses(),
        team=db.query(User).all()))


@app.get("/healthz")
def healthz():
    return {"ok": True, "honcho": hc.enabled(), "ai": ai.enabled(),
            "provider": ai.provider_label()}


# ---------- project APIs ----------

@app.post("/api/project/{slug}/chat")
def api_chat(slug: str, payload: dict, user=Depends(require_user),
             db=Depends(db_session)):
    project = db.query(Project).filter_by(slug=slug).first()
    if not project:
        raise HTTPException(404)
    message = (payload.get("message") or "").strip()
    if not message:
        raise HTTPException(400, "empty message")
    history = (db.query(ChatMessage).filter_by(project_id=project.id)
               .order_by(ChatMessage.created).all())
    reply = ai.project_chat(project, project.org, project.org.contacts,
                            history, user.display_name or user.username,
                            user.peer_id, message)
    db.add(ChatMessage(project_id=project.id, user_id=user.id, role="user",
                       content=message))
    db.add(ChatMessage(project_id=project.id, role="assistant", content=reply))
    db.commit()
    return {"reply": reply}


@app.post("/api/project/{slug}/draft")
def api_draft(slug: str, payload: dict, user=Depends(require_user),
              db=Depends(db_session)):
    project = db.query(Project).filter_by(slug=slug).first()
    contact = db.get(Contact, int(payload.get("contact_id", 0)))
    if not project or not contact:
        raise HTTPException(404)
    channel = payload.get("channel", "email")
    intent = (payload.get("intent") or "").strip()
    if not intent:
        raise HTTPException(400, "describe what the message should say")
    out = ai.draft_message(project, project.org, contact, channel, intent,
                           user.display_name or user.username)
    db.add(Draft(project_id=project.id, contact_id=contact.id, user_id=user.id,
                 channel=channel, intent=intent, content=out["draft"]))
    db.commit()
    return out


@app.post("/api/project/{slug}/sent")
def api_mark_sent(slug: str, payload: dict, user=Depends(require_user),
                  db=Depends(db_session)):
    """Log a message you actually sent — teaches Honcho your real voice."""
    project = db.query(Project).filter_by(slug=slug).first()
    contact = db.get(Contact, int(payload.get("contact_id", 0)))
    if not project or not contact:
        raise HTTPException(404)
    text = (payload.get("content") or "").strip()
    if text and contact.peer_id:
        hc.log_outbound(contact.peer_id, user.peer_id, project.slug, text)
    return {"ok": True}


@app.post("/api/project/{slug}/inbound")
def api_inbound(slug: str, payload: dict, user=Depends(require_user),
                db=Depends(db_session)):
    """Paste a message received FROM a contact — teaches Honcho who they are."""
    project = db.query(Project).filter_by(slug=slug).first()
    contact = db.get(Contact, int(payload.get("contact_id", 0)))
    if not project or not contact:
        raise HTTPException(404)
    text = (payload.get("content") or "").strip()
    if not text:
        raise HTTPException(400, "empty")
    if contact.peer_id:
        hc.log_inbound(contact.peer_id, project.slug, text)
    return {"ok": True, "honcho": hc.enabled()}


@app.post("/api/project/{slug}/notes")
def api_notes(slug: str, payload: dict, user=Depends(require_user),
              db=Depends(db_session)):
    project = db.query(Project).filter_by(slug=slug).first()
    if not project:
        raise HTTPException(404)
    project.notes = payload.get("notes", project.notes)
    db.commit()
    return {"ok": True}


@app.post("/api/contact/{cid}")
def api_contact(cid: int, payload: dict, user=Depends(require_user),
                db=Depends(db_session)):
    c = db.get(Contact, cid)
    if not c:
        raise HTTPException(404)
    for field in ("name", "role", "email", "slack", "style_notes"):
        if field in payload:
            setattr(c, field, payload[field])
    db.commit()
    return {"ok": True}


@app.post("/api/org/{org_id}/contact")
def api_contact_add(org_id: int, payload: dict, user=Depends(require_user),
                    db=Depends(db_session)):
    org = db.get(Org, org_id)
    if not org:
        raise HTTPException(404)
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    slug = "".join(ch for ch in name.lower().replace(" ", "-") if ch.isalnum() or ch == "-")
    c = Contact(org_id=org.id, name=name, role=payload.get("role", ""),
                peer_id=f"contact-{slug}-{org.slug}")
    db.add(c)
    db.commit()
    return {"ok": True, "id": c.id}


@app.get("/api/contact/{cid}/insight")
def api_contact_insight(cid: int, user=Depends(require_user),
                        db=Depends(db_session)):
    c = db.get(Contact, cid)
    if not c:
        raise HTTPException(404)
    if not hc.enabled():
        return {"insight": "Honcho not configured — set HONCHO_API_KEY."}
    out = hc.peer_insight(
        c.peer_id, f"What do we know about {c.name} — their role, priorities, "
                   f"and how they prefer to communicate?")
    return {"insight": out or "Nothing learned yet. Log some inbound messages from them."}


# ---------- jobs APIs ----------

@app.post("/api/jobs")
def api_job_add(payload: dict, user=Depends(require_user), db=Depends(db_session)):
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title required")
    platform = payload.get("platform", "other")
    default_kind = "job" if platform in ("indeed", "builtin", "hiring.cafe",
                                         "linkedin") else "freelance"
    j = Job(title=title, platform=platform,
            kind=payload.get("kind") or default_kind,
            url=payload.get("url", ""), client=payload.get("client", ""),
            budget=payload.get("budget", ""),
            description=payload.get("description", ""),
            screener=payload.get("screener", ""))
    db.add(j)
    db.commit()
    return {"ok": True, "id": j.id}


@app.post("/api/jobs/{jid}/score")
def api_job_score(jid: int, user=Depends(require_user), db=Depends(db_session)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404)
    out = ai.job_fit(j, get_setting(db, "resume_text"), get_setting(db, "profile"),
                     get_setting(db, "past_work"))
    j.fit_score = out["score"]
    j.fit_notes = out["notes"]
    db.commit()
    return out


@app.post("/api/jobs/{jid}/proposal")
def api_job_proposal(jid: int, user=Depends(require_user), db=Depends(db_session)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404)
    j.proposal = ai.job_proposal(j, get_setting(db, "resume_text"),
                                 get_setting(db, "profile"),
                                 get_setting(db, "portfolio_links"),
                                 get_setting(db, "past_work"))
    db.commit()
    return {"proposal": j.proposal}


@app.post("/api/jobs/{jid}/screener")
def api_job_screener(jid: int, payload: dict, user=Depends(require_user),
                     db=Depends(db_session)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404)
    j.screener = payload.get("screener", "")
    db.commit()
    return {"ok": True}


@app.post("/api/jobs/{jid}/delete")
def api_job_delete(jid: int, user=Depends(require_user), db=Depends(db_session)):
    j = db.get(Job, jid)
    if j:
        db.delete(j)
        db.commit()
    return {"ok": True}


@app.post("/api/drafts/{did}/delete")
def api_draft_delete(did: int, user=Depends(require_user), db=Depends(db_session)):
    d = db.get(Draft, did)
    if d:
        db.delete(d)
        db.commit()
    return {"ok": True}


@app.post("/api/jobs/{jid}/status")
def api_job_status(jid: int, payload: dict, user=Depends(require_user),
                   db=Depends(db_session)):
    j = db.get(Job, jid)
    if not j:
        raise HTTPException(404)
    if payload.get("status") in ("lead", "applied", "interview", "won", "lost"):
        j.status = payload["status"]
        db.commit()
    return {"ok": True}


# ---------- settings APIs ----------

@app.post("/settings")
def settings_save(request: Request, profile: str = Form(""),
                  portfolio_links: str = Form(""), past_work: str = Form(""),
                  resume_text: str = Form(""), user=Depends(require_user)):
    db = SessionLocal()
    set_setting(db, "profile", profile)
    set_setting(db, "portfolio_links", portfolio_links)
    set_setting(db, "past_work", past_work)
    set_setting(db, "resume_text", resume_text)
    db.close()
    return RedirectResponse("/settings", status_code=303)
