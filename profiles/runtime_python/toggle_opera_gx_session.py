from __future__ import annotations

import asyncio


async def _toggle_opera_gx() -> bool:
    from winsdk.windows.media.control import (  # type: ignore
        GlobalSystemMediaTransportControlsSessionManager as GSMTCManager,
    )

    manager = await asyncio.wait_for(GSMTCManager.request_async(), timeout=5.0)
    sessions = manager.get_sessions()
    for session in sessions:
        app_id = (session.source_app_user_model_id or "").lower()
        if "opera" not in app_id:
            continue
        await asyncio.wait_for(session.try_toggle_play_pause_async(), timeout=5.0)
        return True
    return False


def main() -> None:
    try:
        found = asyncio.run(_toggle_opera_gx())
    except TimeoutError:
        print("Opera GX media toggle failed: timed out while talking to Windows media sessions.")
        return
    except Exception as exc:
        print(f"Opera GX media toggle failed: {exc}")
        return
    if not found:
        print("Opera GX media session not found.")


if __name__ == "__main__":
    main()
