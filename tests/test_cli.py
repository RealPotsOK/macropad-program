from macropad_ble.cli import build_parser, cli_overrides_from_args


def test_parser_parses_list_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["list"])
    assert args.command == "list"


def test_parser_parses_listen_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["listen"])
    assert args.command == "listen"


def test_parser_parses_led_toggle_command() -> None:
    parser = build_parser()
    args = parser.parse_args(["led", "toggle"])
    assert args.command == "led"
    assert args.led_state == "toggle"


def test_parser_global_options_are_captured() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--port",
            "COM12",
            "--hint",
            "Curiosity",
            "--baud",
            "115200",
            "--log",
            "DEBUG",
            "status",
        ]
    )

    overrides = cli_overrides_from_args(args)
    assert overrides["port"] == "COM12"
    assert overrides["hint"] == "Curiosity"
    assert overrides["baud"] == 115200
    assert overrides["log_level"] == "DEBUG"


def test_parser_accepts_common_options_after_subcommand() -> None:
    parser = build_parser()
    args = parser.parse_args(["led", "on", "--port", "COM13"])
    overrides = cli_overrides_from_args(args)
    assert args.command == "led"
    assert args.led_state == "on"
    assert overrides["port"] == "COM13"


def test_parser_accepts_common_options_after_listen_subcommand() -> None:
    parser = build_parser()
    args = parser.parse_args(["listen", "--port", "COM13"])
    overrides = cli_overrides_from_args(args)
    assert args.command == "listen"
    assert overrides["port"] == "COM13"
