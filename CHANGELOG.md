# Changelog — MK3 → MK3 + FR3D Addon

History of meaningful firmware changes relative to the original Desktop Filament Extruder **MK3** (Mackerel) baseline published as tag `v-mk3-original`.

## [gateway-v2.4.12] — 2026-08-17

### Gateway program (Pi OTA)

- Release tag [`gateway-v2.4.12`](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/tag/gateway-v2.4.12): Pi OTA zip (Windows zip unchanged vs 2.4.11)
- Manual Ø no longer overwritten by a stale 1.75 mm inject tick when idle
- Diameter bar scale follows predictor target (−0.15 / +0.25); live Ø is shown on the thumb
- Update Pi with CONSOLE `PI UPDATE GATEWAY latest` (does not replace the SD factory image)

## [gateway-v2.4.11] — 2026-08-16

### Gateway program (Pi OTA + Windows)

- Release tag [`gateway-v2.4.11`](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/tag/gateway-v2.4.11): Pi OTA zip, Windows x64 zip, MK3 firmware zip
- Web app 2.0.31: pairing/login opens the FR3dAddon product-family WIKI; pairing can return to sign-in without a token
- Update Pi with CONSOLE `PI UPDATE GATEWAY latest` (does not replace the SD factory image)

## [gateway-v2.4.10] — 2026-08-15

### Gateway program (Pi OTA + Windows)

- Release tag [`gateway-v2.4.10`](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/tag/gateway-v2.4.10): Pi OTA zip, Windows x64 zip, MK3 firmware zip
- Older MK3 firmware stays usable: Analog A3, extrusion, winder and predictor Auto
- USB/Manual, Optimizar and P* only if MK3 QUERY reports `DIAMSRC` / `PREDOPT` / `PREDPSTAR`
- Update Pi with CONSOLE `PI UPDATE GATEWAY latest` (does not replace the SD factory image)

## [gateway-v2.4.9] — 2026-08-15

### Gateway program (Pi OTA + Windows)

- Release tag [`gateway-v2.4.9`](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/tag/gateway-v2.4.9): Pi OTA zip, Windows x64 zip, MK3 firmware zip
- Aligns with MK3 **Optimizar P\*** (E+T, puller stays Auto)
- Same web app for **internet** and **LAN / WiFi** (with or without internet)
- Update Pi with CONSOLE `PI UPDATE GATEWAY latest` (does not replace the SD factory image)

## [v-mk3-fr3d] — 2026-08-15

### Predictor Optimizar P*

- **Optimizar** drives **P\*** by acting on **E+T**; puller stays in **Auto** (never writes P Manual)
- Soft Ø band slack while optimizing; E→P health uses a longer persist window
- `dist/MK3-FR3D-Addon.zip` refreshed (15 Aug 2026). **Reflash the MK3 board** to use this Optimizar behaviour.

## [v-mk3-fr3d] — 2026-08-13

### Diameter sensor sources (exclusive)

- `DIAMSRC` / LCD **Source**: **Analog A3** XOR **Digital USB (BDWidth host)** XOR **Manual (mock)**
- Manual Ø from LCD (`D mm`) or host; QUERY reports source for web CONFIG / predictor
- Older boards without `DIAMSRC` keep Analog A3 only
- `dist/MK3-FR3D-Addon.zip` refreshed (13 Aug 2026). **Reflash the MK3 board** to use USB/Manual sources.

## [gateway-v2.4.1] — 2026-08-13

### Gateway program (Pi OTA + Windows)

- Release tag [`gateway-v2.4.1`](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/tag/gateway-v2.4.1): Pi OTA zip, Windows x64 zip, MK3 firmware zip
- Pi: LAN Flutter UI + local `/api` alongside Firebase; BDWidth USB path; reject USB/Manual on legacy MK3
- Update Pi with CONSOLE `PI UPDATE GATEWAY latest` (does not replace the SD factory image)

## [v-mk3-fr3d] — 2026-08-04

### Predictor UI / Hall diameter

- LCD / host state tokens: `SIN A`, `A`, `AH`, `AB`, `AS`, `AC`, `AO`, `AG`, `AN`, `AE±`, `AT±` (`PREDUI` in QUERY)
- `AC` = calibration invalid (`CALV=0`); `AO` = Hall off (`DH=0`) — no longer shared as one code
- Hall diameter path **always ON** (`DH=1` default; `DH0` ignored; EEPROM load forces ON)
- QUERY reports real `DH`; `CALV1` reactivates saved cal and enables Hall
- `dist/MK3-FR3D-Addon.zip` refreshed (4 Aug 2026)

## [pi-gateway-v0.8] — 2026-08-13

### Pi Zero 2 W factory image (Release asset)

- Published [`fr3daddon-v0.8-small.img.zst`](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/download/pi-gateway-v0.8/fr3daddon-v0.8-small.img.zst)
- Includes gateway **2.4.1**: LAN Flutter UI (nginx), BDWidth USB path, DIAMSRC sensor modes support
- Release notes: [`pi-gateway-v0.8`](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/tag/pi-gateway-v0.8)

## [pi-gateway-v0.7] — 2026-08-04

### Pi Zero 2 W factory image (Release asset)

- Published [`fr3daddon-v0.7-small.img.zst`](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/download/pi-gateway-v0.7/fr3daddon-v0.7-small.img.zst)
- Release notes: [`pi-gateway-v0.7`](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/tag/pi-gateway-v0.7)

## [v-mk3-fr3d] — 2026-07-31

### Serial temperature limit (host `T` / `RTFP`)

- Replaced the fixed USB serial ceiling (**190 °C**, later briefly **210**) with a **dynamic** cap driven by predictor **Tmax**:
  - `serial_T_max = max(190, predictor_Tmax + 5)`
  - hard safety clamp: `HEATER_0_MAXTEMP − 15` (~260 °C)
- Raising **Tmax** in Predictor Parms / `PREDTRNG` (LCD or web app) therefore raises the allowed host setpoint automatically (e.g. Tmax **194** → serial up to **199 °C**; PETG Tmax **250** → up to **255 °C** within heater margin).
- Compact HELP text for `T` updated to `0..(Tmax pred+5)`.
- `dist/MK3-FR3D-Addon.zip` refreshed (31 Jul 2026). **Reflash the MK3 board** to apply.

## [pi-gateway-v0.5] — 2026-07-25

### Pi Zero 2 W factory image (Release asset)

- Published [`fr3daddon-v0.5-small.img.zst`](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/download/pi-gateway-v0.5/fr3daddon-v0.5-small.img.zst)
- Release notes: [`pi-gateway-v0.5`](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/tag/pi-gateway-v0.5)
- Image includes gateway program **2.0.3** with OTA (`PI UPDATE GATEWAY latest`)

## [v-mk3-fr3d] — 2026-07-23

### Predictor / host USB

- Internal fusion cycle fixed at **2 s** (LCD selector 5/10 s removed; legacy values coerced to 2 s)
- USB CSV emission **on demand** (`CSVQ`); no periodic CSV push over USB
- **T settle** clamped to **15–20** fusions (default 15)
- Transport **hold** after E/T corrective: hold meters + timeout (`PREDHOLDM` / `PREDHOLDT`, LCD Advanced)
- EEPROM schema **V30** (migrate V29 → V30 for hold m/timeout; V28 and earlier paths retained)
- `dist/MK3-FR3D-Addon.zip` refreshed (23 Jul 2026)

## [v-mk3-fr3d] — 2026-07-21

### Diameter sensor (LCD / Pattern Diameter)

- Menu **Control → AddonFR3D → Diameter Sensor**
- **Pattern Diameter**: shows **Now** (active mm preset) and **Set** for the *other* preset only
  - Wide preset **1.5 / 1.7 / 2.0** mm
  - Standard preset **1.7 / 1.75 / 1.8** mm
- Changing pattern: invalidates calibration (`CALV=0`), clears capture mask/ADC points, and resets **Offset (DOFF) to 0**
- After **Set**: confirm screen → first Capture; **Need Calibrate!** when `CALV=0`; **CALIBRATE** when `CALV=1`
- User guide PDF and `dist/MK3-FR3D-Addon.zip` refreshed (21 Jul 2026)
- Printable INFIDEL-style Hall parts: [`docs/diameter_sensor_infidel/`](docs/diameter_sensor_infidel/)

## [v-mk3-fr3d] — 2026-07-14

### Identity / licensing header

- Firmware header notes **FR3D Addon** modifications by **Claudio Dadone** (14 Jul 2026), diameter measurement and predictive diameter control (manual/auto), and http://fr3d-addon.web.app/
- Firmware is prepared for optional remote control via Raspberry Pi Zero 2 W + web app; that host stack is **not** included in this public firmware repository

### Diameter measurement (Hall)

- Hall diameter sensing support (enable flag, ADC calibration points, diameter offset)
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
