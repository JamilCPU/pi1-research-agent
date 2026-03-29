#!/usr/bin/env python3
"""
Pi 1 Research Agent — scheduler and orchestrator.

Each cycle:
  1. Runs the 'researcher' OpenClaw skill — web searches, scores, returns candidates
  2. Saves each qualifying candidate as a research file in the research folder
  3. For each new research file, runs the 'requirements-writer' OpenClaw skill
  4. Saves the generated requirements doc to the handoff folder for Pis 2 & 3
"""

import json
import logging
import re
import signal
import sys
import time
import yaml
from datetime import datetime
from pathlib import Path

from openclaw_client import run_skill, extract_json
from deduplicator import is_duplicate
from cycle_logger import CycleLogger


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def setup_logging(log_file: str) -> None:
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


def slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_").lower()
    return slug[:60]


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M")


# ──────────────────────────────────────────────────────────────────────────────
# Phase 1 — Research
# ──────────────────────────────────────────────────────────────────────────────

def run_research(config: dict) -> list[dict]:
    """
    Invoke the researcher skill. Returns a list of qualifying opportunity dicts.
    """
    log = logging.getLogger(__name__)
    thresholds = config["thresholds"]

    prompt = (
        f"Run a full research cycle. Find software product opportunities. "
        f"Only include candidates with monetizability >= {thresholds['monetizability']} "
        f"AND feasibility >= {thresholds['feasibility']}. "
        f"Output a JSON array."
    )

    raw_output = run_skill("opportunity-scanner", prompt, config)

    try:
        candidates = extract_json(raw_output)
    except ValueError as e:
        log.error(f"Failed to parse researcher output: {e}")
        return []

    if not isinstance(candidates, list):
        log.error(f"Researcher returned unexpected type: {type(candidates)}")
        return []

    log.info(f"Researcher returned {len(candidates)} qualifying candidates")
    return candidates


# ──────────────────────────────────────────────────────────────────────────────
# Phase 2 — Save research files
# ──────────────────────────────────────────────────────────────────────────────

def save_research_files(
    candidates: list[dict],
    research_folder: Path,
    handoff_folder: Path,
    config: dict,
) -> list[Path]:
    """
    For each candidate:
      - Skip if a similar requirements doc already exists (deduplication)
      - Save as a JSON research file in research_folder/pending/
    Returns list of saved file paths.
    """
    log = logging.getLogger(__name__)
    pending_dir = research_folder / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    saved = []

    for candidate in candidates:
        title = candidate.get("title", "untitled")

        # Deduplicate against existing requirements docs in handoff folder
        if is_duplicate(candidate, handoff_folder, config):
            log.info(f"Duplicate skipped: {title[:60]}")
            continue

        filename = f"{slugify(title)}_{timestamp()}.json"
        filepath = pending_dir / filename
        filepath.write_text(json.dumps(candidate, indent=2), encoding="utf-8")
        log.info(f"Research saved: {filepath.name}")
        saved.append(filepath)

    return saved


# ──────────────────────────────────────────────────────────────────────────────
# Phase 3 — Requirements generation
# ──────────────────────────────────────────────────────────────────────────────

def generate_requirements(research_file: Path, config: dict) -> str:
    """
    Invoke the requirements-writer skill with the research file content.
    Returns the generated markdown document as a string.
    """
    research = json.loads(research_file.read_text(encoding="utf-8"))

    prompt = (
        f"Write a complete engineering requirements document for this opportunity.\n\n"
        f"RESEARCH BRIEF:\n"
        f"Title: {research.get('title', '')}\n"
        f"Problem: {research.get('problem', '')}\n"
        f"Evidence: {research.get('evidence', '')}\n"
        f"Sources: {', '.join(research.get('sources', []))}\n"
        f"Monetizability: {research.get('monetizability', 0)}/10,000\n"
        f"Feasibility: {research.get('feasibility', 0)}/10,000\n"
        f"Scoring Reasoning: {research.get('reasoning', '')}\n"
        f"Suggested Stack: {research.get('suggested_stack', '')}\n\n"
        f"Output the full requirements document in markdown. Nothing else."
    )

    return run_skill("requirements-writer", prompt, config)


def process_research_files(
    research_folder: Path,
    handoff_folder: Path,
    config: dict,
) -> tuple[list[str], list[str]]:
    """
    Process all pending research files:
      - Run requirements-writer for each
      - Save output to handoff folder
      - Move research file to done/
    Returns (generated filenames, failed titles).
    """
    log = logging.getLogger(__name__)
    pending_dir = research_folder / "pending"
    done_dir = research_folder / "done"
    done_dir.mkdir(parents=True, exist_ok=True)
    handoff_folder.mkdir(parents=True, exist_ok=True)

    pending_files = list(pending_dir.glob("*.json"))
    if not pending_files:
        return [], []

    log.info(f"Processing {len(pending_files)} research files")
    generated = []
    failed = []

    for research_file in pending_files:
        title = research_file.stem  # filename as fallback title
        try:
            # Read actual title from JSON for logging
            data = json.loads(research_file.read_text())
            title = data.get("title", title)

            log.info(f"Generating requirements for: {title[:70]}")
            doc = generate_requirements(research_file, config)

            # Save requirements doc
            req_filename = f"{slugify(title)}_{timestamp()}.md"
            req_path = handoff_folder / req_filename
            req_path.write_text(doc, encoding="utf-8")
            log.info(f"Requirements saved: {req_path.name}")
            generated.append(req_filename)

            # Move research file to done/
            research_file.rename(done_dir / research_file.name)

        except Exception as e:
            log.error(f"Requirements generation failed for '{title[:60]}': {e}", exc_info=True)
            failed.append(title)

    return generated, failed


# ──────────────────────────────────────────────────────────────────────────────
# Cycle
# ──────────────────────────────────────────────────────────────────────────────

def run_cycle(config: dict, cycle_logger: CycleLogger) -> None:
    log = logging.getLogger(__name__)
    cycle_logger.start_cycle()

    research_folder = Path(config["paths"]["research_folder"])
    handoff_folder = Path(config["paths"]["handoff_folder"])

    # Phase 1 — research
    log.info("=== Phase 1: Research ===")
    candidates = run_research(config)
    cycle_logger.log_scrape(len(candidates))
    cycle_logger.log_scoring(len(candidates), len(candidates))  # researcher pre-filters

    if not candidates:
        log.info("No candidates this cycle.")
        cycle_logger.end_cycle([], [])
        return

    # Phase 2 — save research files
    log.info("=== Phase 2: Saving research files ===")
    saved_files = save_research_files(candidates, research_folder, handoff_folder, config)
    log.info(f"{len(saved_files)} new research files saved ({len(candidates) - len(saved_files)} duplicates skipped)")
    cycle_logger.log_dedup(
        len(candidates),
        len(saved_files),
        [c.get("title", "?") for c in candidates if not any(
            slugify(c.get("title", "")) in str(f) for f in saved_files
        )],
    )

    if not saved_files:
        log.info("All candidates were duplicates — nothing to generate.")
        cycle_logger.end_cycle([], [])
        return

    # Phase 3 — requirements generation
    log.info("=== Phase 3: Requirements generation ===")
    generated, failed = process_research_files(research_folder, handoff_folder, config)
    cycle_logger.end_cycle(generated, failed)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    config = load_config()
    setup_logging(config["paths"]["log_file"])
    log = logging.getLogger(__name__)

    interval = config["cycle_interval_seconds"]
    log.info(
        f"Pi 1 Research Agent started. "
        f"Interval: {interval}s | "
        f"Thresholds: M≥{config['thresholds']['monetizability']} "
        f"F≥{config['thresholds']['feasibility']}"
    )

    cycle_logger = CycleLogger(config["paths"]["log_file"])

    def shutdown(sig, frame):
        log.info(f"Shutdown signal received ({sig}). Exiting.")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    while True:
        try:
            run_cycle(config, cycle_logger)
        except Exception as e:
            log.error(f"Unhandled cycle error: {e}", exc_info=True)

        log.info(f"Sleeping {interval}s until next cycle.")
        time.sleep(interval)


if __name__ == "__main__":
    main()
