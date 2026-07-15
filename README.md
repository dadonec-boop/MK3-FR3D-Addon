# MK3 + FR3D Addon

Public firmware for the **Desktop Filament Extruder MK3**, with **FR3D Addon** modifications by **Claudio Dadone**.

Based on **MACKEREL** (Marlin-derived filament extruder firmware by Filip Mulier / Hugh Lyman).

**Reference web app:** [http://fr3d-addon.web.app/](http://fr3d-addon.web.app/)

---

## What this repository contains

| Content | Description |
|---------|-------------|
| `MK3/` | Firmware sources (Arduino / Mega — flash this folder) |
| [`dist/MK3-FR3D-Addon.zip`](dist/MK3-FR3D-Addon.zip) | Ready-to-download ZIP of `MK3/` for Arduino IDE |
| [`docs/USER_GUIDE_...pdf`](docs/USER_GUIDE_FR3D_MK3_EN_ch1-2-3-4-5.pdf) | Standalone user guide (sensor, LCD, predictor operation) |
| [Pi gateway image (Release)](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/tag/pi-gateway-v0.1) | Raspberry Pi Zero 2 W factory image (binary only, see Releases) |
| Tag `v-mk3-original` | Stock MK3 (Mackerel base), **without** FR3D Addon |
| Tag `v-mk3-fr3d` / branch `main` | Latest **MK3 + FR3D Addon** |

This repository publishes **MK3 board firmware** (GPL-3.0) and, via **GitHub Releases**, a **prebuilt Pi Zero 2 W gateway image** (binary download only — gateway source is not published here).

It does **not** include the Python host tools or the web application source.

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

The web app / host stack is an **additional product feature** and is **not** published here as open-source.

A **prebuilt SD image** for the Pi Zero 2 W gateway is available for download under [Releases](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases) (image file only).

---

## Download Raspberry Pi Zero 2 W gateway image

Download the factory image from the Release:

- **[fr3daddon-small.img.zst](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/download/pi-gateway-v0.1/fr3daddon-small.img.zst)**  
  Release notes: [pi-gateway-v0.1](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/tag/pi-gateway-v0.1)

### Flash with Raspberry Pi Imager

1. Download [Raspberry Pi Imager](https://www.raspberrypi.com/software/).
2. Insert a micro SD card (**32 GB** or larger recommended).
3. Open Imager → **Choose OS** → **Use custom** → select `fr3daddon-small.img.zst`.
4. **Choose storage** → your SD card → **Write**.
5. Insert the SD into the Pi Zero 2 W and power on.

### First boot / factory defaults

- WiFi hotspot: **SSID `addonfr3d`** / password **`addonfr3d`**
- Local setup page (from a device on that hotspot): **http://10.42.0.1:8080/**  
  Login: **`addonfr3d` / `addonfr3d`**
- On first boot the image personalizes hostname / SSH keys automatically (no manual script needed).
- Then continue pairing from the web app ([fr3d-addon.web.app](http://fr3d-addon.web.app/)) using the token shown on the MK3S+ (**Control → addonfr3d-gateway**).

---

## Standalone user guide

For MK3S+ with FR3D Addon operating from the machine LCD (**standalone** — without Raspberry Pi gateway / web app):

- [USER_GUIDE_FR3D_MK3_EN_ch1-2-3-4-5.pdf](docs/USER_GUIDE_FR3D_MK3_EN_ch1-2-3-4-5.pdf)

Covers project scope, Addon FR3D overview, diameter hardware (Hall on A3 / ARTME 3D optical), LCD main-screen use, and recommended steps for automatic predictor operation.

---

## Download ZIP (Arduino IDE)

If you only want to flash the board, download the ready-made package:

- **[MK3-FR3D-Addon.zip](dist/MK3-FR3D-Addon.zip)**

### Steps on your PC

1. Download [`dist/MK3-FR3D-Addon.zip`](dist/MK3-FR3D-Addon.zip).
2. Unzip it. You will get a folder named **`MK3`** (it must stay named `MK3`, matching `MK3.ino`).
3. Install **Arduino IDE** (or a compatible AVR Mega 2560 / RAMPS toolchain as used by MK3).
4. In Arduino IDE: **File → Open…** and open `MK3/MK3.ino`.
5. Select the correct **board** and **port**.
6. Click **Upload**.

After a first flash on an older EEPROM, the board may load hardcoded defaults (`Hardcoded Default Settings Loaded` on serial) or migrate known FR3D EEPROM versions to V28.

### Alternative (from source tree)

Clone or browse this repository and open `MK3/MK3.ino` directly — same result as using the ZIP.

---

## License

- **Firmware in this repository (`MK3/`):** [GPL-3.0](LICENSE)
  - Upstream Mackerel/Marlin base remains free software under the GNU GPL
  - FR3D Addon modifications are distributed under the same GPL-3.0 terms

- **Internet control stack (web app + gateway source):**  
  **not** included in this repository and **not** licensed here as public open-source software.

- **Pi Zero 2 W factory image (Release asset):** distributed as a binary image for end users; gateway source code is not published in this repository.

---

## Links

- Pi gateway image: [fr3daddon-small.img.zst](https://github.com/dadonec-boop/MK3-FR3D-Addon/releases/download/pi-gateway-v0.1/fr3daddon-small.img.zst)
- Firmware ZIP (Arduino IDE): [dist/MK3-FR3D-Addon.zip](dist/MK3-FR3D-Addon.zip)
- Standalone user guide (PDF): [docs/USER_GUIDE_FR3D_MK3_EN_ch1-2-3-4-5.pdf](docs/USER_GUIDE_FR3D_MK3_EN_ch1-2-3-4-5.pdf)
- System / web app reference: [http://fr3d-addon.web.app/](http://fr3d-addon.web.app/)
- Source: [github.com/dadonec-boop/MK3-FR3D-Addon](https://github.com/dadonec-boop/MK3-FR3D-Addon)
