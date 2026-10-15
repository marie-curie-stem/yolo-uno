# bus_check.py - low-level check of the I2C lines (SDA=GPIO11, SCL=GPIO12)
# Run on the Yolo UNO with the LCD connected:  import bus_check
# Paste the full output back into the chat.

from machine import Pin, SoftI2C, I2C
import time

SDA, SCL = 11, 12   # confirmed by yolo_uno.SDA_PIN / SCL_PIN


def level(pin_no, pull):
    p = Pin(pin_no, Pin.IN, pull)
    time.sleep_ms(5)
    return p.value()


print("=== 1. Idle levels of the I2C lines ===")
for name, no in (("SDA", SDA), ("SCL", SCL)):
    nopull = level(no, None)
    pdown = level(no, Pin.PULL_DOWN)
    pup = level(no, Pin.PULL_UP)
    print("{} (GPIO{}): no pull={}  internal pull-down={}  internal pull-up={}".format(
        name, no, nopull, pdown, pup))
    if pup == 0:
        print("   -> held LOW even with pull-up: short to GND or a device pulling the line down")
    elif pdown == 1:
        print("   -> external pull-up present (good, a powered backpack/module is connected)")
    else:
        print("   -> NO external pull-up: line floats. The LCD backpack is not powered,")
        print("      not connected to this pin, or has no pull-up resistors")

print()
print("=== 2. Scans at different speeds (software and hardware I2C) ===")
found_any = False
for freq in (10000, 100000, 400000):
    for label, make in (
        ("SoftI2C", lambda f: SoftI2C(scl=Pin(SCL), sda=Pin(SDA), freq=f, timeout=50000)),
        ("I2C(0)", lambda f: I2C(0, scl=Pin(SCL), sda=Pin(SDA), freq=f)),
    ):
        try:
            res = make(freq).scan()
            print("{:8} {:>6} Hz: {}".format(label, freq, [hex(a) for a in res]))
            found_any = found_any or bool(res)
        except Exception as e:
            print("{:8} {:>6} Hz: error {}".format(label, freq, e))

print()
print("=== 3. Direct write to the usual LCD addresses ===")
i2c = SoftI2C(scl=Pin(SCL), sda=Pin(SDA), freq=50000, timeout=50000)
for addr in (0x27, 0x3F, 0x20, 0x38):
    try:
        i2c.writeto(addr, b"\x08")
        print("0x{:02X}: ACK - device answers!".format(addr))
        found_any = True
    except OSError as e:
        # errno 19 = ENODEV (no ACK), 110 = timeout (line stuck)
        print("0x{:02X}: no answer (OSError {})".format(addr, e.args[0] if e.args else e))

print()
print("Result:", "device(s) found" if found_any else "no I2C device answered")