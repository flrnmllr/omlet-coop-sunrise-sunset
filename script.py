import os
import datetime
from dateutil import tz
from suntime import Sun
from smartcoop.client import SmartCoopClient
from smartcoop.api.omlet import Omlet

latitude = 51.4263901
longitude = 7.0781257

sun = Sun(latitude, longitude)

timezone = tz.gettz('Europe/Berlin')
sunrise_time = sun.get_sunrise_time().astimezone(timezone)
sunset_time = sun.get_sunset_time().astimezone(timezone)

client = SmartCoopClient(client_secret=os.environ.get('OMLET_API_TOKEN'))
omlet = Omlet(client)
device = omlet.get_device_by_id(os.environ.get('OMLET_DEVICE_ID'))

configuration = device.configuration
configuration.door.openMode = 'time'
configuration.door.openTime = sunrise_time.strftime('%H:%M')
configuration.door.closeMode = 'time'
configuration.door.closeTime = sunset_time.strftime('%H:%M')

omlet.update_configuration(device.deviceId, configuration)