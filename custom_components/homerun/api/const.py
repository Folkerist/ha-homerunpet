"""Constants of the homerunPET (霍曼宠物) cloud, taken from the Android app 3.6.7.

These are app constants shipped in every copy of the APK, not user secrets.
"""

from __future__ import annotations

# Legacy API: POST /app/v1/..., body {data, timestamp, sign}, header x-token.
BASE_URL_CN = "https://api.homerunsmart.com"
BASE_URLS = {
    "cn": BASE_URL_CN,
    "eu": "https://euapi.homerunsmart.com",
    "us": "https://usapi.homerunsmart.com",
    "sgp": "https://sgpapi.homerunsmart.com",
    "ind": "https://indapi.homerunsmart.com",
    "sa": "https://saapi.homerunsmart.com",
}

APP_SECRET = "8946644a4eb35e50f83f96dbb6403dab"  # Contacts.APP_SECRET, used as "appKey" in sign
APP_ID = "ddf3f28b7bda47bf83aafba9faf611bc"  # Contacts.appId, sent on login
APPLICATION_ID = "f73b2c3ca9031565e6d6b9337d762bd9"  # X-Application-Id header
APP_VERSION = "3.6.7"

# MD5Pwd(): MD5(PWD_KEY + password + PWD_SALT)[7:27]
PWD_KEY = "akbumgokcupum36vh0okfp7hkfz4m2m5"
PWD_SALT = "#q&8UT6eRV79ol4*"

CODE_OK = "200"
CODE_AUTH_INVALID = "4001"  # the app treats it as "session invalid / kicked" and logs out

# EZVIZ otap proxy (CS106 and other EZVIZ-module boxes).
OTAP_PROP = "/api/v3/device/otap/prop"
OTAP_ACTION = "/api/v3/device/otap/action"
CATEGORY_GLOBAL = "global"
DOMAIN_CUSTOM = "customDomain"

CATEG_LITTER_BOX = "CatLitterBox"

CLEAN_DELAY_RANGE = (1, 60)  # minutes, as the app's picker allows
