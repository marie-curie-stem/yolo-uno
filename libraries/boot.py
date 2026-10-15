# This file is executed on every boot (including wake-boot from deepsleep)
import os, time, gc, esp, sys, asyncio
from machine import Pin, reset
from neopixel import NeoPixel

from setting import *
from utility import *
from yolo_uno import *

esp.osdebug(None)

print('Firmware version:',  VERSION)

def stop_all():
  pass

if PRODUCT_TYPE == 'yolo-uno':
  # The NOBLE firmware variant is built without the bluetooth stack; there the
  # ble module is a no-op stub whose start() says so and does nothing else.
  # The except is a belt-and-braces guard for images built without either one.
  try:
    from ble import *
    ble.start()
  except ImportError:
    print('Bluetooth disabled in this firmware')