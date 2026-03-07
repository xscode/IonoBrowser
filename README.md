# IonoBrowser

**IonoBrowser** is a desktop application for browsing HF shortwave frequency lists and controlling an [SDRplay SDRConnect](https://www.sdrplay.com/sdrconnect/) receiver via its WebSocket API.

Open multiple frequency databases in tabs, filter by text, time-of-broadcast, or current VFO frequency, and tune your SDR with a double-click.

> **Version 0.1.0-beta** — first public release. Feedback and bug reports welcome via [GitHub Issues](../../issues).

---

## Screenshots

_Screenshots coming soon._

---

## Features

- **Multi-tab frequency list viewer** — open as many lists as you like simultaneously, each with independent filters
- **One-click download** of popular HF databases (EIBI, AOKI, HFCC, RWW, RNA, REU) with automatic format detection
- **Smart format parsing** — handles EIBI semicolon CSV, AOKI and HFCC fixed-width text, and RWW/RNA/REU quoted CSV automatically
- **On Air Now filter** — shows only stations currently broadcasting based on UTC schedule columns
- **Match SDR Freq** — filters all tabs to entries within ±5 kHz of the current SDRConnect VFO
- **SDRConnect control** — connect, tune, and change mode directly from the app via WebSocket
- **Live readback** — VFO frequency, demodulator mode, and signal power updated in real time
- **Dark and Light themes** — switchable from the Help menu, preference saved across sessions
- **Edit support** — add, edit, and delete entries in any list; save back to CSV
- **Cross-platform** — Linux, macOS, and Windows

---

## Supported Frequency Databases

| Source | Format | Auto-download |
|--------|--------|---------------|
| [EIBI](https://www.eibispace.de) | Semicolon-delimited CSV | ✓ |
| [AOKI](https://www1.m2.mediacat.ne.jp/binews/) | Fixed-width text (zip) | ✓ |
| [HFCC](https://www.hfcc.org) | Fixed-width text (zip) | ✓ |
| [RWW / RNA / REU](https://rxx.classaxe.com) | Quoted CSV | ✓ |
| Any custom CSV | Auto-detected | — |

Downloaded files are cached in the settings directory and available offline via **Lists → Cached Lists**.

---

## Requirements

- Python 3.10 or newer
- [PyQt6](https://pypi.org/project/PyQt6/)
- [websockets](https://pypi.org/project/websockets/)
- [requests](https://pypi.org/project/requests/) _(optional but recommended — improves download reliability)_

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/YOUR_USERNAME/ionobrowser.git
cd ionobrowser

# 2. Install dependencies
pip install PyQt6 websockets requests

# 3. Run
python ionobrowser.py
```

### Linux note
If `pip` complains about system packages, use:
```bash
pip install PyQt6 websockets requests --break-system-packages
```
Or create a virtual environment first:
```bash
python -m venv venv
source venv/bin/activate
pip install PyQt6 websockets requests
python ionobrowser.py
```

---

## SDRConnect Setup

IonoBrowser connects to SDRConnect via its built-in WebSocket API.

1. Open SDRConnect and start a device
2. In IonoBrowser, enter the host (`localhost`) and port (`8073` by default) in the SDRConnect Control panel
3. Click **Connect**
4. Select a row in any frequency list and click **Tune Selected** (or double-click a row) to tune

The **Match SDR freq** checkbox (enabled once connected) filters all open tabs to entries within ±5 kHz of the current VFO — useful for identifying what you are listening to.

---

## Settings & Data

All settings and cached database files are stored in:

| Platform | Path |
|----------|------|
| Linux / macOS | `~/.config/IonoBrowser/` |
| Windows | `%APPDATA%\IonoBrowser\` |

Settings include window geometry, SDRConnect host/port, last open files, and theme preference.

---

## Roadmap

- [ ] Scheduled auto-refresh of cached databases
- [ ] Column visibility toggle per tab
- [ ] Highlight rows matching current frequency without filtering
- [ ] Export filtered view to CSV
- [ ] Support for additional database formats

---

## Contributing

Contributions are welcome. Please open an issue first to discuss what you would like to change.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Open a pull request

---

## Licence

IonoBrowser is released under the [GNU General Public License v3.0](LICENSE).

You are free to use, modify, and redistribute this software. Any derivative work must also be released under the GPL v3. Commercial sale is not permitted under the terms of this licence.

---

## Acknowledgements

- Frequency data provided by [EIBI](https://www.eibispace.de), [AOKI](https://www1.m2.mediacat.ne.jp/binews/), [HFCC](https://www.hfcc.org), and [Classaxe RXX](https://rxx.classaxe.com)
- SDRConnect WebSocket API by [SDRplay](https://www.sdrplay.com)
- UI theme inspired by [Catppuccin Mocha](https://github.com/catppuccin/catppuccin)
