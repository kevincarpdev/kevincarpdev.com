"""Idempotent seed: current orgs, projects, contacts. Run:
  python -m app.seed
"""
from .db import Contact, Org, Project, SessionLocal, init_db, set_setting


def seed():
    init_db()
    db = SessionLocal()

    def org(slug, name, notes=""):
        o = db.query(Org).filter_by(slug=slug).first()
        if not o:
            o = Org(slug=slug, name=name, notes=notes)
            db.add(o)
            db.commit()
        return o

    def project(org_, slug, name, repo="", notes=""):
        p = db.query(Project).filter_by(slug=slug).first()
        if not p:
            db.add(Project(org_id=org_.id, slug=slug, name=name, repo=repo,
                           notes=notes))
            db.commit()

    def contact(org_, name, role, peer_id, style_notes=""):
        c = db.query(Contact).filter_by(peer_id=peer_id).first()
        if not c:
            db.add(Contact(org_id=org_.id, name=name, role=role,
                           peer_id=peer_id, style_notes=style_notes))
            db.commit()

    qolos = org("qolos", "Qolos",
                "Agency partner. We deliver dev work through Qolos for their clients.")
    project(qolos, "stryker-bc", "Stryker BigCommerce", repo="Stryker.BC",
            notes="BigCommerce build for Stryker, delivered with/through Qolos.")
    contact(qolos, "Chad", "Main point of contact", "contact-chad-qolos",
            "Primary stakeholder — keep updates outcome- and timeline-focused.")
    contact(qolos, "Jim", "Developer (Qolos)", "contact-jim-qolos",
            "Engineer — fine to go deep on implementation detail.")

    fore = org("fore-genomics", "Fore Genomics", "Direct client.")
    project(fore, "fg-parent-portal", "Parent Portal",
            repo="fore-genomics-parent-portal",
            notes="Health portal for parents (genomics results).")
    contact(fore, "Kyle", "(set role)", "contact-kyle-foregenomics")
    contact(fore, "Suzanna", "(set role)", "contact-suzanna-foregenomics")

    set_setting(db, "profile",
                "Kevin Carpenter — freelance/contract software developer. "
                "Site: kevincarp.com · LinkedIn: linkedin.com/in/kevin-carpenter-304a4554")
    db.close()
    print("Seeded. Edit roles/style notes in the UI as you learn them.")


if __name__ == "__main__":
    seed()
