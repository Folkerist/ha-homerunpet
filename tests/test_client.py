"""HomerunClient against recorded (sanitised) cloud answers."""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from api import (
    AutoClean,
    HomerunApiError,
    HomerunAuthError,
    HomerunClient,
    HomerunConnectionError,
    LitterMargin,
    NightMode,
)
from api.const import BASE_URL_CN
from api.signing import sign
from conftest import SERIAL, FakeSession, load

CONTROL = f"{BASE_URL_CN}/app/v1/devices/control"


def url(path: str) -> str:
    return BASE_URL_CN + path


@pytest.fixture
def m():
    return FakeSession()


@pytest.fixture
def client(m):
    return HomerunClient(m, "tok-123", client_device_id="dev")


async def test_request_is_signed_and_carries_token(client, m):
    m.add(url("/app/v1/devices/status"), {"code": "200", "data": {"status": 1}})
    assert await client.device_status(SERIAL) == 1
    [(body, headers)] = m.sent(url("/app/v1/devices/status"))
    assert body["data"] == {"deviceSerial": SERIAL}
    assert body["sign"] == sign(body["data"], body["timestamp"])
    assert headers["x-token"] == "tok-123"
    assert headers["X-Sign-Timestamp"] == body["timestamp"]


async def test_auth_error_on_4001(client, m):
    m.add(url("/app/v1/family/list"), {"code": "4001", "msg": "kicked"})
    with pytest.raises(HomerunAuthError):
        await client.families()


async def test_api_error_keeps_code(client, m):
    m.add(url("/app/v1/devicesMaintenance/list"), {"code": "4000", "msg": "bad"})
    with pytest.raises(HomerunApiError) as err:
        await client.request("/app/v1/devicesMaintenance/list", {"deviceSerial": SERIAL})
    assert err.value.code == "4000"


async def test_http_error_is_connection_error(client, m):
    m.add(url("/app/v1/family/list"), None, status=502)
    with pytest.raises(HomerunConnectionError):
        await client.families()


async def test_litter_boxes_from_families(client, m):
    m.add(url("/app/v1/family/list"), load("family_list"))
    m.add(url("/app/v1/devices/list"), load("devices_list"))
    boxes = await client.litter_boxes()
    [(body, _)] = m.sent(url("/app/v1/devices/list"))
    assert body["data"]["familyId"] == 1000001
    assert [b.serial for b in boxes] == [SERIAL]
    assert boxes[0].name == "Smart Litter Box CS1"
    assert boxes[0].status == 1


async def test_toilet_visits_and_cleanings(client, m):
    m.add(url("/app/v1/devicesToiletData/list"), load("toilet_list"))
    m.add(url("/app/v1/devicesCleanData/list"), load("clean_list"))
    visits = await client.toilet_visits(SERIAL, date(2026, 10, 5))
    cleans = await client.cleanings(SERIAL, date(2026, 10, 5))
    assert len(visits) == 6
    assert visits == sorted(visits, key=lambda v: v.time)
    assert visits[0].time == datetime(2026, 10, 5, 12, 10, 44)
    assert visits[0].weight_g == 3794
    assert visits[0].duration_s == 50
    assert cleans and cleans[0] == datetime(2026, 10, 5, 10, 50, 58)


async def test_faults_empty(client, m):
    m.add(url("/app/v1/devicesExceptionStatus/list"), load("exceptions"))
    assert await client.faults(SERIAL) == []


async def test_get_prop_goes_through_otap_proxy(client, m):
    m.add(CONTROL, load("prop_AutoShovel"))
    raw = await client.get_prop(SERIAL, "AutoShovel")
    [(body, _)] = m.sent(CONTROL)
    assert AutoClean.from_api(raw) == AutoClean(enabled=True, delay_min=5)
    data = body["data"]
    assert data["url"] == "/api/v3/device/otap/prop"
    assert data["method"] == "GET"
    assert data["body"] == "{}"
    assert json.loads(data["headers"]) == {
        "Content-Type": "application/json",
        "deviceSerial": SERIAL,
        "localIndex": 0,
        "resourceCategory": "global",
        "domainIdentifier": "customDomain",
        "propIdentifier": "AutoShovel",
    }
    # The headers value is a JSON string and is signed as-is.
    assert body["sign"] == sign(data, body["timestamp"])


async def test_set_clean_delay_payload(client, m):
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 200}, "data": None}})
    await client.set_prop(SERIAL, "AutoShovel", AutoClean(True, 15).to_api())
    [(body, _)] = m.sent(CONTROL)
    assert body["data"]["method"] == "PUT"
    assert json.loads(body["data"]["body"]) == {"Switch": True, "time": 15}


async def test_otap_meta_error_raises(client, m):
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 2003, "message": "offline"}}})
    with pytest.raises(HomerunApiError) as err:
        await client.get_prop(SERIAL, "AutoShovel")
    assert err.value.code == "2003"


async def test_clean_now_action(client, m):
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 200}}})
    await client.clean_now(SERIAL)
    [(body, _)] = m.sent(CONTROL)
    data = body["data"]
    assert data["url"] == "/api/v3/device/otap/action"
    assert json.loads(data["headers"])["actionIdentifier"] == "ManualShovel"
    # Same as the app: JSONObject({"value": null}).toString()
    assert data["body"] == '{"value":null}'


async def test_refill_portions_validated(client):
    with pytest.raises(ValueError):
        await client.refill_litter(SERIAL, 4)


def test_models_from_fixtures():
    margin = LitterMargin.from_api(load("prop_LitterMargin")["data"]["data"])
    assert margin == LitterMargin(refill_bucket_ok=True, drum_litter_ok=True, waste_bin_ok=False)
    night = NightMode.from_api(load("prop_NightMode")["data"]["data"])
    assert night == NightMode(enabled=False, start_s=79200, end_s=28800)
    assert night.to_api() == {"Switch": False, "StartTimeInt": 79200, "EndTimeInt": 28800}
    assert AutoClean.from_api(None) is None


async def test_level_and_refill_send_bare_values(client, m):
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 200}}})
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 200}}})
    await client.level_litter(SERIAL)
    await client.refill_litter(SERIAL, 2)
    level, refill = (body["data"] for body, _ in m.sent(CONTROL))
    assert json.loads(level["headers"])["actionIdentifier"] == "ManualLayingCatLitter"
    assert level["body"] == "1"
    assert json.loads(refill["headers"])["actionIdentifier"] == "AutomaticSand"
    assert refill["body"] == "2"


async def test_set_delay_keeps_switch_as_on_the_box(client, m):
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 200}, "data": {"Switch": False, "time": 5}}})
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 200}}})
    new = await client.update_auto_clean(SERIAL, delay_min=15)
    read, write = (body["data"] for body, _ in m.sent(CONTROL))
    assert read["method"] == "GET"
    assert write["method"] == "PUT"
    assert json.loads(write["body"]) == {"Switch": False, "time": 15}
    assert new == AutoClean(enabled=False, delay_min=15)


async def test_toggle_auto_clean_keeps_delay(client, m):
    m.add(CONTROL, load("prop_AutoShovel"))  # {"Switch": true, "time": 5}
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 200}}})
    await client.update_auto_clean(SERIAL, enabled=False)
    _, write = (body["data"] for body, _ in m.sent(CONTROL))
    assert json.loads(write["body"]) == {"Switch": False, "time": 5}


async def test_no_write_when_current_value_unreadable(client, m):
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 2003, "message": "offline"}}})
    with pytest.raises(HomerunApiError):
        await client.update_auto_clean(SERIAL, delay_min=10)
    assert len(m.sent(CONTROL)) == 1  # only the read, no PUT


async def test_delay_out_of_range_rejected_before_any_request(client, m):
    with pytest.raises(ValueError):
        await client.update_auto_clean(SERIAL, delay_min=0)
    assert m.calls == []


async def test_night_mode_keeps_window(client, m):
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 200}, "data": {"Switch": False, "StartTimeInt": 3600, "EndTimeInt": 7200}}})
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 200}}})
    await client.update_night_mode(SERIAL, enabled=True)
    _, write = (body["data"] for body, _ in m.sent(CONTROL))
    assert json.loads(write["body"]) == {"Switch": True, "StartTimeInt": 3600, "EndTimeInt": 7200}


async def test_bool_prop_written_as_json_bool(client, m):
    m.add(CONTROL, {"code": "200", "data": {"meta": {"code": 200}}})
    await client.set_prop(SERIAL, "ChildLock", True)
    [(body, _)] = m.sent(CONTROL)
    assert body["data"]["body"] == "true"  # the app: Switch + ""


def test_parse_bool_and_robust_models():
    from api.models import parse_bool

    assert parse_bool("false") is False
    assert parse_bool("true") is True
    assert parse_bool(0) is False
    with pytest.raises(ValueError):
        parse_bool("maybe")
    assert AutoClean.from_api({"Switch": "false", "time": "7"}) == AutoClean(False, 7)
    assert AutoClean.from_api({"Switch": True}) is None  # no delay: do not guess
    assert LitterMargin.from_api({"Dustbin": "false"}).waste_bin_ok is False
    from api.models import ToiletVisit

    v = ToiletVisit.from_api({"dateTime": "2026-10-05 12:00:00", "weight": "x", "duration": None})
    assert v is not None and v.weight_g is None
