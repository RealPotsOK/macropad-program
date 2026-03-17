from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _app_window_media import send_app_play_pause

def main() -> None:
    send_app_play_pause(("spotify.exe",), label="Spotify")


if __name__ == "__main__":
    main()
