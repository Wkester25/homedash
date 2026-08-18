"""GUI smoke tests. Skipped automatically if tkinter isn't installed or no
display is available (e.g. python3-tk missing, or headless CI with no X /
Xvfb) - the rest of the suite runs fine without these.
"""

import pytest

tk = pytest.importorskip("tkinter")

from homedash.checks.base import BaseCheck  # noqa: E402
from homedash.models import CheckResult, Status  # noqa: E402
from homedash.monitor import Monitor  # noqa: E402
from homedash.ui.dashboard import DashboardApp  # noqa: E402


class StubCheck(BaseCheck):
    name = "Stub"

    def run(self):
        return CheckResult(name=self.name, status=Status.OK, summary="fine")


def _find_widgets(widget, tk_class):
    found = []
    for child in widget.winfo_children():
        if child.winfo_class() == tk_class:
            found.append(child)
        found.extend(_find_widgets(child, tk_class))
    return found


@pytest.fixture
def app():
    # Long interval + no polling: the background monitor thread and UI
    # refresh timer should never actually fire during these tests.
    monitor = Monitor(config={"refresh_interval_seconds": 3600}, checks=[StubCheck()])
    try:
        dashboard = DashboardApp(monitor, ui_config={"fullscreen": False, "poll_interval_seconds": 3600})
    except tk.TclError:
        pytest.skip("no display available for Tkinter tests")
    yield dashboard
    try:
        if dashboard.winfo_exists():
            dashboard.destroy()
    except tk.TclError:
        pass  # already destroyed by the test itself


def test_dashboard_has_exactly_one_close_button(app):
    app.update()
    close_buttons = [b for b in _find_widgets(app, "Button") if b.cget("text") == "✕"]
    assert len(close_buttons) == 1


def test_clicking_close_button_destroys_window(app):
    app.update()
    close_buttons = [b for b in _find_widgets(app, "Button") if b.cget("text") == "✕"]

    close_buttons[0].invoke()

    # The whole Tk interpreter is torn down along with the root window, so
    # any further call into it raises rather than returning False - that's
    # the strongest available proof the window is gone.
    with pytest.raises(tk.TclError):
        app.winfo_exists()


def test_clicking_close_button_stops_the_monitor(app):
    app.update()
    close_buttons = [b for b in _find_widgets(app, "Button") if b.cget("text") == "✕"]

    close_buttons[0].invoke()

    assert app.monitor._thread is None or not app.monitor._thread.is_alive()
