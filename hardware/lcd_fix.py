# lcd_fix.py - let the OhStem lcd1602 library talk to a backpack at 0x27
#
# The OhStem library hard-codes address 0x21. Your backpack is at 0x27.
# Import this file FIRST; it redirects 0x21 -> 0x27 for the SoftI2C bus.
#
#   import lcd_fix          # must come before "from lcd1602 import *"
#   from lcd1602 import *
#   from yolo_uno import *
#   ...

import machine

LIB_ADDR = 0x21      # address the OhStem library uses
REAL_ADDR = 0x27     # address of your backpack

_RealSoftI2C = machine.SoftI2C


class _RemapI2C:
    def __init__(self, *args, **kwargs):
        self._real = _RealSoftI2C(*args, **kwargs)

    def _map(self, addr):
        return REAL_ADDR if addr == LIB_ADDR else addr

    def writeto(self, addr, buf, *a, **k):
        return self._real.writeto(self._map(addr), buf, *a, **k)

    def readfrom(self, addr, n, *a, **k):
        return self._real.readfrom(self._map(addr), n, *a, **k)

    def readfrom_into(self, addr, buf, *a, **k):
        return self._real.readfrom_into(self._map(addr), buf, *a, **k)

    def scan(self):
        return [LIB_ADDR if a == REAL_ADDR else a for a in self._real.scan()]

    def __getattr__(self, name):
        return getattr(self._real, name)


machine.SoftI2C = _RemapI2C