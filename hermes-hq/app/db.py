import datetime
import os

from sqlalchemy import (Column, DateTime, Float, ForeignKey, Integer, String,
                        Text, create_engine)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from .config import DATABASE_URL

if DATABASE_URL.startswith("sqlite:///"):
    path = DATABASE_URL.replace("sqlite:///", "")
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


def now():
    return datetime.datetime.utcnow()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    display_name = Column(String, default="")
    pw_hash = Column(String, nullable=False)
    peer_id = Column(String, default="")  # honcho peer, e.g. team-kevin


class Org(Base):
    __tablename__ = "orgs"
    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    notes = Column(Text, default="")
    projects = relationship("Project", back_populates="org")
    contacts = relationship("Contact", back_populates="org")


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("orgs.id"))
    slug = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    repo = Column(String, default="")
    links = Column(Text, default="")  # one per line: Label|URL
    notes = Column(Text, default="")  # standing context for the AI
    status = Column(String, default="active")
    org = relationship("Org", back_populates="projects")


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey("orgs.id"))
    name = Column(String, nullable=False)
    role = Column(String, default="")
    email = Column(String, default="")
    slack = Column(String, default="")
    style_notes = Column(Text, default="")  # how we talk to this person
    peer_id = Column(String, default="")  # honcho peer, e.g. contact-chad-qolos
    org = relationship("Org", back_populates="contacts")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    role = Column(String, nullable=False)  # user | assistant
    content = Column(Text, nullable=False)
    created = Column(DateTime, default=now)


class Draft(Base):
    __tablename__ = "drafts"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    contact_id = Column(Integer, ForeignKey("contacts.id"))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    channel = Column(String, default="email")  # email | slack
    intent = Column(Text, default="")
    content = Column(Text, default="")
    created = Column(DateTime, default=now)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    platform = Column(String, default="upwork")  # upwork | linkedin | direct | other
    url = Column(String, default="")
    client = Column(String, default="")
    budget = Column(String, default="")
    description = Column(Text, default="")
    status = Column(String, default="lead")  # lead | applied | interview | won | lost
    fit_score = Column(Float, nullable=True)
    fit_notes = Column(Text, default="")
    proposal = Column(Text, default="")
    created = Column(DateTime, default=now)


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String, primary_key=True)
    value = Column(Text, default="")


def init_db():
    Base.metadata.create_all(engine)


def get_setting(db, key, default=""):
    row = db.get(Setting, key)
    return row.value if row else default


def set_setting(db, key, value):
    row = db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()
