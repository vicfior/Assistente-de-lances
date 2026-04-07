from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event
from typing import Callable, Optional

from browser import BrowserAutomation, ElementSnapshot


@dataclass
class ChangeEvent:
    old_value: str
    new_value: str
    timestamp: str
    locator_description: str


@dataclass
class MonitorStats:
    started_at: str
    monitored_label: str
    checks_performed: int = 0
    changes_detected: int = 0
    current_value: str = ""
    initial_value: str = ""
    last_change_at: str = ""
    locator_description: str = ""


class AuctionMonitor:
    def __init__(
        self,
        browser: BrowserAutomation,
        logger,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self.browser = browser
        self.logger = logger
        self.sleep_func = sleep_func

    def fetch_current_value(self, url: str, selector: str, selector_type: str) -> ElementSnapshot:
        snapshot = self.browser.get_field_value(url, selector, selector_type)
        self.logger.info("Campo localizado com sucesso: %s", snapshot.locator_description)
        return snapshot

    def detect_change(
        self,
        previous_value: str,
        current_value: str,
        locator_description: str,
    ) -> Optional[ChangeEvent]:
        if previous_value == current_value:
            return None

        return ChangeEvent(
            old_value=previous_value,
            new_value=current_value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            locator_description=locator_description,
        )

    def monitor(
        self,
        url: str,
        selector: str,
        selector_type: str,
        interval_seconds: float,
        on_change: Callable[[ChangeEvent], None],
        max_cycles: Optional[int] = None,
        on_stats: Optional[Callable[[MonitorStats], None]] = None,
        on_initialized: Optional[Callable[[ElementSnapshot, MonitorStats], None]] = None,
        stop_event: Optional[Event] = None,
    ) -> MonitorStats:
        cycle = 0
        previous_snapshot = self.fetch_current_value(url, selector, selector_type)
        self.logger.info("Valor inicial capturado: %s", previous_snapshot.value)
        stats = MonitorStats(
            started_at=datetime.now(timezone.utc).isoformat(),
            monitored_label=selector,
            checks_performed=1,
            current_value=previous_snapshot.value,
            initial_value=previous_snapshot.value,
            locator_description=previous_snapshot.locator_description,
        )
        if on_stats:
            on_stats(stats)
        if on_initialized:
            on_initialized(previous_snapshot, stats)

        while True:
            if stop_event and stop_event.is_set():
                self.logger.info("Monitoramento interrompido manualmente.")
                return stats
            if max_cycles is not None and cycle >= max_cycles:
                self.logger.info("Monitoramento encerrado apos %s ciclos.", cycle)
                return stats

            self.sleep_func(interval_seconds)
            try:
                current_snapshot = self.fetch_current_value(url, selector, selector_type)
            except Exception as exc:
                self.logger.exception("Falha ao consultar valor atual: %s", exc)
                cycle += 1
                stats.checks_performed += 1
                if on_stats:
                    on_stats(stats)
                continue

            stats.checks_performed += 1
            stats.current_value = current_snapshot.value
            stats.locator_description = current_snapshot.locator_description
            change_event = self.detect_change(
                previous_value=previous_snapshot.value,
                current_value=current_snapshot.value,
                locator_description=current_snapshot.locator_description,
            )

            if change_event:
                self.logger.info(
                    "Alteracao detectada | anterior=%s | novo=%s | timestamp=%s",
                    change_event.old_value,
                    change_event.new_value,
                    change_event.timestamp,
                )
                stats.changes_detected += 1
                stats.last_change_at = change_event.timestamp
                on_change(change_event)
                previous_snapshot = current_snapshot
            else:
                self.logger.info("Nenhuma alteracao detectada. Valor atual: %s", current_snapshot.value)

            if on_stats:
                on_stats(stats)
            cycle += 1
