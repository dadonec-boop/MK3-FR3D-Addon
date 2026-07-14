# Changelog — MK3 → MK3 + FR3D Addon

History of meaningful firmware changes relative to the original Desktop Filament Extruder **MK3** (Mackerel) baseline published as tag `v-mk3-original`.

## [v-mk3-fr3d] — 2026-07-14

### Identity / licensing header

- Firmware header notes **FR3D Addon** modifications by **Claudio Dadone** (14 Jul 2026), diameter measurement and predictive diameter control (manual/auto), and http://fr3d-addon.web.app/
- Firmware is prepared for optional remote control via Raspberry Pi Zero 2 W + web app; that host stack is **not** included in this public firmware repository

### Diameter measurement (Hall)

- Hall diameter sensing support (enable flag, ADC calibration points 1.70 / 1.75 / 1.80 mm, diameter offset)
- LCD helpers for capture / offset under AddonFR3D-related menus
- Default: Hall diameter **OFF** until calibrated/enabled
- Jump debounce / pending-match filtering for published diameter (CSV / predictor)

### Predictor (diameter control)

- Predictor model integrated in firmware (shared with host/app conventions)
- Modes:
  - **Predictor Auto Off** (`fr3d_pred_mode = 0`): computes / suggests, does **not** auto-apply E/T
  - **Predictor Auto On** (`fr3d_pred_mode = 1`): applies extruder RPM + temperature adjustments in firmware
- Main LCD menu: **Predictor Auto** On/Off toggle (full word “Predictor”)
- Status line mode indicator: `A` = Auto On, `-` = Auto Off
- **Predictor Parms** submenu under Settings (limits, deadband, target D, gains, Advanced)
- Advanced menu includes E/T margins, `|T−Ttgt| max`, settle, CSV cycle 5/10 s, median jump/conf, delta/gains, **DIAMDEBUG** at end (default OFF)

### Predictor defaults (when EEPROM has no FR3D values / `Config_ResetDefault`)

| Parameter | Default |
|-----------|---------|
| Predictor enabled (internal) | ON |
| Predictor Auto | OFF |
| Target D | 1.75 mm |
| Deadband/2 | 0.035 mm (3 decimals on LCD) |
| \|T−Ttgt\| max | 2 °C (integer edit) |
| Emin / Emax | 14 / 26 RPM |
| Tmin / Tmax | 173 / 182 °C |
| E margin / T margin | 2 / 2 (integers on LCD) |
| CSV cycle | 10 s |
| DIAMDEBUG | OFF |
| Hall diameter | OFF |
| Preheat Extruder | 150 °C |

### LCD / Settings UX

- Removed from Settings menu: **Filtra ok USB**, **Grabar settings**, **Cargar settings**
- USB “ok” filtering forced **always ON** (no user toggle; ignores turning it off via EEPROM/`MF`)
- Predictor mode selector removed from Settings (only on main menu as Auto On/Off)
- Fix: returning from Predictor Parms to Settings no longer shows a blank LCD until encoder move

### Host / USB / CSV

- Compact USB command set for predictor, diameter, materials/settings helpers (FR3D protocol)
- CSV telemetry cycle selectable 5 s / 10 s
- Optional DIAMDEBUG CSV diagnostics (default off)

### EEPROM

- Schema evolved through FR3D versions; current store/retrieve version **V28**
- Migration paths from known intermediate versions (V15–V27) where applicable
- Unknown / stock non-FR3D EEPROM → hardcoded defaults via `Config_ResetDefault()`

### Files added versus original MK3 (high level)

- `fr3d_telemetry.cpp` / `fr3d_telemetry.h`
- `fr3d_gateway_id.cpp` / `fr3d_gateway_id.h`
- Related hooks in `MK3_main.cpp`, `ultralcd.cpp`, `Configuration.h`, `ConfigurationStore.cpp`, `temperature.*`, etc.

---

## [v-mk3-original]

Unmodified **Desktop Filament Extruder MK3** firmware tree as archived locally (Mackerel / Marlin-based), without FR3D Addon features.
