import random
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from scraper.core.config import Config
from scraper.main import load_symbol_roster
from scraper.scheduler.jobs import scrape_symbol_job


def start_scheduler() -> None:
    scheduler_cfg = Config.get("scheduler", default={}) or {}
    symbols = load_symbol_roster()

    if not symbols:
        raise RuntimeError("No symbols configured for scheduler")

    timezone = scheduler_cfg.get("timezone", "Asia/Kolkata")
    daily_run_time = scheduler_cfg.get("daily_run_time", "18:30")
    jitter_seconds = int(scheduler_cfg.get("jitter_seconds", 30))

    try:
        hour_str, minute_str = daily_run_time.split(":")
        hour, minute = int(hour_str), int(minute_str)
    except ValueError as exc:  # noqa: BLE001
        raise ValueError(f"Invalid daily_run_time format: {daily_run_time}") from exc

    scheduler = BlockingScheduler(timezone=timezone)

    for symbol in symbols:
        scheduler.add_job(
            scrape_symbol_job,
            trigger=CronTrigger(hour=hour, minute=minute),
            args=[symbol],
            id=f"scrape_{symbol}",
            max_instances=1,
            misfire_grace_time=300,
            coalesce=True,
        )

        if jitter_seconds > 0:
            time.sleep(random.randint(1, jitter_seconds))

    scheduler.start()

