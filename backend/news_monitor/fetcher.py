import logging
import requests
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session
from models import DisruptionEvent

logger = logging.getLogger(__name__)

POLL_INTERVAL_MINUTES = 30

TARGET_CITIES = [
    "Kolkata", "Mumbai", "Chennai", "Bangalore", 
    "Ahmedabad", "Patna", "Guwahati", "Chandigarh", 
    "Haridwar", "Varanasi", "Gurgaon", "Delhi",
    "Hyderabad", "Pune", "Jaipur", "Surat", 
    "Lucknow", "Kanpur", "Nagpur", "Indore", 
    "Thane", "Bhopal", "Visakhapatnam", "Agra", 
    "Nashik", "Faridabad", "Rajkot", "Amritsar", 
    "Ranchi", "Coimbatore", "Ludhiana"
]

def fetch_gdelt_events() -> List[dict]:
    """Fetch recent disruptions from GDELT."""
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": "(flood OR earthquake OR outbreak OR strike OR quarantine)",
        "mode": "ArtList",
        "format": "json",
        "maxrecords": 10,
        "sort": "DateDesc"
    }
    
    events = []
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            articles = data.get("articles", [])
            for article in articles:
                title = article.get("title", "").lower()
                
                # Determine event type
                event_type = "other"
                if "flood" in title: event_type = "flood"
                elif "earthquake" in title: event_type = "earthquake"
                elif "outbreak" in title: event_type = "outbreak"
                elif "strike" in title: event_type = "strike"
                elif "quarantine" in title: event_type = "quarantine"
                
                # We'll use the domain or URL as a proxy for region if not easily parsable,
                # but let's just mark it as Global/News for now unless we do NER.
                region = article.get("domain", "Global")
                
                events.append({
                    "event_type": event_type,
                    "region": region,
                    "severity": "medium",  # default
                    "source": "GDELT"
                })
    except Exception as e:
        logger.error(f"GDELT fetch error: {e}")
        
    return events


def fetch_openweather_events(api_key: str) -> List[dict]:
    """Fetch current weather for key hubs and flag extreme conditions."""
    if not api_key:
        return []
        
    url = "https://api.openweathermap.org/data/2.5/weather"
    events = []
    
    for city in TARGET_CITIES:
        params = {
            "q": f"{city},IN",
            "appid": api_key,
            "units": "metric"
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                weather_main = data["weather"][0]["main"].lower()
                weather_id = data["weather"][0]["id"]
                
                # Condition codes: https://openweathermap.org/weather-conditions
                # 2xx: Thunderstorm, 5xx: Rain, 6xx: Snow, 781: Tornado
                if weather_id < 600 or weather_id == 781:
                    event_type = "flood" if weather_id >= 500 else "storm"
                    severity = "high" if weather_id in [212, 232, 503, 504, 781] else "medium"
                    
                    events.append({
                        "event_type": event_type,
                        "region": city,
                        "severity": severity,
                        "source": "OpenWeather"
                    })
        except Exception as e:
            logger.error(f"OpenWeather fetch error for {city}: {e}")
            
    return events


def poll_and_store(db_factory, openweather_key: str):
    """Fetch from APIs and store new events in DB."""
    logger.info("CrisisAI Scheduler: Polling GDELT and OpenWeather...")
    db: Session = db_factory()
    
    try:
        new_events_data = []
        new_events_data.extend(fetch_gdelt_events())
        new_events_data.extend(fetch_openweather_events(openweather_key))
        
        inserted = 0
        for data in new_events_data:
            # Check if active event of same type and region already exists
            existing = db.query(DisruptionEvent).filter(
                DisruptionEvent.event_type == data["event_type"],
                DisruptionEvent.region == data["region"],
                DisruptionEvent.resolved_at == None
            ).first()
            
            if not existing:
                event = DisruptionEvent(
                    event_type=data["event_type"],
                    region=data["region"],
                    severity=data["severity"],
                    source=data["source"]
                )
                db.add(event)
                inserted += 1
                
        if inserted > 0:
            db.commit()
            logger.info(f"CrisisAI Scheduler: Inserted {inserted} new disruption events.")
        else:
            logger.info("CrisisAI Scheduler: No new disruption events detected.")
            
    except Exception as e:
        logger.error(f"CrisisAI Scheduler error: {e}")
        db.rollback()
    finally:
        db.close()


def start_scheduler(db_session_factory, openweather_api_key: str = "") -> Optional[object]:
    """Start APScheduler for news monitoring."""
    if not openweather_api_key:
        logger.warning(
            "NewsMonitor: OPENWEATHER_API_KEY not set. "
            "Weather monitoring disabled. GDELT will still run."
        )

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("APScheduler not installed — Crisis AI automated polling disabled.")
        return None

    def _job():
        poll_and_store(db_session_factory, openweather_api_key)

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _job,
        trigger="interval",
        minutes=POLL_INTERVAL_MINUTES,
        id="crisis_ai_news_poll",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"CrisisAI scheduler started — polling every {POLL_INTERVAL_MINUTES} minutes.")
    
    # Run once immediately on startup
    _job()
    
    return scheduler
