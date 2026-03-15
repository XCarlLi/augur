"""Pure asyncio scheduler. Uses loop.call_later() — zero external dependencies."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, time
from typing import Awaitable, Callable
from zoneinfo import ZoneInfo

from . import log


@dataclass(frozen=True)
class JobSpec:
    """A daily job that runs at a fixed time."""

    name: str
    hour: int
    minute: int = 0
    handler: Callable[[], Awaitable[None]] = lambda: None  # type: ignore[assignment]


class Scheduler:
    """Schedule daily and repeating async jobs on an existing event loop."""

    def __init__(self, loop: asyncio.AbstractEventLoop, tz: str) -> None:
        self._loop = loop
        self._tz = ZoneInfo(tz)
        self._handles: list[asyncio.TimerHandle] = []

    def add(self, spec: JobSpec) -> None:
        """Schedule a daily job at the given hour:minute."""
        self._schedule_daily(spec)

    def add_repeating(
        self, name: str, interval_seconds: int, handler: Callable[[], Awaitable[None]]
    ) -> None:
        """Schedule a repeating job every interval_seconds."""
        self._schedule_repeating(name, interval_seconds, handler)

    def cancel_all(self) -> None:
        """Cancel all scheduled jobs."""
        for handle in self._handles:
            handle.cancel()
        self._handles.clear()

    def _schedule_daily(self, spec: JobSpec) -> None:
        """Compute seconds until next trigger, schedule, and re-arm after firing."""
        delay = self._seconds_until(spec.hour, spec.minute)
        log.info(f"scheduled {spec.name} at {spec.hour:02d}:{spec.minute:02d} ({delay}s)")

        def _fire():
            async def _run():
                try:
                    await spec.handler()
                except Exception as e:
                    log.error(f"job {spec.name} failed", str(e))
                # Re-arm for next day
                self._schedule_daily(spec)

            asyncio.run_coroutine_threadsafe(_run(), self._loop)

        handle = self._loop.call_later(delay, _fire)
        self._handles.append(handle)

    def _schedule_repeating(
        self, name: str, interval: int, handler: Callable[[], Awaitable[None]]
    ) -> None:
        """Schedule a repeating job."""

        def _fire():
            async def _run():
                try:
                    await handler()
                except Exception as e:
                    log.error(f"job {name} failed", str(e))

            asyncio.run_coroutine_threadsafe(_run(), self._loop)
            # Re-arm
            h = self._loop.call_later(interval, _fire)
            self._handles.append(h)

        handle = self._loop.call_later(interval, _fire)
        self._handles.append(handle)
        log.info(f"scheduled {name} every {interval}s")

    def _seconds_until(self, hour: int, minute: int) -> int:
        """Seconds from now until the next occurrence of hour:minute in local tz."""
        now = datetime.now(self._tz)
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target = target.replace(day=target.day + 1)
        delta = (target - now).total_seconds()
        return max(1, int(delta))
