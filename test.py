import serial

PORT = "COM13"  # Change if needed.
BAUD = 9600


def main() -> None:
    with serial.Serial(PORT, BAUD, timeout=1) as ser:
        ser.write(b"ABCDEFGH\n")
        ser.flush()
    print(f"Sent to {PORT} @ {BAUD}: ABCDEFGH")


if __name__ == "__main__":
    main()
