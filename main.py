#!/usr/bin/env python3
"""HomeDash entry point.

Usage:
    python main.py                 # launch the touchscreen dashboard (default)
    python main.py --once          # run every check once, print results, exit
    python main.py --no-ui         # run the monitor loop headless, logging results
    python main.py --config PATH   # use a config file other than ./config.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from homedash.config import ConfigError, load_config  # noqa: E402
from homedash.models import Status  # noqa: E402
from homedash.monitor import Monitor  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("homedash")


def _print_results(monitor: Monitor) -> bool:
    """Print a text summary of the latest results. Returns True if all OK."""
    results = monitor.get_results()
    all_ok = True
    for name, result in results.items():
        if result.status != Status.OK:
            all_ok = False
        print(f"[{result.status.value.upper():7}] {name}: {result.summary}")
    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml")
    parser.add_argument("--once", action="store_true", help="Run all checks once, print, and exit")
    parser.add_argument("--no-ui", action="store_true", help="Run headless, logging results on each cycle")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        logger.error(str(exc))
        return 1

    monitor = Monitor(config)

    if args.once:
        monitor.run_once()
        all_ok = _print_results(monitor)
        return 0 if all_ok else 2

    if args.no_ui:
        monitor.start()
        try:
            while True:
                time.sleep(monitor.refresh_interval)
                _print_results(monitor)
        except KeyboardInterrupt:
            pass
        finally:
            monitor.stop()
        return 0

    from homedash.ui.dashboard import DashboardApp

    app = DashboardApp(monitor, ui_config=config.get("ui", {}))
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
