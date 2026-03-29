"""
Structured cycle-level logging.
Writes a summary entry per cycle to the agent log.
"""

import logging
from datetime import datetime

log = logging.getLogger(__name__)


class CycleLogger:
    def __init__(self, log_file: str = ""):
        self._cycle_start: datetime | None = None
        self._raw_count = 0
        self._candidates_count = 0

    def start_cycle(self) -> None:
        self._cycle_start = datetime.now()
        self._raw_count = 0
        self._candidates_count = 0
        log.info(
            "=" * 60
            + f"\nCYCLE START: {self._cycle_start.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def log_scrape(self, raw_count: int) -> None:
        self._raw_count = raw_count
        log.info(f"[SCRAPE] {raw_count} raw opportunities collected")

    def log_scoring(self, total: int, candidates: int) -> None:
        self._candidates_count = candidates
        pct = (candidates / total * 100) if total else 0
        log.info(
            f"[SCORE] {total} scored → {candidates} above thresholds ({pct:.1f}%)"
        )

    def log_dedup(
        self, pre_dedup: int, post_dedup: int, skipped_titles: list[str]
    ) -> None:
        log.info(
            f"[DEDUP] {pre_dedup} candidates → {post_dedup} new "
            f"({pre_dedup - post_dedup} duplicates skipped)"
        )
        for title in skipped_titles:
            log.info(f"  └─ Duplicate: {title}")

    def end_cycle(self, generated: list[str], failed: list[str]) -> None:
        elapsed = ""
        if self._cycle_start:
            secs = (datetime.now() - self._cycle_start).total_seconds()
            elapsed = f" | elapsed {secs:.0f}s"

        log.info(
            f"[CYCLE END] Docs generated: {len(generated)} | "
            f"Failed: {len(failed)}{elapsed}"
        )
        for filename in generated:
            log.info(f"  └─ Generated: {filename}")
        for title in failed:
            log.warning(f"  └─ Failed: {title}")
        log.info("=" * 60)
