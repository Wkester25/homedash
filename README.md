# HomeDash

A small Python dashboard for a Raspberry Pi + touchscreen that keeps an eye
on your home network: internet connectivity/speed, your router's logs, your
Home Assistant instance, and every VM/LXC container on Proxmox.

Four tiles, color-coded (green/amber/red), tap any tile for details:

- **Internet** - ping reachability + latency, DNS resolution, periodic speed test (down/up Mbps).
- **Router** - reachable check, plus recent log lines scanned for errors over SSH.
- **Home Assistant** - `/api/` reachability, plus a scan of `/api/states` for anything stuck `unavailable`/`unknown`.
- **Proxmox** - every node's online status, and every VM/LXC's running state, CPU, and memory.

A background thread re-runs all checks on a timer (`refresh_interval_seconds`
in config, default 60s); the UI just reads the latest results and redraws.

## Setup on the Raspberry Pi

```bash
sudo apt update
sudo apt install -y python3-venv python3-tk
cd ~
git clone <this repo> homedash
cd homedash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
```

Edit `config.yaml` (see inline comments for every field):

- **Home Assistant**: create a long-lived access token under your HA profile
  (Settings -> your profile -> Security -> Long-Lived Access Tokens) and set
  `base_url` + `token`.
- **Proxmox**: create an API token under Datacenter -> Permissions -> API
  Tokens. Set `token_id` (e.g. `root@pam!homedash`) and `token_secret`. Give
  the token read (`PVEAuditor`) access to see VM status - it doesn't need
  anything more privileged than that.
- **Router**: set `host` to your router's LAN IP. If it supports SSH (most
  OpenWrt/DD-WRT/pfSense/OPNsense/UniFi gear does), enable `ssh` and set the
  `log_command` for your firmware - a few common ones are listed as comments
  in `config.example.yaml`. If your router has no SSH access, set
  `ssh.enabled: false` and you'll still get a reachability check.

Run it once to sanity-check your config before wiring up the GUI:

```bash
python main.py --once
```

This prints one line per check and exits non-zero if anything isn't OK -
handy for a quick `cron`/`systemd` smoke test too.

## Running the touchscreen dashboard

```bash
python main.py
```

Launches fullscreen by default (`ui.fullscreen: true` in config.yaml). Press
`Esc` to toggle out of fullscreen, `q` to quit - useful while you're setting
it up with a keyboard attached before mounting it kiosk-style.

Other modes:

```bash
python main.py --no-ui              # headless loop, logs each cycle to stdout
python main.py --config /path.yaml  # use a config file elsewhere
```

## Auto-start on boot (kiosk mode)

A systemd unit is provided in `systemd/homedash.service`. Adjust the paths/
user inside it to match your setup, then:

```bash
sudo cp systemd/homedash.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now homedash.service
```

It assumes X is already running on `:0` (e.g. via `raspi-config` -> auto
login to desktop). If you're running a minimal/no-desktop image instead,
start X yourself first (e.g. via `.xinitrc` + `startx`) and point
`DISPLAY`/`XAUTHORITY` at that session.

## Project layout

```
main.py                        CLI entry point (--once / --no-ui / GUI)
config.example.yaml            Config schema + docs (copy to config.yaml)
src/homedash/
  config.py                    YAML loader (layers config.yaml over the example's defaults)
  models.py                    CheckResult / Status shared types
  monitor.py                   Background polling loop, thread-safe result store
  net_utils.py                 Shared ping() helper (shells out to system ping)
  checks/
    internet.py                Ping + DNS + speed test
    home_assistant.py          HA REST API checks
    proxmox.py                 Proxmox VE API checks
    router.py                  Router reachability + SSH log scan
  ui/
    dashboard.py               Tkinter kiosk UI
    formatting.py              Pure text-formatting helpers (no Tk - unit testable)
systemd/homedash.service       Autostart unit
tests/                         pytest suite (mocks all network calls)
```

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

All checks talk to the network via `requests`, `paramiko`, `speedtest`, and
`subprocess` (for `ping`) - the test suite mocks every one of those, so
`pytest` runs offline and doesn't touch your real devices.

## Extending

Every check is a small class implementing `BaseCheck.run() -> CheckResult`
(see `src/homedash/checks/base.py`). To add a new one (e.g. a NAS, a UPS, a
second Proxmox cluster), drop a new file in `checks/`, wire it up in
`monitor.build_checks()`, and it'll automatically get a tile.
