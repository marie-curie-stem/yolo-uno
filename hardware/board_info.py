# board_info.py - collect as much information as possible about a
# Yolo UNO (ESP32-S3) running MicroPython 1.26
# Copy to the board and run:  import board_info   (or run in Thonny)

import sys, gc, os, time
import machine

try:
    import esp32
except ImportError:
    esp32 = None
try:
    import esp
except ImportError:
    esp = None
try:
    import network
except ImportError:
    network = None
try:
    import ubinascii as binascii
except ImportError:
    import binascii


def section(title):
    print()
    print("=" * 52)
    print(" " + title)
    print("=" * 52)


def show(label, value):
    print("{:<26}: {}".format(label, value))


def fmt_bytes(n):
    if n >= 1024 * 1024:
        return "{} B ({:.2f} MiB)".format(n, n / 1048576)
    if n >= 1024:
        return "{} B ({:.1f} KiB)".format(n, n / 1024)
    return "{} B".format(n)


def safe(label, fn):
    try:
        show(label, fn())
    except Exception as e:
        show(label, "n/a ({})".format(e))


# ---------------------------------------------------------------- firmware
section("MicroPython / firmware")
show("sys.version", sys.version)
show("sys.implementation", sys.implementation)
show("sys.platform", sys.platform)
show("sys.byteorder", sys.byteorder)
show("sys.maxsize", sys.maxsize)
u = os.uname()
for k in ("sysname", "nodename", "release", "version", "machine"):
    show("uname." + k, getattr(u, k, "?"))
safe("build (impl version)", lambda: ".".join(str(x) for x in sys.implementation.version[:3]))
safe("mpy version", lambda: sys.implementation._mpy)
safe("float type", lambda: "single (32-bit)" if 1e300 == float("inf") else "double (64-bit)")
safe("ESP-IDF version", lambda: getattr(esp32, "idf_version", lambda: "n/a")()
     if esp32 else "n/a")

# ---------------------------------------------------------------- CPU
section("CPU / chip")
safe("CPU freq", lambda: "{} MHz".format(machine.freq() // 1000000))
safe("Unique ID", lambda: binascii.hexlify(machine.unique_id()).decode())
safe("Reset cause", lambda: {
    machine.PWRON_RESET: "PWRON_RESET",
    machine.HARD_RESET: "HARD_RESET",
    machine.WDT_RESET: "WDT_RESET",
    machine.DEEPSLEEP_RESET: "DEEPSLEEP_RESET",
    machine.SOFT_RESET: "SOFT_RESET",
}.get(machine.reset_cause(), machine.reset_cause()))
safe("Wake reason", lambda: machine.wake_reason())
if esp32:
    safe("Core temperature", lambda: "{:.1f} C".format(esp32.mcu_temperature()))
    safe("Hall sensor", lambda: esp32.hall_sensor())  # not on S3, expected n/a
safe("Uptime (ms)", lambda: time.ticks_ms())

# ---------------------------------------------------------------- RAM
section("RAM")
gc.collect()
free = gc.mem_free()
alloc = gc.mem_alloc()
show("MicroPython heap total", fmt_bytes(free + alloc))
show("  allocated", fmt_bytes(alloc))
show("  free", fmt_bytes(free))
if esp32 and hasattr(esp32, "idf_heap_info"):
    for name in ("HEAP_DATA", "HEAP_EXEC"):
        const = getattr(esp32, name, None)
        if const is None:
            continue
        try:
            regions = esp32.idf_heap_info(const)
        except Exception as e:
            show(name, "n/a ({})".format(e))
            continue
        print()
        print("ESP-IDF {} regions (total, free, largest free block, min free ever):".format(name))
        tot = fr = 0
        for i, r in enumerate(regions):
            print("  [{}] {:>9} {:>9} {:>9} {:>9}".format(i, r[0], r[1], r[2], r[3]))
            tot += r[0]
            fr += r[1]
        show("  sum total", fmt_bytes(tot))
        show("  sum free", fmt_bytes(fr))
        if name == "HEAP_DATA":
            big = [r for r in regions if r[0] > 1024 * 1024]
            if big:
                show("  PSRAM detected", "yes, ~{}".format(fmt_bytes(big[0][0])))
            else:
                show("  PSRAM detected", "no region > 1 MiB (PSRAM may be off/absent)")

# ---------------------------------------------------------------- flash
section("Flash (ROM)")
if esp:
    safe("Flash size (chip)", lambda: fmt_bytes(esp.flash_size()))
    safe("Flash user start", lambda: hex(esp.flash_user_start()))
if esp32 and hasattr(esp32, "Partition"):
    try:
        parts = esp32.Partition.find(esp32.Partition.TYPE_APP) + \
                esp32.Partition.find(esp32.Partition.TYPE_DATA)
        print()
        print("Partition table (type, subtype, address, size, label, encrypted):")
        for p in parts:
            t, st, addr, size, label, enc = p.info()
            print("  type={} sub={:>2} addr=0x{:06x} size={:>9} ({:>6.0f} KiB) {} enc={}".format(
                t, st, addr, size, size / 1024, label, enc))
        try:
            cur = esp32.Partition(esp32.Partition.RUNNING)
            show("Running partition", cur.info()[4])
        except Exception as e:
            show("Running partition", "n/a ({})".format(e))
    except Exception as e:
        show("Partitions", "n/a ({})".format(e))

# ---------------------------------------------------------------- filesystem
section("Filesystem")
for mp in ("/", "/flash", "/sd"):
    try:
        s = os.statvfs(mp)
        total = s[0] * s[2]
        freeb = s[0] * s[3]
        show(mp + " block size", s[0])
        show(mp + " total", fmt_bytes(total))
        show(mp + " free", fmt_bytes(freeb))
        show(mp + " used", fmt_bytes(total - freeb))
    except OSError:
        pass
try:
    print()
    print("Root directory:")
    for name in os.listdir("/"):
        print("  " + name)
except Exception as e:
    show("listdir", e)

# ---------------------------------------------------------------- NVS
if esp32 and hasattr(esp32, "NVS"):
    section("Non-volatile storage")
    try:
        esp32.NVS("board_info")
        show("NVS", "accessible")
    except Exception as e:
        show("NVS", "n/a ({})".format(e))

# ---------------------------------------------------------------- network
section("Network / radio")
if network:
    try:
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        show("WiFi STA MAC", binascii.hexlify(sta.config("mac"), ":").decode())
        safe("WiFi hostname", lambda: network.hostname())
        safe("WiFi TX power", lambda: sta.config("txpower"))
        ap = network.WLAN(network.AP_IF)
        show("WiFi AP MAC", binascii.hexlify(ap.config("mac"), ":").decode())
        print()
        print("Scanning WiFi networks (a few seconds)...")
        nets = sta.scan()
        show("Networks found", len(nets))
        for n in sorted(nets, key=lambda x: -x[3])[:10]:
            try:
                ssid = n[0].decode()
            except Exception:
                ssid = str(n[0])
            print("  {:<24} ch={:>2} rssi={:>4} dBm".format(ssid, n[2], n[3]))
        sta.active(False)
    except Exception as e:
        show("WiFi", "n/a ({})".format(e))
try:
    import bluetooth
    ble = bluetooth.BLE()
    ble.active(True)
    show("Bluetooth LE", "available")
    try:
        show("BLE MAC", binascii.hexlify(ble.config("mac")[1], ":").decode())
    except Exception as e:
        show("BLE MAC", "n/a ({})".format(e))
    ble.active(False)
except Exception as e:
    show("Bluetooth LE", "n/a ({})".format(e))

# ---------------------------------------------------------------- pins / buses
section("Pins, buses and peripherals")
try:
    from machine import Pin
    ok_pins = []
    for n in range(0, 49):
        try:
            Pin(n, Pin.IN)
            ok_pins.append(n)
        except Exception:
            pass
    show("Usable GPIO numbers", ok_pins)
except Exception as e:
    show("GPIO probe", e)

try:
    show("Board pin names", [n for n in dir(machine.Pin.board)
                             if not n.startswith("_")])
except Exception:
    show("Board pin names", "n/a (no Pin.board in this build)")

try:
    from machine import ADC
    adc_ok = []
    for n in range(1, 21):  # ADC1: GPIO1-10, ADC2: GPIO11-20 on S3
        try:
            a = ADC(machine.Pin(n))
            adc_ok.append((n, a.read_u16()))
        except Exception:
            pass
    show("ADC pins (gpio, raw u16)", adc_ok)
except Exception as e:
    show("ADC", e)

try:
    from machine import I2C
    i2c_found = {}
    # try the common default bus, ignoring failures
    for (scl, sda) in ((9, 8), (2, 1), (48, 47), (22, 21)):
        try:
            i2c = I2C(0, scl=machine.Pin(scl), sda=machine.Pin(sda), freq=100000)
            found = i2c.scan()
            if found:
                i2c_found["SCL{}/SDA{}".format(scl, sda)] = [hex(a) for a in found]
        except Exception:
            pass
    show("I2C devices found", i2c_found if i2c_found else "none on tried pairs")
except Exception as e:
    show("I2C scan", e)

for mod in ("neopixel", "dht", "onewire", "ds18x20", "espnow", "esp32",
            "machine", "framebuf", "ssl", "socket", "json", "asyncio",
            "usb", "usb.device", "lcd160cr", "btree", "cryptolib",
            "hashlib", "deflate", "vfs", "uctypes", "micropython"):
    try:
        __import__(mod)
        mark = "yes"
    except ImportError:
        mark = "no"
    print("  module {:<14}: {}".format(mod, mark))

# ---------------------------------------------------------------- micropython
section("MicroPython runtime")
try:
    import micropython
    print("micropython.mem_info():")
    micropython.mem_info()
    print()
    print("micropython.qstr_info():")
    micropython.qstr_info()
    safe("opt_level", lambda: micropython.opt_level())
except Exception as e:
    show("micropython", e)

print()
print("Builtin modules (help('modules')):")
try:
    help("modules")
except Exception as e:
    show("help", e)

print()
print("Done.")
