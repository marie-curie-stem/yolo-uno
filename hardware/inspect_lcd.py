# inspect_lcd.py - find out which pins / address the OhStem lcd1602 library uses
# Run on the Yolo UNO:  import inspect_lcd
# Then paste the complete output back into the chat.

import os, sys

KEYWORDS = ("i2c", "scl", "sda", "pin", "addr", "0x", "freq", "power", "enable", "grove", "port")


def hr(title):
    print()
    print("=" * 50)
    print(title)
    print("=" * 50)


def public(obj):
    return [n for n in dir(obj) if not n.startswith("__")]


def find_source(mod):
    """Return the .py source path of an imported module, if it is not frozen."""
    name = mod.__name__
    path = getattr(mod, "__file__", None)
    cands = [path] if path else []
    cands += ["/" + name + ".py", "/lib/" + name + ".py", name + ".py"]
    for c in cands:
        if not c:
            continue
        try:
            open(c).close()
            return c
        except OSError:
            pass
    return None


def dump_source(modname):
    hr("MODULE: " + modname)
    try:
        mod = __import__(modname)
    except Exception as e:
        print("import failed:", e)
        return None
    print("public names:", public(mod))
    src = find_source(mod)
    if not src:
        print("(no .py source on the filesystem - module is probably frozen into the firmware)")
        return mod
    print("source file:", src)
    print("--- lines mentioning pins / I2C / addresses ---")
    try:
        with open(src) as f:
            n = 0
            for line in f:
                n += 1
                low = line.lower()
                if any(k in low for k in KEYWORDS):
                    print("{:4d}: {}".format(n, line.rstrip()))
    except Exception as e:
        print("read failed:", e)
    return mod


hr("Filesystem")
for d in ("/", "/lib"):
    try:
        print(d, "->", os.listdir(d))
    except OSError:
        pass

yolo = dump_source("yolo_uno")
lcdmod = dump_source("lcd1602")

# ---- create the display object exactly like the example program does
hr("LCD1602 object")
lcd = None
try:
    from lcd1602 import LCD1602
    lcd = LCD1602()
    print("created:", lcd)
    print("attributes:", public(lcd))
except Exception as e:
    print("LCD1602() failed:", e)
    sys.print_exception(e)


def walk(obj, label, depth=0, seen=None):
    """Look for I2C objects inside obj and print their repr (shows pins!)."""
    if seen is None:
        seen = []
    if depth > 3 or id(obj) in seen:
        return
    seen.append(id(obj))
    for name in public(obj):
        try:
            val = getattr(obj, name)
        except Exception:
            continue
        r = repr(val)
        if "I2C" in r or "Pin(" in r or "scl" in r.lower():
            print("  {}.{} = {}".format(label, name, r))
        if depth < 2 and not callable(val) and not isinstance(val, (int, str, bytes, float, bool, type(None))):
            walk(val, label + "." + name, depth + 1, seen)


if lcd is not None:
    hr("I2C / Pin objects found inside the LCD object")
    walk(lcd, "lcd")
    # common attribute names
    for n in ("i2c", "_i2c", "bus", "addr", "_addr", "address", "i2c_addr", "_address"):
        if hasattr(lcd, n):
            v = getattr(lcd, n)
            print("lcd.{} = {!r}".format(n, v))
            if n.lower().endswith(("addr", "address")) and isinstance(v, int):
                print("    -> 0x{:02X}".format(v))
            try:
                found = v.scan()
                print("    scan() on this bus:", [hex(a) for a in found])
            except Exception:
                pass

# ---- pins defined by the board support module
if yolo is not None:
    hr("yolo_uno: names that look like pins / buses")
    for n in public(yolo):
        low = n.lower()
        if any(k in low for k in ("i2c", "scl", "sda", "pin", "grove", "port", "d1", "a0", "led", "power")):
            try:
                print("  {} = {!r}".format(n, getattr(yolo, n)))
            except Exception:
                pass

hr("Done - please paste everything above into the chat")
