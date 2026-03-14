from __future__ import annotations

from .mixins_callbacks_a import CallbacksAMixin
from .mixins_callbacks_b import CallbacksBMixin
from .mixins_chrome import ChromeMixin
from .mixins_connection import ConnectionMixin
from .mixins_desktop import DesktopMixin
from .mixins_init import InitMixin
from .mixins_overlay import OverlayMixin
from .mixins_panels_a import PanelsAMixin
from .mixins_panels_b import PanelsBMixin
from .mixins_profile import ProfileMixin
from .mixins_profile_copy import ProfileCopyMixin
from .mixins_workspace import WorkspaceMixin
from .shared import SerialControllerError, Settings, _enable_windows_dpi_awareness, suppress, tk


class MacropadWindow(
    InitMixin,
    ChromeMixin,
    PanelsAMixin,
    PanelsBMixin,
    ProfileMixin,
    ProfileCopyMixin,
    WorkspaceMixin,
    OverlayMixin,
    DesktopMixin,
    ConnectionMixin,
    CallbacksAMixin,
    CallbacksBMixin,
):
    pass


async def run_key_window(
    settings: Settings,
    *,
    start_hidden: bool = False,
    launch_command: list[str] | None = None,
    instance_guard: object | None = None,
) -> int:
    _enable_windows_dpi_awareness()
    try:
        root = tk.Tk()
    except Exception as exc:  # pragma: no cover - environment specific
        raise SerialControllerError(f"Tkinter is unavailable: {exc}") from exc
    if start_hidden:
        with suppress(Exception):
            root.withdraw()

    app = MacropadWindow(
        root,
        settings,
        start_hidden=start_hidden,
        launch_command=launch_command,
        instance_guard=instance_guard,
    )
    return await app.run()
