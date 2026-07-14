# MK3 + FR3D Addon

Public firmware for the **Desktop Filament Extruder MK3**, with **FR3D Addon** modifications by **Claudio Dadone**.

Based on **MACKEREL** (Marlin-derived filament extruder firmware by Filip Mulier / Hugh Lyman).

**Reference web app:** [http://fr3d-addon.web.app/](http://fr3d-addon.web.app/)

---

## What this repository contains

| Content | Description |
|---------|-------------|
| `MK3/` | Firmware sources (Arduino / Mega — flash this folder) |
| Tag `v-mk3-original` | Stock MK3 (Mackerel base), **without** FR3D Addon |
| Tag `v-mk3-fr3d` / branch `main` | Latest **MK3 + FR3D Addon** |

This repository publishes **MK3 board firmware only**.

It does **not** include the Raspberry Pi gateway, Python host tools, or the web application.

---

## What FR3D Addon adds to the firmware

Compared with original MK3, this firmware includes:

- Diameter measurement (Hall sensor) and LCD calibration helpers
- Diameter **predictor** with **Auto On / Off** (automatic E/T apply vs suggest-only)
- Predictor parameter menus (basic + Advanced)
- Compact USB host commands and CSV telemetry (5/10 s cycle)
- Extended EEPROM layout for FR3D settings (current schema **V28**)

See [CHANGELOG.md](CHANGELOG.md) for the full list of changes versus original MK3.

---

## Internet control (MK3s + FR3D Addon)

This firmware is **prepared** for remote control when used with the **MK3s + FR3D Addon** product stack:

- A **Raspberry Pi Zero 2 W** acts as a gateway between the MK3 (USB/serial) and the Internet
- A **web application** is used to configure and control the machine
- Operational reference: [http://fr3d-addon.web.app/](http://fr3d-addon.web.app/)

That layer (Pi gateway, host/backend, and web app) is an **additional product feature**.  
It is **not included in this repository** and is **not published here under an open-source / public license**.

What *is* public and licensed under **GPL-3.0** in this repo is the **modified MK3 firmware (FR3D Addon)** — ready to flash, and optionally integrable with your own host using the firmware’s USB/CSV protocol.

---

## How to flash

1. Install Arduino IDE (or a compatible toolchain for AVR Mega 2560 / RAMPS as used by MK3).
2. Open `MK3/MK3.ino`.
3. Select the correct board and port.
4. Upload.

After a first flash on an older EEPROM, the board may load hardcoded defaults (`Hardcoded Default Settings Loaded` on serial) or migrate known FR3D EEPROM versions to V28.

---

## License

- **Firmware in this repository (`MK3/`):** [GPL-3.0](LICENSE)
  - Upstream Mackerel/Marlin base remains free software under the GNU GPL
  - FR3D Addon modifications are distributed under the same GPL-3.0 terms

- **Internet control stack (Raspberry Pi Zero 2 W + web app + gateway):**  
  **not** included in this repository and **not** licensed here as public open-source software.

---

## Links

- System / web app reference: [http://fr3d-addon.web.app/](http://fr3d-addon.web.app/)
- Source: [github.com/dadonec-boop/MK3-FR3D-Addon](https://github.com/dadonec-boop/MK3-FR3D-Addon)
