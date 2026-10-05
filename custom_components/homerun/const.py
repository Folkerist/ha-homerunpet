"""Constants of the homerunPET integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "homerun"
MANUFACTURER = "homerunPET"

CONF_TOKEN = "token"
CONF_REGION = "region"
CONF_ALLOW_PASSWORD_LOGIN = "allow_password_login"
CONF_PHONE = "phone"
CONF_AREA_CODE = "area_code"
CONF_PASSWORD = "password"
CONF_CLIENT_DEVICE_ID = "client_device_id"

DEFAULT_REGION = "cn"

# Each refresh is ~7 requests per box: status, MachineTask, LitterMargin, visits,
# cleanings, faults. Settings (6 more props + firmware) are read every SETTINGS_EVERY.
SCAN_INTERVAL = timedelta(seconds=60)
SETTINGS_EVERY = timedelta(minutes=10)

CLEAN_DELAY_MIN = 1
CLEAN_DELAY_MAX = 60

EVENT_CAT_VISIT = "cat_visit"
