import os
from datetime import date, datetime, timedelta
from dateutil import tz
from suntime import Sun
from smartcoop.client import SmartCoopClient
from smartcoop.api.omlet import Omlet

LATITUDE = float(os.environ.get('COOP_LATITUDE'))
LONGITUDE = float(os.environ.get('COOP_LONGITUDE'))
TIMEZONE = tz.gettz(os.environ.get('TIMEZONE'))
OMLET_TOKEN = os.environ.get('OMLET_API_TOKEN')
DEVICE_ID = os.environ.get('OMLET_DEVICE_ID')

sun = Sun(LATITUDE, LONGITUDE)
today = datetime.today()
tomorrow = today + timedelta(days=1)
now = datetime.now(TIMEZONE)

sunrise_today_utc = sun.get_sunrise_time(today)
sunset_today_utc = sun.get_sunset_time(today)
sunrise_tomorrow_utc = sun.get_sunrise_time(tomorrow)
sunset_tomorrow_utc = sun.get_sunset_time(tomorrow)

sunrise_today = sunrise_today_utc.astimezone(TIMEZONE)
sunset_today = sunset_today_utc.astimezone(TIMEZONE)
sunrise_tomorrow = sunrise_tomorrow_utc.astimezone(TIMEZONE)
sunset_tomorrow = sunset_tomorrow_utc.astimezone(TIMEZONE)

print('Sunrise today:', sunrise_today)
print('Sunset today:', sunset_today)
print('Sunrise tomorrow:', sunrise_tomorrow)
print('Sunset tomorrow:', sunset_tomorrow)

if now > sunrise_today:
    open_time = sunrise_tomorrow
else:
    open_time = sunrise_today

if now > sunset_today:
    close_time = sunset_tomorrow
else:
    close_time = sunset_today

print('Open time:', open_time)
print('Close time:', close_time)

client = SmartCoopClient(client_secret=OMLET_TOKEN)
omlet = Omlet(client)
device = omlet.get_device_by_id(DEVICE_ID)

configuration = device.configuration

configuration.door.openMode = 'time'
configuration.door.openTime = open_time.strftime('%H:%M')
configuration.door.closeMode = 'time'
configuration.door.closeTime = close_time.strftime('%H:%M')

omlet.update_configuration(device.deviceId, configuration)