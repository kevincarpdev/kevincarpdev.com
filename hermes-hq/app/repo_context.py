"""Read-only repo awareness for the workspace chat.

Client repos live on the VPS at /opt/repos/<repo-name> and are mounted into
the container at REPOS_DIR (read-only). Each project's `repo` field must match
the folder name. On every chat turn we inject a capped file tree, plus the
contents of any files the user explicitly mentions by path/filename.

This is intentionally read-only — agentic edits/commits happen via Hermes CLI
inside the repo (phase 2 wires write access into the dashboard).
"""
import os
import re

REPOS_DIR = os.getenv("REPOS_DIR", "/repos")

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", "dist", "build",
             "bin", "obj", ".venv", "venv", "packages", ".vercel", "coverage"}
MAX_TREE_FILES = 400
MAX_FILE_CHARS = 9000
MAX_TOTAL_CHARS = 26000
TEXT_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".cs", ".sql", ".json",
            ".yaml", ".yml", ".md", ".txt", ".html", ".css", ".scss", ".sh",
            ".env.example", ".config", ".csproj", ".sln", ".xml", ".toml",
            ".ps1", ".prisma"}


def repo_path(repo_name: str):
    if not repo_name:
        return None
    path = os.path.join(REPOS_DIR, os.path.basename(repo_name.strip()))
    return path if os.path.isdir(path) else None


def file_tree(root: str):
    """Relative paths, capped, stable order."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS
                             and not d.startswith("."))
        for f in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, f), root)
            out.append(rel)
            if len(out) >= MAX_TREE_FILES:
                return out, True
    return out, False


def _is_texty(path: str) -> bool:
    return any(path.endswith(ext) for ext in TEXT_EXT)


def mentioned_files(message: str, tree: list):
    """Files referenced by relative path, filename, or filename stem.

    Stem matches ("OrderController" → OrderController.cs) are skipped when
    ambiguous (same stem in >3 places).
    """
    msg = message.lower()
    tokens = set(re.findall(r"[\w./\\-]{4,}", msg))
    exact, by_stem = [], {}
    for rel in tree:
        rl = rel.lower().replace("\\", "/")
        base = os.path.basename(rl)
        stem = base.rsplit(".", 1)[0]
        if rl in msg or (len(base) >= 6 and base in tokens):
            exact.append(rel)
        elif len(stem) >= 6 and stem in tokens:
            by_stem.setdefault(stem, []).append(rel)
    hits = exact[:6]
    for rels in by_stem.values():
        if len(rels) <= 3:
            for rel in rels:
                if rel not in hits and len(hits) < 6:
                    hits.append(rel)
    return hits[:6]


def build_context(repo_name: str, message: str):
    """Returns a system-prompt block, or None if repo isn't mounted."""
    root = repo_path(repo_name)
    if not root:
        return None
    tree, truncated = file_tree(root)
    parts = [f"Repository snapshot for {repo_name} (read-only mount; live checkout on the VPS):",
             "FILES:" + (" (truncated)" if truncated else ""),
             "\n".join(tree)]
    total = sum(len(p) for p in parts)
    for rel in mentioned_files(message, tree):
        full = os.path.join(root, rel)
        if not _is_texty(rel) or not os.path.isfile(full):
            continue
        try:
            with open(full, "r", errors="replace") as f:
                content = f.read(MAX_FILE_CHARS + 1)
        except OSError:
            continue
        clipped = " [truncated]" if len(content) > MAX_FILE_CHARS else ""
        block = f"\n--- {rel}{clipped} ---\n{content[:MAX_FILE_CHARS]}"
        if total + len(block) > MAX_TOTAL_CHARS:
            break
        parts.append(block)
        total += len(block)
    parts.append("\nIf you need a file that isn't shown, ask the user to mention "
                 "it by path and it will be included next turn. You cannot write "
                 "to the repo from here — for edits, direct work to Hermes CLI "
                 "in this repo on the VPS.")
    return "\n".join(parts)
