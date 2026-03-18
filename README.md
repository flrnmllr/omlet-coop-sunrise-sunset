# omlet-coop-sunrise-sunset

This python script calculates the sunrise and sunset times for given coordinates and updates the configuration of an Omlet Smart Automatic Chicken Coop Door.
The script is intended to be executed at least once daily to update the opening and closing times for the next open and close events, depending on the current time.
It can be used with Docker and scheduled to run regularly using a cron job, either by starting the container or by running the script directly.