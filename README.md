# homerunPET for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/folkerist/ha-homerunpet/actions/workflows/validate.yml/badge.svg)](https://github.com/folkerist/ha-homerunpet/actions/workflows/validate.yml)

Unofficial Home Assistant integration for **homerunPET (霍曼宠物) self-cleaning litter boxes**
that use the EZVIZ Wi-Fi module, tested with the **CS106** on a Chinese-region account.
It talks to the vendor cloud the same way the phone app does. There is no local API on these boxes.

> **Not affiliated with, endorsed by or supported by Shenzhen Qianhai Homerun Smart Technology Co., Ltd.**
> It uses an undocumented API that can change or disappear at any time. Using it may break the
> app's terms of service; use it at your own risk.

[Русский — ниже](#по-русски)

## Features

| Entity | What it does |
|---|---|
| Number **Cleaning delay after the cat leaves** (1–60 min) | `AutoShovel.time` |
| Switches **Auto clean**, **Night mode**, **Auto litter refill**, **Auto cover**, **Kitten protection**, **Child lock** | box settings |
| Buttons **Clean now**, **Add litter** | the actions the app offers for these boxes |
| Sensors: activity, visits today, last visit, cat weight, visit duration, cleanings today, last cleaning, faults, firmware | |
| Binary sensors: online, waste bin full, litter reservoir low, drum litter low, problem | |
| Event **Cat visit** (time, weight, duration) | fired once per new visit, for automations |

Settings made of several fields (auto clean + delay, night mode + its window) are written
read-modify-write: the integration reads the current value from the box first and changes only
one field. If the read fails, nothing is written.

Polling: status, activity, containers, visits, cleanings and faults every minute
(about 7 requests per box); settings and firmware every 10 minutes and after each change.

## Login: reuse the app's token

The cloud keeps **one session per account**: a fresh login can log the phone app out (code `4001`),
and Chinese accounts log in with an SMS code. So by default the integration does **not** log in;
it reuses the token the app already has. Using the same token from Home Assistant was verified
not to log the phone out.

How to get the token, no root needed (the app writes its requests to the Android log):

1. Enable USB debugging on the phone, connect it to a computer with `adb`.
2. Open the homerunPET / 霍曼宠物 app and open the litter box page.
3. Run:
   ```sh
   adb logcat -d | grep -m1 -oE 'x-token: [^ ]+' | cut -d' ' -f2
   ```

Keep the token private: it gives full access to the account. If the cloud rejects it later,
Home Assistant asks for a new one (re-authentication); take it the same way.

A phone + password login exists for accounts that have a password, but it is off unless you tick
**"No token: log in with phone and password (risky)"**, because it may log the app out.

## Installation

HACS → ⋮ → **Custom repositories** → `https://github.com/folkerist/ha-homerunpet`, type
**Integration** → install **homerunPET** → restart Home Assistant →
**Settings → Devices & services → Add integration → homerunPET** → paste the token, pick the region
(China for 霍曼宠物 accounts).

Manual: copy `custom_components/homerun` into `<config>/custom_components/` and restart.

## Supported devices

Tested: **CS106** (model code `C5F40390`, EZVIZ module, Chinese cloud `api.homerunsmart.com`).
Other homerunPET litter boxes with the EZVIZ module (`C627DB69`, `C9EF47BB`, `C58BEDC0`, …) use the
same API and should work; the newer self-developed boxes (`A90152xx`, `B90152xx`, `A9012803`) use a
different API and are **not** supported yet. Other regions (EU, US, …) are selectable but untested.

Not exposed on purpose: open/reset the entrance, factory reset, reboot, and actions the CS106
rejects (`ManualLayingCatLitter`) or that need a camera module (`ManualAirClean`).

## How it works

- `POST https://api.homerunsmart.com/app/v1/...`, body `{"data": {...}, "timestamp": "<unix>", "sign": "<hex>"}`;
  `sign = sha256("k=v&" for data keys sorted descending + "appKey=<app secret>&timestamp=<ts>")`.
  Header `x-token` carries the token.
- Box properties and actions go through `POST /app/v1/devices/control`, which the cloud relays to
  the EZVIZ "otap" property/action API (`AutoShovel`, `LitterMargin`, `MachineTask`, `NightMode`,
  `ManualShovel`, `AutomaticSand`, …).
- The client (`custom_components/homerun/api/`) does not depend on Home Assistant and is tested
  against sanitised recorded cloud answers in `tests/`.

```sh
pip install aiohttp pytest pytest-asyncio && python -m pytest -q tests
```

---

## По-русски

Неофициальная интеграция для самоочищающихся лотков homerunPET (霍曼宠物) с модулем EZVIZ,
проверена на **CS106** с китайским аккаунтом. Работает через облако производителя, как приложение;
локального управления у этих лотков нет. С производителем никак не связана, API недокументирован
и может измениться; использование может нарушать пользовательское соглашение приложения.

**Вход.** Облако держит одну сессию на аккаунт: новый вход может выкинуть телефон из приложения,
а китайские аккаунты входят по SMS. Поэтому интеграция по умолчанию берёт токен приложения:
откройте приложение, подключите телефон с отладкой по USB и выполните
`adb logcat -d | grep -m1 -oE 'x-token: [^ ]+' | cut -d' ' -f2` (root не нужен). Проверено:
с этим токеном Home Assistant и телефон работают одновременно. Вход по паролю — только если явно
отметить «Нет токена: войти по телефону и паролю (рискованно)».

**Установка.** HACS → ⋮ → «Пользовательские репозитории» → `https://github.com/folkerist/ha-homerunpet`,
тип «Интеграция» → установить → перезапустить HA → «Настройки → Устройства и службы → Добавить
интеграцию → homerunPET» → вставить токен, регион «Китай».

**Что есть:** задержка уборки после ухода кошки (1–60 мин), автоуборка, ночной режим, автодосыпание,
автоприкапывание, защита котят и от детей; кнопки «Убрать сейчас» и «Досыпать наполнитель»; визиты,
вес кошки, уборки, ёмкости, ошибки, «в сети», прошивка; событие «Визит кошки» для автоматизаций.

## License

MIT
