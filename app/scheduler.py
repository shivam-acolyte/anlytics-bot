import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.config import config
from app.services.analytics_service import analytics_service

logger = logging.getLogger("trackingbot.scheduler")

class DailyRefreshScheduler:
    _scheduler = None

    @classmethod
    def start(cls):
        if cls._scheduler is None:
            cls._scheduler = BackgroundScheduler(daemon=True)
            # Schedule daily at config.DAILY_REFRESH_HOUR (default 04:00 AM IST)
            cls._scheduler.add_job(
                cls.refresh_job,
                CronTrigger(hour=config.DAILY_REFRESH_HOUR, minute=0),
                id="daily_analytics_refresh",
                replace_existing=True
            )
            cls._scheduler.start()
            logger.info(f"Daily Analytics Refresh Scheduler started (Runs at {config.DAILY_REFRESH_HOUR}:00 daily).")
            # Run initial refresh on startup in background
            try:
                analytics_service.refresh_daily_cache()
            except Exception as e:
                logger.warning(f"Initial cache refresh skipped: {e}")

    @classmethod
    def refresh_job(cls):
        logger.info("Executing scheduled daily analytics rollup...")
        try:
            analytics_service.refresh_daily_cache()
            logger.info("Daily analytics refresh completed successfully.")
        except Exception as e:
            logger.error(f"Error during daily refresh job: {e}")

    @classmethod
    def trigger_now(cls):
        logger.info("Manual refresh triggered by user.")
        return analytics_service.refresh_daily_cache()

scheduler = DailyRefreshScheduler
