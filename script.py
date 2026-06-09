import json
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

handler = RotatingFileHandler(
    "log/smartcoop.log",
    maxBytes=1_000_000,
    backupCount=3
)

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s"
)

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


def parse_devices(value):
    """
    Parse OMLET_DEVICES from JSON.

    Example:
    [
        {
            "id": "12345",
            "open_offset": 15,
            "close_offset": -10
        }
    ]
    """
    if not value:
        return []

    devices = json.loads(value)

    result = []

    for device in devices:
        result.append({
            "device_id": str(device["id"]),
            "open_offset": int(device.get("open_offset", 0)),
            "close_offset": int(device.get("close_offset", 0))
        })

    return result


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


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

try:
    LATITUDE = float(os.environ.get("COOP_LATITUDE"))
    LONGITUDE = float(os.environ.get("COOP_LONGITUDE"))

    TIMEZONE = tz.gettz(
        os.environ.get("TIMEZONE")
    )

    OMLET_TOKEN = os.environ.get(
        "OMLET_API_TOKEN"
    )

    DEVICES = parse_devices(
        os.environ.get("OMLET_DEVICES", "")
    )

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

    if None in [
        LATITUDE,
        LONGITUDE,
        TIMEZONE,
        OMLET_TOKEN
    ]:
        raise ValueError(
            "Missing required environment variables"
        )

    if not DEVICES:
        raise ValueError(
            "No devices configured in OMLET_DEVICES"
        )

except Exception as e:
    logger.critical(
        f"Configuration error: {e}",
        exc_info=True
    )
    raise SystemExit(1)


# ----------------------------------------------------------------------
# Calculate sunrise / sunset
# ----------------------------------------------------------------------

try:
    sun = Sun(LATITUDE, LONGITUDE)

    today = datetime.today()
    tomorrow = today + timedelta(days=1)

    now = datetime.now(TIMEZONE)

    sunrise_today = (
        sun.get_sunrise_time(today)
        .astimezone(TIMEZONE)
    )

    sunset_today = (
        sun.get_sunset_time(today)
        .astimezone(TIMEZONE)
    )

    sunrise_tomorrow = (
        sun.get_sunrise_time(tomorrow)
        .astimezone(TIMEZONE)
    )

    sunset_tomorrow = (
        sun.get_sunset_time(tomorrow)
        .astimezone(TIMEZONE)
    )

    logger.info(f"Sunrise today: {sunrise_today}")
    logger.info(f"Sunset today: {sunset_today}")
    logger.info(f"Sunrise tomorrow: {sunrise_tomorrow}")
    logger.info(f"Sunset tomorrow: {sunset_tomorrow}")

except Exception as e:
    logger.error(
        f"Failed to calculate sun times: {e}",
        exc_info=True
    )
    raise SystemExit(1)


# ----------------------------------------------------------------------
# Determine base open / close time
# ----------------------------------------------------------------------

try:
    base_open_time = (
        sunrise_tomorrow
        if now > sunrise_today
        else sunrise_today
    )

    base_close_time = (
        sunset_tomorrow
        if now > sunset_today
        else sunset_today
    )

    logger.info(
        f"Base open time: {base_open_time}"
    )

    logger.info(
        f"Base close time: {base_close_time}"
    )

except Exception as e:
    logger.error(
        f"Failed to determine open/close times: {e}",
        exc_info=True
    )
    raise SystemExit(1)


# ----------------------------------------------------------------------
# Update all configured devices
# ----------------------------------------------------------------------

try:
    client = SmartCoopClient(
        client_secret=OMLET_TOKEN
    )

    omlet = Omlet(client)

    for device_cfg in DEVICES:

        device_id = device_cfg["device_id"]

        open_time = (
            base_open_time
            + timedelta(
                minutes=device_cfg["open_offset"]
            )
        )

        close_time = (
            base_close_time
            + timedelta(
                minutes=device_cfg["close_offset"]
            )
        )

        open_time = apply_min_time(
            open_time,
            EARLIEST_OPEN_TIME
        )

        open_time = apply_max_time(
            open_time,
            LATEST_OPEN_TIME
        )

        close_time = apply_min_time(
            close_time,
            EARLIEST_CLOSE_TIME
        )

        close_time = apply_max_time(
            close_time,
            LATEST_CLOSE_TIME
        )

        logger.info(
            f"Device {device_id}: "
            f"open={open_time.strftime('%H:%M')} "
            f"close={close_time.strftime('%H:%M')}"
        )

        device = omlet.get_device_by_id(
            device_id
        )

        configuration = device.configuration

        configuration.door.openMode = "time"
        configuration.door.openTime = (
            open_time.strftime("%H:%M")
        )

        configuration.door.closeMode = "time"
        configuration.door.closeTime = (
            close_time.strftime("%H:%M")
        )

        omlet.update_configuration(
            device.deviceId,
            configuration
        )

        logger.info(
            f"Device {device_id} updated successfully"
        )

    logger.info(
        f"Successfully updated {len(DEVICES)} device(s)"
    )

except Exception as e:
    logger.error(
        f"API error: {e}",
        exc_info=True
    )
    raise SystemExit(1)
