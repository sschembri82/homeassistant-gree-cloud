# sschembri82 fork

A pinned copy of [davo22/homeassistant-gree-cloud](https://github.com/davo22/homeassistant-gree-cloud)
for one Gree hot water heat pump, so upstream releases only arrive after review.

- Versions are `<upstream>-ss.<n>`, e.g. `1.7.6-ss.1` = upstream 1.7.6 + fork change 1.
  Every version is a tag and a GitHub release, so HACS can reinstall any of them.
- Fork changes live mostly in `custom_components/gree_cloud/hwhp_extra.py`
  (extra read-only HWHP readings, upstream issue #74); hooks in `sensor.py`,
  `binary_sensor.py` and `coordinator.py` are marked `# Fork:`.
- Upstream releases are merged selectively (fixes for HWHP, cloud/MQTT, login
  and new Home Assistant versions). If upstream ships the #74 readings itself,
  drop ours and use theirs.
- After reviewing an upstream release, re-version onto it (e.g. `1.7.7-ss.1`)
  even if nothing was merged: Home Assistant compares the part before `-ss`
  with davo22's latest release to decide whether to raise a review alert.
- Revert: HACS -> Gree Climate Cloud -> Redownload -> pick an earlier tag, or
  remove this repo and reinstall davo22's.
