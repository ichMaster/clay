"""
LLM configuration -- loaded from a .env file at the project root.

Every knob the LLM brain needs (API key, model, token budget) lives in one
.env file instead of being scattered through the code. Stdlib only: a tiny
KEY=VALUE parser, no python-dotenv dependency, in keeping with the rest of the
core. Real environment variables take precedence over .env, so you can still
override per run with `export VAR=... python game.py`.

The Anthropic SDK reads ANTHROPIC_API_KEY straight from the environment, so once
load_dotenv() has run, `anthropic.Anthropic()` picks up the key with no wiring.
"""

from __future__ import annotations
import os
from pathlib import Path

# The project root is the directory that holds .env (one level above brains/).
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_dotenv(path: Path = ENV_PATH) -> dict:
    """Parse a simple KEY=VALUE .env file into os.environ.

    - Blank lines and lines starting with `#` are ignored (put comments on their
      own line -- inline `# ...` after a value is NOT stripped).
    - A leading `export ` is tolerated.
    - Surrounding single/double quotes around the value are stripped.
    - Real environment variables WIN: an already-set var is never overwritten,
      so `export ANTHROPIC_MODEL=... ; python game.py` still overrides .env.

    Returns the dict that was parsed (handy for debugging).
    """
    parsed: dict = {}
    if not path.exists():
        return parsed
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        parsed[key] = value
        os.environ.setdefault(key, value)   # real env wins over .env
    return parsed


# Load on import, so importing config (or LLMBrain) is enough to pick up .env.
load_dotenv()

# ---- the LLM knobs (read after load) ----------------------------------------
API_KEY = os.environ.get("ANTHROPIC_API_KEY") or None
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")
MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "200"))


def is_configured() -> bool:
    """True if an API key is available -- safe to start the LLM brain.
    When False, the caller should fall back to the offline StubBrain."""
    return bool(API_KEY)
