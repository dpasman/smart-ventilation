# Smart Ventilation

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![CI](https://github.com/dpasman/smart-ventilation/actions/workflows/ci.yml/badge.svg)](https://github.com/dpasman/smart-ventilation/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/dpasman/smart-ventilation)](https://github.com/dpasman/smart-ventilation/releases)
[![GitHub license](https://img.shields.io/github/license/dpasman/smart-ventilation)](https://github.com/dpasman/smart-ventilation/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/dpasman/smart-ventilation)](https://github.com/dpasman/smart-ventilation/issues)

Smart Ventilation is a Home Assistant integration that tells you when and where to open your windows — and, optionally, can act on that advice itself. It compares indoor and outdoor conditions across multiple rooms, factors in current and near-term weather, and calculates a ventilation efficiency score per area. Instead of guessing, you get a clear recommendation based on temperature, humidity, CO2, air quality, and weather data from your existing sensors.

## Features

- Calculates a ventilation efficiency score (0-100%) for each room
- Provides a plain-language advice level: Optimal, Recommended, Decent, Neutral, or Not Recommended
- Derives an OPEN / CLOSE / VENTILATE BRIEFLY / NO ACTION recommendation per room
- Detects room type from the area name for room-specific logic (kitchen, bathroom, bedroom, attic)
- Shows indoor vs outdoor humidity and temperature differences
- Separate cooling recommendation for hot days when outside air is cooler
- Optional weather entity integration: blocks/derates advice on thunderstorms, heavy rain, snow, fog, or strong wind, and looks ahead at the near-term forecast
- Optional actuation: trigger an automation to open/close, with safety guardrails (hold/lockout) and an optional Companion App confirmation step before anything happens
- Notifications with quiet hours, a cooldown between repeats, and severity-aware dedup (so an escalation still gets through)
- Live-tunable settings (quiet hours, cooldown, notifications on/off, confirmation-required) as regular HA entities — no need to reopen the integration's settings for routine tweaks
- Supports multiple areas with independent calculations
- Fully configured through the UI, no YAML required
- Dutch and English translations

## Installation

### Via HACS (recommended)

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=dpasman&repository=smart-ventilation&category=integration)

Click the button above, or add it manually:

1. Open HACS in Home Assistant
2. Go to Integrations
3. Click the three dots in the top right and choose Custom repositories
4. Add `https://github.com/dpasman/smart-ventilation` with category Integration
5. Search for Smart Ventilation and install it
6. Restart Home Assistant

### Manual

1. Copy the `custom_components/smart_ventilation` folder into your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Setup

Go to Settings > Devices & Services, click Add Integration, and search for Smart Ventilation.

The first step asks for your outdoor sensors. Only outdoor temperature and outdoor absolute humidity are required. The rest are optional but improve the recommendations.

| Field | Required | Notes |
|---|---|---|
| Outdoor Temperature | Yes | |
| Outdoor Absolute Humidity | Yes | |
| Outdoor Relative Humidity | No | |
| Outdoor Dew Point | No | Used to prevent condensation |
| Outdoor Max Temperature 24h | No | Improves cold weather logic |
| Wind Average | No | |
| Wind Maximum | No | |

After saving, open the integration options to add your first area. Select a Home Assistant area from the list, then assign the sensors for that room. You can add as many areas as you like.

| Field | Required |
|---|---|
| Indoor Temperature | Yes |
| Indoor Humidity | Yes |
| Indoor Absolute Humidity | No |
| Indoor Dew Point | No |
| Indoor Heat Index | No |
| Indoor CO2 | No |
| Indoor PM2.5 | No |
| Open Automation | No | Triggered for an accepted OPEN action, see [Actions & Actuation](#actions--actuation) |
| Close Automation | No | Triggered for an accepted CLOSE action |
| Window Sensors | No | Skip re-triggering if a window is already in the target state |
| Action Hold / Action Lockout | No | Safety guardrails, see below |
| Require Confirmation Before Acting | No | Default on — ask via the Companion App before actuating |

An area with none of the actuation fields configured behaves exactly as
before: advisory-only, no automation ever triggered.

A separate "Global Settings" entry in the options menu covers the
weather entity, notification devices, quiet hours, cooldown/stability
windows, season bias, and debug mode — see the sections below.

## Entities

For each configured area, the integration creates:

| Entity | Type | Description |
|---|---|---|
| Ventilation Efficiency | Sensor | Score from 0 to 100% |
| Ventilation Advice | Sensor | Optimal / Recommended / Decent / Neutral / Not Recommended |
| Humidity Difference | Sensor | Indoor minus outdoor absolute humidity (g/m³) |
| Temperature Difference | Sensor | Indoor minus outdoor temperature (°C) |
| Ventilation Action | Sensor | OPEN / CLOSE / VENTILATE briefly / NO ACTION |
| Cooling by Ventilation Recommended | Binary Sensor | True when outside air is meaningfully cooler than inside |
| Require Confirmation Before Acting | Switch | Per-area, live-toggleable copy of the options-flow field |
| Send Recommendation Now | Button | Sends this area's current recommendation immediately, bypassing quiet hours/cooldown/stability — see below |

Global (not per-area) entities:

| Entity | Type | Description |
|---|---|---|
| Notification Cooldown | Number | Minutes before re-notifying the same area for the same reason |
| Notification Stability Window | Number | Minutes a recommendation must hold before it's acted on |
| Quiet Hours Start / End | Time | — |
| Notifications Enabled | Switch | — |
| Quiet Hours Enabled | Switch | — |
| Debug Mode | Switch | — |

## Weather & Forecast

Optionally set a `weather.*` entity under Global Settings. Its current
condition and a near-term (~2 hour) forecast lookahead are factored into
every area's score:

- **Blocking** conditions (thunderstorm, hail, or a high near-term
  precipitation/wind probability) cap the efficiency score low and become
  the top-priority reason shown, right alongside the existing strong-wind
  check.
- **Caution** conditions (rain, snow, fog, moderate wind) apply a smaller
  penalty and surface only as a fallback reason when nothing more specific
  applies.

Hourly forecast support varies by weather integration — if yours doesn't
expose it, Smart Ventilation falls back to the current condition only.

## Actions & Actuation

Each area now also derives an action — **OPEN**, **CLOSE**, **VENTILATE
BRIEFLY**, or **NO ACTION** — from its efficiency score, with safety
conditions (storm, adverse weather, condensation risk, dangerous CO2)
always taking priority over the score-based tier.

If you configure an **Open Automation** and/or **Close Automation** for an
area, Smart Ventilation can trigger them automatically:

- **Safety guardrails**: a changed action must hold stable for the
  configured **Action Hold** (default 5 min) before it's accepted, and
  once accepted it's locked in for the **Action Lockout** (default
  20 min) before a *different* action is even reconsidered — sensor noise
  can't flap your windows open and shut. A safety-critical action (storm,
  adverse weather, condensation, dangerous CO2) bypasses both immediately.
- **Idempotency**: if you configure **Window Sensors** for the area, an
  already-open window is never re-triggered to open again (and vice versa
  for close).
- **Confirmation**: with **Require Confirmation Before Acting** on
  (the default), nothing is triggered until you tap Confirm on an
  actionable Companion App notification — a safety-critical action skips
  this and acts immediately. An unanswered confirmation expires after
  15 minutes and is treated as a decline, never as a go-ahead.

An area with no automations configured stays exactly as advisory-only as
it always was — this is entirely opt-in.

## Notifications & Quiet Hours

Notifications are gated separately from actuation: **Quiet Hours**
suppress them (a safety-critical action still gets through), a
**Notification Cooldown** avoids repeating the same reason too often, and
a **Notification Stability Window** means a recommendation must hold
before it's worth notifying about at all. A severity escalation (e.g. CO2
climbing into the dangerous range) bypasses the cooldown so it's never
silently missed.

The per-area **Send Recommendation Now** button bypasses the stability
window, cooldown, and quiet hours — an explicit request shouldn't wait —
but any resulting actuation still goes through the normal hold/lockout and
confirmation-required checks above; this button cuts notification noise,
not safety checks.

If an area is configured to require confirmation but no notification
device is set under Global Settings, that confirmation can never be
delivered and the area would silently never act — Smart Ventilation
raises a persistent Home Assistant notification telling you so, rather
than failing silently.

**Notification Language** (English/Dutch, under Global Settings) controls
the language of the push notifications and confirmation requests
themselves — independent of the language your Home Assistant profile is
set to. Entity names and states on the dashboard still follow your HA
profile language as usual; this setting only affects the text actually
sent to your phone.

## Room types

The integration reads the area name to determine room type and adjusts the scoring accordingly:

- **Kitchen**: Prioritizes humidity and CO2
- **Bathroom**: Aggressive humidity reduction, post-shower detection
- **Bedroom**: CO2 is the dominant factor
- **Attic**: Focuses on temperature cooling, ignores humidity

Any area that does not match a known keyword uses the generic scoring logic.

## Issues and contributions

Bug reports and pull requests are welcome at [github.com/dpasman/smart-ventilation](https://github.com/dpasman/smart-ventilation/issues).

## Changelog

Version history is tracked via [GitHub releases](https://github.com/dpasman/smart-ventilation/releases). The current version is also reflected in `custom_components/smart_ventilation/manifest.json`.
