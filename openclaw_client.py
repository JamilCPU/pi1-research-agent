"""
OpenClaw client — agent invocation and response parsing.

Correct invocation:
  openclaw agent --agent main --message "<instructions + task>" --json

Skills in this project are instruction files (skills/*.md). Their content is
read and passed directly as the message body — OpenClaw's main agent executes them.
"""

import json
import logging
import re
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

SKILLS_DIR = Path(__file__).parent / "skills"


def _load_instructions(skill_name: str) -> str:
    """Read skill .md file, strip YAML frontmatter, return instruction body."""
    path = SKILLS_DIR / f"{skill_name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill file not found: {path}")

    content = path.read_text(encoding="utf-8")

    # Strip --- frontmatter block if present
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:].lstrip("\n")

    return content.strip()


def run_skill(skill_name: str, prompt: str, config: dict) -> str:
    """
    Run an OpenClaw agent turn using a skill's instruction file as context.
    Passes the full instructions + task prompt as the message to the main agent.
    Returns the agent's response text.
    """
    oc = config.get("openclaw", {})
    timeout = oc.get("skill_timeout_seconds", 600)
    agent = oc.get("agent", "main")

    instructions = _load_instructions(skill_name)
    message = f"{instructions}\n\n---\n\nTASK: {prompt}"

    cmd = [
        "openclaw", "agent",
        "--agent", agent,
        "--message", message,
        "--json",
        "--timeout", str(timeout),
    ]

    log.info(f"Running skill '{skill_name}' via OpenClaw agent '{agent}'")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Skill '{skill_name}' timed out after {timeout}s")
    except FileNotFoundError:
        raise RuntimeError("openclaw binary not found. Run: which openclaw")

    if result.returncode != 0:
        raise RuntimeError(
            f"Skill '{skill_name}' failed (exit {result.returncode}): "
            f"{result.stderr[:600]}"
        )

    return _extract_response(result.stdout, skill_name)


def _extract_response(stdout: str, skill_name: str) -> str:
    """
    Extract text response from openclaw agent --json output.
    Structure: result.payloads[0].text
    """
    try:
        data = json.loads(stdout.strip())
        payloads = data.get("result", {}).get("payloads", [])
        if payloads:
            text = payloads[0].get("text", "")
            if text:
                return text
    except (json.JSONDecodeError, TypeError, IndexError):
        log.debug(f"Skill '{skill_name}': could not parse JSON response — using raw stdout")

    return stdout


def extract_json(text: str) -> list | dict:
    """
    Parse JSON from agent response text. Three passes:
    1. Direct parse
    2. Strip markdown code fences
    3. Extract first [...] or {...} block via regex
    """
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass

    for pattern in (r"\[[\s\S]+\]", r"\{[\s\S]+\}"):
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    raise ValueError(f"No valid JSON in agent response. First 400 chars: {text[:400]}")
