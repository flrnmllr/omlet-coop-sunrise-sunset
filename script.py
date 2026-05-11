import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from datetime import datetime, timedelta
from dateutil import tz
from suntime import Sun
from smartcoop.client import SmartCoopClient
from smartcoop.api.omlet import Omlet

logger = logging.getLogger("smartcoop")
logger.setLevel(logging.INFO)

handler = RotatingFileHandler("log/smartcoop.log", maxBytes=1_000_000, backupCount=3)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)

logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())

load_dotenv()

def parse_optional_time(value):
    """
    Parse HH:MM into datetime.time or return None.
    """
    if not value:
        return None

    return datetime.strptime(value, "%H:%M").time()


def apply_min_time(dt, min_time):
    """
    Ensure datetime is not earlier than min_time.
    """
    if min_time is None:
        return dt

    minimum = dt.replace(
        hour=min_time.hour,
        minute=min_time.minute,
        second=0,
        microsecond=0
    )

    return max(dt, minimum)


def apply_max_time(dt, max_time):
    """
    Ensure datetime is not later than max_time.
    """
    if max_time is None:
        return dt

    maximum = dt.replace(
        hour=max_time.hour,
        minute=max_time.minute,
        second=0,
        microsecond=0
    )

    return min(dt, maximum)

try:
    LATITUDE = float(os.environ.get("COOP_LATITUDE"))
    LONGITUDE = float(os.environ.get("COOP_LONGITUDE"))
    TIMEZONE = tz.gettz(os.environ.get("TIMEZONE"))
    OMLET_TOKEN = os.environ.get("OMLET_API_TOKEN")
    DEVICE_ID = os.environ.get("OMLET_DEVICE_ID")

    EARLIEST_OPEN_TIME = parse_optional_time(
        os.environ.get("EARLIEST_OPEN_TIME", "08:00")
    )

    LATEST_OPEN_TIME = parse_optional_time(
        os.environ.get("LATEST_OPEN_TIME", "10:00")
    )

    EARLIEST_CLOSE_TIME = parse_optional_time(
        os.environ.get("EARLIEST_CLOSE_TIME", "18:00")
    )

    LATEST_CLOSE_TIME = parse_optional_time(
        os.environ.get("LATEST_CLOSE_TIME", "20:00")
    )

    if None in [LATITUDE, LONGITUDE, TIMEZONE, OMLET_TOKEN, DEVICE_ID]:
        raise ValueError("Missing required environment variables")

except Exception as e:
    logger.critical(f"Configuration error: {e}", exc_info=True)
    raise SystemExit(1)

try:
    sun = Sun(LATITUDE, LONGITUDE)

    today = datetime.today()
    tomorrow = today + timedelta(days=1)
    now = datetime.now(TIMEZONE)

    sunrise_today = sun.get_sunrise_time(today).astimezone(TIMEZONE)
    sunset_today = sun.get_sunset_time(today).astimezone(TIMEZONE)
    sunrise_tomorrow = sun.get_sunrise_time(tomorrow).astimezone(TIMEZONE)
    sunset_tomorrow = sun.get_sunset_time(tomorrow).astimezone(TIMEZONE)

    logger.info(f"Sunrise today: {sunrise_today}")
    logger.info(f"Sunset today: {sunset_today}")
    logger.info(f"Sunrise tomorrow: {sunrise_tomorrow}")
    logger.info(f"Sunset tomorrow: {sunset_tomorrow}")

except Exception as e:
    logger.error(f"Failed to calculate sun times: {e}", exc_info=True)
    raise SystemExit(1)

try:
    open_time = sunrise_tomorrow if now > sunrise_today else sunrise_today
    close_time = sunset_tomorrow if now > sunset_today else sunset_today

    open_time = apply_min_time(open_time, EARLIEST_OPEN_TIME)
    open_time = apply_max_time(open_time, LATEST_OPEN_TIME)
    close_time = apply_min_time(close_time, EARLIEST_CLOSE_TIME)
    close_time = apply_max_time(close_time, LATEST_CLOSE_TIME)

    logger.info(f"Open time: {open_time}")
    logger.info(f"Close time: {close_time}")

except Exception as e:
    logger.error(f"Failed to determine open/close times: {e}", exc_info=True)
    raise SystemExit(1)

try:
    client = SmartCoopClient(client_secret=OMLET_TOKEN)
    omlet = Omlet(client)

    device = omlet.get_device_by_id(DEVICE_ID)
    configuration = device.configuration

    configuration.door.openMode = "time"
    configuration.door.openTime = open_time.strftime("%H:%M")
    configuration.door.closeMode = "time"
    configuration.door.closeTime = close_time.strftime("%H:%M")

    logger.info(f"New configuration: open={configuration.door.openTime}, close={configuration.door.closeTime}")

    omlet.update_configuration(device.deviceId, configuration)

    logger.info("Configuration updated successfully")

except Exception as e:
    logger.error(f"API error: {e}", exc_info=True)
    raise SystemExit(1)