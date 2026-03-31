# Smart Ventilation

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/v/release/dpasman/smart-ventilation)](https://github.com/dpasman/smart-ventilation/releases)
[![GitHub license](https://img.shields.io/github/license/dpasman/smart-ventilation)](https://github.com/dpasman/smart-ventilation/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/dpasman/smart-ventilation)](https://github.com/dpasman/smart-ventilation/issues)

Smart Ventilation is a Home Assistant integration that tells you when and where to open your windows. It compares indoor and outdoor conditions across multiple rooms and calculates a ventilation efficiency score per area. Instead of guessing, you get a clear recommendation based on temperature, humidity, CO2, and air quality data from your existing sensors.

## Features

- Calculates a ventilation efficiency score (0-100%) for each room
- Provides a plain-language advice level: Optimal, Recommended, Decent, Neutral, or Not Recommended
- Detects room type from the area name for room-specific logic (kitchen, bathroom, bedroom, attic)
- Shows indoor vs outdoor humidity and temperature differences
- Separate cooling recommendation for hot days when outside air is cooler
- Supports multiple areas with independent calculations
- Fully configured through the UI, no YAML required

## Installation

### Via HACS (recommended)

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

## Entities

For each configured area, the integration creates:

| Entity | Type | Description |
|---|---|---|
| Ventilation Efficiency | Sensor | Score from 0 to 100% |
| Ventilation Advice | Sensor | Optimal / Recommended / Decent / Neutral / Not Recommended |
| Humidity Difference | Sensor | Indoor minus outdoor absolute humidity (g/m³) |
| Temperature Difference | Sensor | Indoor minus outdoor temperature (°C) |
| Cooling by Ventilation Recommended | Binary Sensor | True when outside air is meaningfully cooler than inside |

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
