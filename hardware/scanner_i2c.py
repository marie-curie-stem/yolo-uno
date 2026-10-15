# i2c_scan.py - I2C scanner for Yolo UNO (ESP32-S3), MicroPython 1.26
#
# Usage on the board:
#   import i2c_scan
#   i2c_scan.scan(scl=9, sda=8)      # scan one specific pin pair
#   i2c_scan.find_bus()              # try many pin pairs (use if you don't know the pins)
#   i2c_scan.backlight_test(0x27, scl=9, sda=8)   # blink the LCD backlight
#
# Running the file directly (import i2c_scan) scans the default candidates.

from machine import Pin, SoftI2C
import time

# Known I2C addresses, to help identify what was found
KNOWN = {
    0x20: "PCF8574 I/O expander (LCD backpack, alt. address)",
    0x21: "PCF8574 I/O expander",
    0x22: "PCF8574 I/O expander",
    0x23: "PCF8574 I/O expander / BH1750 light sensor",
    0x24: "PCF8574 I/O expander",
    0x25: "PCF8574 I/O expander",
    0x26: "PCF8574 I/O expander",
    0x27: "PCF8574 LCD backpack (the usual 1602 address)",
    0x38: "PCF8574A I/O expander / AHT10/AHT20",
    0x39: "PCF8574A I/O expander",
    0x3A: "PCF8574A I/O expander",
    0x3B: "PCF8574A I/O expander",
    0x3C: "SSD1306 OLED / PCF8574A",
    0x3D: "SSD1306 OLED (alt) / PCF8574A",
    0x3E: "PCF8574A I/O expander",
    0x3F: "PCF8574A LCD backpack (the other common 1602 address)",
    0x40: "PCA9685 / INA219 / HTU21D / SI7021",
    0x48: "ADS1115 / PCF8591 / TMP102",
    0x50: "AT24C EEPROM",
    0x51: "PCF8563 RTC / EEPROM",
    0x57: "AT24C32 EEPROM (on DS3231 modules)",
    0x5A: "MLX90614 / CCS811",
    0x68: "DS3231 / DS1307 RTC / MPU6050",
    0x69: "MPU6050 (alt)",
    0x76: "BME280 / BMP280",
    0x77: "BME280 / BMP280 / BMP180",
}

# Default candidate pairs (scl, sda). Adjust once you know the board's I2C pins.
CANDIDATES = ((12, 11), (9, 8), (2, 1), (48, 47), (22, 21), (5, 4), (7, 6))

# GPIOs that are safe to wiggle on an ESP32-S3 module with flash + PSRAM.
# Skipped: 19/20 (USB), 26-37 (flash/PSRAM), 0 (boot), 43/44 (UART0), 45/46 (strapping).
SAFE_PINS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
             15, 16, 17, 18, 21, 38, 39, 40, 41, 42, 47, 48]


def scan(scl, sda, freq=100000, verbose=True):
    """Scan one pin pair. Returns a list of addresses found."""
    try:
        i2c = SoftI2C(scl=Pin(scl), sda=Pin(sda), freq=freq, timeout=20000)
        found = i2c.scan()
    except Exception as e:
        if verbose:
            print("SCL={} SDA={}: error ({})".format(scl, sda, e))
        return []
    if verbose:
        if found:
            print("SCL={} SDA={}: {} device(s)".format(scl, sda, len(found)))
            for a in found:
                print("   0x{:02X} ({:3d})  {}".format(a, a, KNOWN.get(a, "unknown device")))
        else:
            print("SCL={} SDA={}: nothing found".format(scl, sda))
    return found


def scan_candidates():
    hits = {}
    for scl, sda in CANDIDATES:
        found = scan(scl, sda)
        if found:
            hits[(scl, sda)] = found
    return hits


def find_bus(pins=SAFE_PINS):
    """Brute force: try every ordered pair of safe GPIOs as (SCL, SDA).
    Takes a while (~600 pairs). Stops printing noise, only reports hits.
    I2C lines are open-drain with pull-ups, so this is harmless to the board,
    but unplug anything on those pins that dislikes being toggled."""
    print("Brute-force scan over {} pins, please wait...".format(len(pins)))
    hits = {}
    for scl in pins:
        for sda in pins:
            if scl == sda:
                continue
            try:
                i2c = SoftI2C(scl=Pin(scl), sda=Pin(sda), freq=100000, timeout=5000)
                found = i2c.scan()
            except Exception:
                continue
            if found:
                hits[(scl, sda)] = found
                print("HIT  SCL={} SDA={} -> {}".format(
                    scl, sda, ", ".join("0x{:02X}".format(a) for a in found)))
    if not hits:
        print("No device found on any pin pair. Check wiring, power (the 1602 backpack")
        print("needs 5 V) and the pull-up resistors.")
    return hits


def backlight_test(addr, scl, sda, times=3):
    """Toggle the backlight of a PCF8574 LCD backpack (bit 3 = backlight).
    If it blinks, the address is correct and the backpack answers."""
    i2c = SoftI2C(scl=Pin(scl), sda=Pin(sda), freq=100000)
    for _ in range(times):
        i2c.writeto(addr, b"\x00")   # backlight off
        time.sleep(0.4)
        i2c.writeto(addr, b"\x08")   # backlight on
        time.sleep(0.4)
    print("Backlight toggled {} times at 0x{:02X}".format(times, addr))


def main():
    print("I2C scanner - checking default pin pairs")
    hits = scan_candidates()
    print()
    lcd = [(p, a) for p, addrs in hits.items() for a in addrs if a in (0x27, 0x3F) or 0x20 <= a <= 0x27 or 0x38 <= a <= 0x3F]
    if lcd:
        (scl, sda), addr = lcd[0]
        print("Likely 1602 LCD backpack at 0x{:02X} (SCL={}, SDA={}).".format(addr, scl, sda))
        print("Try: i2c_scan.backlight_test(0x{:02X}, {}, {})".format(addr, scl, sda))
    elif hits:
        print("Devices found, but none look like an LCD backpack.")
    else:
        print("Nothing found on the default pairs. Run i2c_scan.find_bus()")
        print("to try all safe pin combinations.")


main()