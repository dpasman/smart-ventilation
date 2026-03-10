# Smart Ventilation

Smart Ventilation is a **Home Assistant custom integration** that helps determine **when to ventilate a room and when not to**.  
It takes into account:

- Indoor temperature and humidity (**required**)  
- Optional: Outdoor temperature and humidity  
- Optional: CO₂  
- Optional: PM2.5 (indoor and outdoor)  
- Optional: Wind  
- Optional: Heat index  

The integration calculates a **ventilation score (0–100)**, provides **advice**, and lists **reasons** for the recommendation.  
Each room can have its own configuration entry, making multi-room setups simple.

---

## 🧩 Features

- **Multi-room support:** One config entry per room.  
- **Flexible:** Works with only indoor sensors or enhanced with outdoor and air quality sensors.  
- **HACS-ready:** Can be installed easily via GitHub.  
- **Detailed attributes:** Advice and reasons are exposed for dashboards and automations.

---

## ⚙️ Installation

1. Place the folder `smart_ventilation` in `config/custom_components/`.  
2. Restart Home Assistant.  
3. Go to **Settings → Devices & Services → Add Integration → Smart Ventilation**.  
4. Configure the sensors for the room.

| Field | Required | Description |
|-------|----------|------------|
| **Room Name** | Yes | Name of the room, used for the sensor entity name |
| **Indoor Temperature** | Yes | Sensor for indoor temperature |
| **Indoor Humidity** | Yes | Sensor for indoor humidity |
| **Outdoor Temperature** | Optional | Sensor for outdoor temperature |
| **Outdoor Humidity** | Optional | Sensor for outdoor humidity |
| **CO₂** | Optional | Indoor CO₂ sensor |
| **PM2.5 Indoor** | Optional | Indoor PM2.5 sensor |
| **PM2.5 Outdoor** | Optional | Outdoor PM2.5 sensor |
| **Wind** | Optional | Wind speed sensor (m/s) |
| **Heat Index** | Optional | Indoor heat index sensor |

---

## 🛠️ Sensor Output

For each room, the integration creates **one main sensor**:

**Entity Example:** `sensor.smart_ventilation_score_kitchen`

### Attributes

- `advice`: Textual recommendation
  - `"Optimal"` – Best ventilation conditions  
  - `"Recommended"` – Ventilation suggested  
  - `"Neutral"` – Ventilation optional  
  - `"Not Recommended"` – Avoid ventilating  
- `reasons`: List of explanations for the recommendation, e.g.:  
  - `"High indoor humidity"`  
  - `"Humidity difference inside-outside: 3.5"`  
  - `"High CO2: 1200 ppm"`  
  - `"Outdoor PM2.5 high - ventilate less"`

---

## 📊 Example Automations

### 1️⃣ Notify when ventilation is recommended

```yaml
alias: "Notify Ventilation Recommended"
trigger:
  platform: state
  entity_id: sensor.smart_ventilation_score_kitchen
condition:
  condition: template
  value_template: "{{ states('sensor.smart_ventilation_score_kitchen') | float > 60 }}"
action:
  service: notify.mobile_app
  data:
    message: "Ventilation recommended in the kitchen. Score: {{ states('sensor.smart_ventilation_score_kitchen') }}"
```

### 2️⃣ Control a window actuator or fan

```yaml
alias: "Auto Ventilation Kitchen"
trigger:
  platform: state
  entity_id: sensor.smart_ventilation_score_kitchen
condition: []
action:
  service: switch.turn_on
  target:
    entity_id: switch.kitchen_window_fan
  when: "{{ states('sensor.smart_ventilation_score_kitchen') | float > 70 }}"
```

---

## 📝 Notes

- The integration works with **just indoor sensors**, but additional outdoor and air quality sensors improve accuracy.  
- Designed for **multiple rooms**; each room has its own config entry.  
- Can be extended with VOC, pollen, or other sensors easily.  
- Fully **HACS-ready** and supports UI configuration.  

---

## 📂 Repository Structure

smart_ventilation/
 ├── __init__.py
 ├── manifest.json
 ├── const.py
 ├── config_flow.py
 ├── sensor.py
 └── translations/
     └── en.json

