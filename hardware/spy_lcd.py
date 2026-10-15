# spy_lcd.py - log every I2C call the OhStem lcd1602 library makes
# Run on the Yolo UNO:  import spy_lcd
# Paste the whole output back into the chat.

import machine, sys

LOG = []


def log(*a):
    print("[spy]", *a)


class Spy:
    """Wraps a real I2C/SoftI2C object and prints what the library does with it."""

    def __init__(self, kind, real, args, kwargs):
        self._kind = kind
        self._real = real
        log("{}(*{}, **{})".format(kind, args, kwargs))

    def __getattr__(self, name):
        attr = getattr(self._real, name)
        if not callable(attr):
            return attr

        def wrapper(*a, **k):
            try:
                r = attr(*a, **k)
                if name == "scan":
                    log("scan() ->", [hex(x) for x in r])
                else:
                    log("{}{} ok".format(name, a if len(repr(a)) < 80 else "(...)"))
                return r
            except Exception as e:
                log("{}{} FAILED: {}".format(name, a if len(repr(a)) < 80 else "(...)", e))
                raise
        return wrapper


def make_factory(kind):
    real_cls = getattr(machine, kind)

    def factory(*args, **kwargs):
        return Spy(kind, real_cls(*args, **kwargs), args, kwargs)
    return factory


for k in ("I2C", "SoftI2C"):
    if hasattr(machine, k):
        setattr(machine, k, make_factory(k))

print("--- importing OhStem library and creating LCD1602() ---")
try:
    from lcd1602 import LCD1602
    lcd = LCD1602()
    print("--- LCD1602() succeeded ---")
except Exception as e:
    print("--- LCD1602() failed:", e)

# Source hints: the board also contains a readable smartcity_lcd1602.py
print()
print("--- lines in smartcity_lcd1602.py that mention address / I2C ---")
try:
    with open("smartcity_lcd1602.py") as f:
        n = 0
        for line in f:
            n += 1
            low = line.lower()
            if any(w in low for w in ("addr", "i2c", "0x", "scan", "freq", "pcf")):
                print("{:4d}: {}".format(n, line.rstrip()))
except Exception as e:
    print("cannot read:", e)