# Smart Ventilation for Home Assistant

A Home Assistant integration that calculates ventilation efficiency based on indoor and outdoor environmental conditions. It provides recommendations on when it's optimal to ventilate your home.

## Features

- Calculates ventilation efficiency based on temperature, humidity, CO2, and PM2.5 levels
- Supports multiple areas/rooms
- Provides actionable advice for ventilation decisions
- Detects room type (kitchen, bathroom, bedroom, attic) for customized calculations
- Calculates temperature and humidity differences between indoor and outdoor

## Installation

### Via HACS (Recommended)

1. Open Home Assistant
2. Go to HACS > Integrations
3. Click the three dots (top right) > Custom repositories
4. Add `https://github.com/dpasman/smart-ventilation`
5. Search for "Smart Ventilation" and install

### Manual Installation

1. Copy the `custom_components/smart_ventilation` folder to your Home Assistant's `custom_components` folder
2. Restart Home Assistant

## Configuration

### Via UI

1. Go to Settings > Devices & Services
2. Click "Add Integration"
3. Search for "Smart Ventilation"
4. Follow the configuration steps

### Configuration Options

- **Outdoor Temperature**: Entity with outdoor temperature sensor (required)
- **Outdoor Absolute Humidity**: Entity with outdoor absolute humidity (required)
- **Outdoor Humidity**: Entity with outdoor relative humidity (optional)
- **Outdoor Dew Point**: Entity with outdoor dew point (optional)
- **Outdoor Max Temperature (24h)**: Entity with 24h maximum temperature (optional)
- **Wind Average**: Entity with average wind speed (optional)
- **Wind Maximum**: Entity with maximum wind speed (optional)

### Areas Configuration

For each area/room, you can configure:

- Area name
- Indoor temperature sensor
- Indoor humidity sensor
- Indoor absolute humidity sensor
- Indoor dew point sensor
- Indoor heat index sensor
- Indoor CO2 sensor
- Indoor PM2.5 sensor

## Entities

The integration creates the following entities for each configured area:

### Sensors

- **Ventilation Efficiency**: Percentage efficiency of ventilation (0-100%)
- **Ventilation Advice**: Human-readable recommendation
- **Humidity Difference**: Indoor - Outdoor absolute humidity
- **Temperature Difference**: Indoor - Outdoor temperature
- **Cooling Recommended**: Boolean indicating if cooling via ventilation is recommended

### Binary Sensors

- **Ventilation Reasons**: Multiple binary sensors for each factor affecting ventilation (temperature benefit, humidity benefit, etc.)

## Room Types

The integration automatically detects room types based on area names:

- **Kitchen**: Higher priority for humidity and CO2
- **Bathroom**: Highest priority for humidity
- **Bedroom**: Higher priority for CO2 levels
- **Attic**: Temperature-focused optimization

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Issues

If you encounter any issues, please report them at:
https://github.com/dpasman/smart-ventilation/issues
