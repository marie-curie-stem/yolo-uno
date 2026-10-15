# Circuitpython on the Yolo UNO

It does not exist yet, but

- A ticket is filed: https://github.com/AITT-VN/ohstem_arduino_board/issues/3
- You can try a similar for [YD-ESP32-S3 N16R8 by VCC-GND Studio](https://circuitpython.org/board/yd_esp32_s3_n16r8/) with also 8 GB PSRAM and 16 GB Flash

## Example for 1602 Display over i2c

Remember: `GPIO11` is `SDA` and `GPIO12` is `SCL`. 

![image 1602](../2%20Làm%20việc%20với%20module/Màn%20hình%20LCD1602/lcd1602_0x27.jpg)

``` py
import time
import board
import busio

# 1. Initialize I2C on GPIO11 (SDA) and GPIO12 (SCL)
# ESP32-S3 uses board.IO11 and board.IO12 in CircuitPython
i2c = busio.I2C(scl=board.GPIO12, sda=board.GPIO11)
I2C_ADDR = 0x27  # Change to 0x3F if your screen remains blank

# PCF8574 Control Bit Definitions
RS = 0x01         # Register Select (0 = Command, 1 = Data)
RW = 0x02         # Read/Write (0 = Write)
EN = 0x04         # Enable signal
BACKLIGHT = 0x08  # Backlight control

def write_i2c(val):
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto(I2C_ADDR, bytes([val]))
    finally:
        i2c.unlock()

def pulse_enable(val):
    write_i2c(val | EN)
    time.sleep(0.000001)
    write_i2c(val & ~EN)
    time.sleep(0.00005)

def send_nibble(nibble, mode=0):
    # D4-D7 map to upper 4 bits of PCF8574; include backlight
    val = (nibble << 4) | mode | BACKLIGHT
    write_i2c(val)
    pulse_enable(val)

def send_byte(value, mode=0):
    # Send high nibble, then low nibble (4-bit mode)
    send_nibble((value >> 4) & 0x0F, mode)
    send_nibble(value & 0x0F, mode)

def lcd_command(cmd):
    send_byte(cmd, mode=0)

def lcd_data(data):
    send_byte(data, mode=RS)

def lcd_init():
    time.sleep(0.05)
    # HD44780 4-bit initialization sequence
    send_nibble(0x03)
    time.sleep(0.0045)
    send_nibble(0x03)
    time.sleep(0.00015)
    send_nibble(0x03)
    send_nibble(0x02)  # Switch to 4-bit mode
    
    lcd_command(0x28)  # Function set: 2 lines, 5x7 dots
    lcd_command(0x0C)  # Display ON, Cursor OFF, Blink OFF
    lcd_command(0x06)  # Entry mode: Auto-increment cursor
    lcd_command(0x01)  # Clear display
    time.sleep(0.002)

def lcd_print(text):
    for char in text:
        if char == '\n':
            lcd_command(0xC0)  # Move cursor to the second line
        else:
            lcd_data(ord(char))

# 2. Initialize and write to the display
lcd_init()
lcd_print("Hello, ESP32-S3!\nCP 10.3 No Libs")

while True:
    time.sleep(1)
```
