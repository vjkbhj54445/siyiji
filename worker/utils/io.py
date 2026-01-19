from __future__ import annotations
from pathlib import Path

def is_under_allowed_parent(candidate: str, parent: str) -> bool:
    """
    Ensure `candidate` path is inside `parent` directory using resolved paths.
    Avoids naive startswith checks which are vulnerable to path traversal.
    """
    try:
        c = Path(candidate).expanduser().resolve()
        p = Path(parent).expanduser().resolve()
        return c == p or p in c.parents
    except Exception:
        return False
