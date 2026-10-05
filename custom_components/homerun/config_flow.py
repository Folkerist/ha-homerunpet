"""Config flow. Default path: paste the token the app already uses (no new login).

A fresh password login can end the app's session on the phone, and the account
may be tied to a phone number that cannot receive a new SMS. So it is opt-in:
the user has to tick allow_password_login.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HomerunAuthError, HomerunClient, HomerunError
from .api.client import _client_device_id
from .api.const import BASE_URLS
from .const import (
    CONF_ALLOW_PASSWORD_LOGIN,
    CONF_AREA_CODE,
    CONF_CLIENT_DEVICE_ID,
    CONF_PASSWORD,
    CONF_PHONE,
    CONF_REGION,
    CONF_TOKEN,
    DEFAULT_REGION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

REGION_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=list(BASE_URLS), translation_key="region", mode=selector.SelectSelectorMode.DROPDOWN
    )
)
PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


class HomerunConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._region = DEFAULT_REGION
        self._device_id = _client_device_id()

    def _client(self, token: str | None) -> HomerunClient:
        return HomerunClient(
            async_get_clientsession(self.hass),
            token,
            base_url=BASE_URLS[self._region],
            time_zone=str(self.hass.config.time_zone),
            client_device_id=self._device_id,
        )

    async def _validate(self, token: str) -> tuple[str | None, str | None]:
        """Return (unique_id, error)."""
        client = self._client(token)
        try:
            families = await client.families()
            boxes = await client.litter_boxes(families)
        except HomerunAuthError:
            return None, "invalid_auth"
        except HomerunError as err:
            _LOGGER.debug("homerun validation failed: %s", err)
            return None, "cannot_connect"
        if not boxes:
            return None, "no_devices"
        ids = [f["id"] for f in families if f.get("id") is not None]
        if not ids:
            return None, "no_devices"
        return f"family_{min(ids)}", None

    async def _finish(self, unique_id: str, token: str) -> ConfigFlowResult:
        await self.async_set_unique_id(unique_id)
        data = {CONF_TOKEN: token, CONF_REGION: self._region, CONF_CLIENT_DEVICE_ID: self._device_id}
        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(self._get_reauth_entry(), data_updates=data)
        # Adding the same account again just refreshes its token.
        self._abort_if_unique_id_configured(updates={CONF_TOKEN: token})
        return self.async_create_entry(title="homerunPET", data=data)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._region = user_input[CONF_REGION]
            token = (user_input.get(CONF_TOKEN) or "").strip()
            if token:
                unique_id, error = await self._validate(token)
                if error is None:
                    return await self._finish(unique_id, token)
                errors["base"] = error
            elif user_input.get(CONF_ALLOW_PASSWORD_LOGIN):
                return await self.async_step_password()
            else:
                errors["base"] = "token_required"

        schema = vol.Schema(
            {
                vol.Optional(CONF_TOKEN): PASSWORD_SELECTOR,
                vol.Required(CONF_REGION, default=self._region): REGION_SELECTOR,
                vol.Required(CONF_ALLOW_PASSWORD_LOGIN, default=False): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_password(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Opt-in fresh login. May log the phone out of the app."""
        errors: dict[str, str] = {}
        if user_input is not None and CONF_PHONE in user_input:
            client = self._client(None)
            try:
                token = await client.login_password(
                    phone=user_input[CONF_PHONE].strip(),
                    password=user_input[CONF_PASSWORD],
                    area_code=user_input[CONF_AREA_CODE].strip().lstrip("+"),
                    country_code=self._region.upper(),
                )
            except HomerunAuthError:
                errors["base"] = "invalid_auth"
            except HomerunError as err:
                _LOGGER.debug("homerun login failed: %s", err)
                errors["base"] = "cannot_connect"
            else:
                unique_id, error = await self._validate(token)
                if error is None:
                    return await self._finish(unique_id, token)
                errors["base"] = error

        schema = vol.Schema(
            {
                vol.Required(CONF_AREA_CODE, default="86"): str,
                vol.Required(CONF_PHONE): str,
                vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR,
            }
        )
        return self.async_show_form(step_id="password", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        self._region = entry_data.get(CONF_REGION, DEFAULT_REGION)
        self._device_id = entry_data.get(CONF_CLIENT_DEVICE_ID) or self._device_id
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_TOKEN].strip()
            unique_id, error = await self._validate(token)
            if error is None:
                return await self._finish(unique_id, token)
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_TOKEN): PASSWORD_SELECTOR}),
            errors=errors,
        )
