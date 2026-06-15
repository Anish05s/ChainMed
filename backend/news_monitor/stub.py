"""
News Monitor — Phase 3 stub.
=========================================
Phase 3 upgrade: wire up GDELT + OpenWeather to auto-detect disruption events.

To enable:
  1. Set OPENWEATHER_API_KEY in .env (GDELT needs no key)
  2. Replace this stub with news_monitor/fetcher.py containing:
     - fetch_gdelt_events(query="flood OR earthquake OR outbreak") → List[Article]
     - fetch_openweather_alerts(region) → List[Alert]
     - parse_article_to_event(article) → DisruptionEvent | None
     - schedule_news_poll(db_factory, interval_minutes=30)
  3. Import and start the scheduler in main.py (same pattern as inventory_ai)

Current state: logs a startup notice only.
"""
import logging

logger = logging.getLogger(__name__)


def start_news_monitor(openweather_api_key: str = "") -> None:
    if not openweather_api_key:
        logger.info(
            "NewsMonitor: OPENWEATHER_API_KEY not set — external monitoring disabled. "
            "Events can still be submitted manually via POST /crisis/events. "
            "Set OPENWEATHER_API_KEY in .env to enable Phase 3 auto-detection."
        )
        return

    # Phase 3: import fetcher and start scheduler here
    logger.info("NewsMonitor: OPENWEATHER_API_KEY present — Phase 3 polling ready to wire up.")
