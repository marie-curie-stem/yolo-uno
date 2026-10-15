# lcd_test.py - minimal 1602 LCD (PCF8574 backpack) test, no external library
# Yolo UNO: SDA=GPIO11, SCL=GPIO12, address 0x27
# Run:  import lcd_test

from machine import Pin, I2C
import time

ADDR = 0x27
i2c = I2C(0, scl=Pin(12), sda=Pin(11), freq=100000)

RS, EN, BL = 0x01, 0x04, 0x08   # RS bit, Enable bit, Backlight bit (RW stays 0)


def _write4(nibble, rs):
    data = (nibble << 4) | BL | (RS if rs else 0)
    i2c.writeto(ADDR, bytes([data | EN]))
    time.sleep_us(2)
    i2c.writeto(ADDR, bytes([data & ~EN]))
    time.sleep_us(50)


def _send(byte, rs):
    _write4(byte >> 4, rs)
    _write4(byte & 0x0F, rs)


def cmd(c):
    _send(c, 0)


def init():
    time.sleep_ms(50)
    for _ in range(3):          # force 8-bit mode, then switch to 4-bit
        _write4(0x03, 0)
        time.sleep_ms(5)
    _write4(0x02, 0)
    cmd(0x28)                   # 4-bit, 2 lines, 5x8 font
    cmd(0x0C)                   # display on, cursor off
    cmd(0x06)                   # increment cursor
    clear()


def clear():
    cmd(0x01)
    time.sleep_ms(3)


def put(text, row=0, col=0):
    cmd(0x80 | (0x40 * row) | col)
    for ch in text:
        _send(ord(ch), 1)


init()
put("Hello Yolo UNO", 0)
put("ESP32-S3  0x27", 1)
print("Text written. If the screen stays blank, adjust the contrast potentiometer.")