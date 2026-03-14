# Changelog

All notable changes to IonoBrowser are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.2.0-beta] — 2026-03-14

### Added

- **UK FM Stations CSV** — 2,632 transmitter entries parsed from the England, Scotland, Wales and Ireland FM Transmitters Frequency Finder PDF. Includes frequency, station, broadcaster, format, power, area, transmitter site, OS grid reference, and RDS PI code (84.9% coverage). PI codes sourced from a built-in lookup covering BBC nationals/locals/nations, Global Radio, Bauer, Nation, BFBS, Manx Radio, Channel Islands, and Irish (RTÉ + commercial) networks.

- **Distance column** — when location is configured in Settings and freq-match is active, a `Distance (km/miles)` column appears showing the distance from the user to each matched transmitter. Computed from OS National Grid and Irish Grid references via full Helmert transform (OSGB36/WGS84). Column is suppressed entirely for datasets with no location data.

- **Google Maps context menu** — right-click any row to open the transmitter location in Google Maps. Now works for FM CSV rows via Grid_Ref column in addition to existing lat/lon support (AOKI, RWW/RNA/REU formats).

- **Auto-cache on file open** — files opened from outside the cache directory are offered to be cached automatically. If a file with the same name already exists in the cache and the content differs, the user is offered to update it. Cached files reload automatically on next startup.

- **Cached Lists menu** — Lists menu now includes a submenu of all cached datasets for quick re-opening.

- **Settings → General panel** — new General section in Settings dialog. Currently contains the debug log toggle.

- **Debug log panel** — dockable panel (toggled via Settings → General) logging frequency change events and per-tab `_refresh_table` timing in milliseconds. Useful for diagnosing performance issues.

- **Numeric column sorting** — Distance, Frequency, and Power columns sort numerically rather than lexicographically via a custom `SORT_ROLE` on the model.

### Changed

- **Package refactor** — monolithic `ionobrowser.py` split into a proper Python package (`ionobrowser/`) with submodules: `constants`, `helpers`, `models`, `parsers`, `workers`, `mainwindow`, and `widgets/` (list_tab, sdr_panel, settings_dialog).

- **Frequency unit detection** — three-tier logic now checks column name first (`mhz` → ×1,000,000; `khz` → ×1,000; bare `hz` → as-is) before falling back to magnitude heuristic. Fixes FM frequency matching which was treating 88.1 as 88.1 kHz.

- **Frequency matching performance** — pre-compute `_freq_hz` for every row on load (eliminates per-refresh string parsing). Build a sorted frequency index at load time; freq-match now uses `bisect` binary search (O log n) rather than a linear scan. In a 1,800-row dataset, refresh time dropped from ~6 seconds to ~0.2 ms.

- **SDR panel update guards** — `update_property` now checks whether frequency, mode, or signal power has actually changed before updating QLabel text, eliminating spurious repaints on every poll cycle.

- **Frequency change guard** — `set_sdr_frequency` only calls `_refresh_table` when the frequency value actually differs from the last received value.

- **On Air Now filter** — passes all rows through silently when the dataset has no schedule/time columns, rather than hiding everything.

- **Distance column header** — now includes the active unit, e.g. `Distance (km)` or `Distance (miles)`. Values are plain floats.

- **Geo resolution moved to background thread** — OS/Irish grid ref Helmert transforms (previously blocking the UI for ~8 seconds on the FM CSV) now run in a `_GeoWorker` QThread. The tab is usable immediately on load. The geo worker is only spawned if the dataset has recognised location column names.

### Fixed

- **SDR++ rigctld disconnect** — SDR++ does not implement the `m` (mode query) rigctld command. IonoBrowser was sending it every poll cycle, receiving no response, and disconnecting after 3 failures. Fixed by passing `mode_supported=False` when constructing `RigctldWorker` for SDR++; `m` is never sent.

- **Socket timeout** — raised from 2s to 5s. Added `MAX_ERRORS = 3` consecutive failure tolerance; a single slow response no longer causes an immediate disconnect.

- **Poll errors** — transient poll errors now appear in the status bar rather than a modal dialog. Fatal connection errors still show a dialog.

- **Duplicate `_refresh_table` tail** — removed copy-paste duplicate of selection reconnect and count label code that was running twice per refresh.

- **Startup location settings** — `_apply_location_settings` is now called at the end of `_restore_settings` so tabs opened from saved session state receive the correct location settings on startup.

### Build

- **PyInstaller spec** — added `('ionobrowser', 'ionobrowser')` to `datas` and `collect_submodules('ionobrowser')` to `hiddenimports` for the package structure. Removed invalid `--specpath` flag from the workflow command.

- **AppImageBuilder** — removed unsupported `name` key from `AppImage` section. Added `allow_unauthenticated: true` to apt section. Added `cp -r ionobrowser/` to AppDir copy step. Added icon copy from `appimage/ionobrowser.svg` to `pixmaps` and hicolor icon theme paths. Removed redundant `mv` rename step.

---

## [0.1.0-beta] — initial release

- HF/FM frequency browser with tabbed interface
- Supports EIBI, AOKI, HFCC, RWW/RNA/REU, and generic CSV formats
- SDRConnect WebSocket integration
- SDR++ and GQRX via rigctld TCP
- Frequency match filtering with configurable tolerance
- On Air Now filter (UTC schedule-aware)
- Text search with column filter
- Dark/light theme support
- Download built-in lists (EIBI, AOKI, RWW, RNA, REU)
- OS National Grid and Irish Grid reference parsing with WGS84 conversion
- Settings: SDR host/port, location (lat/lon, km/miles), theme
- Windows EXE (PyInstaller) and Linux AppImage builds via GitHub Actions
