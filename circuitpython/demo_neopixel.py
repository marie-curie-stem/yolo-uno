import time
import board
import neopixel

# 1. Initialize the onboard NeoPixel on GPIO45 (using board.IO45 for safety)
# Brightness is set to 0.2 (20%) so it isn't blindingly bright.
pixel = neopixel.NeoPixel(board.IO45, 1, brightness=0.2, auto_write=False)

def wheel(pos):
    """Generate rainbow colors across 0-255 positions."""
    if pos < 85:
        return (int(pos * 3), int(255 - pos * 3), 0)
    elif pos < 170:
        pos -= 85
        return (int(255 - pos * 3), 0, int(pos * 3))
    else:
        pos -= 170
        return (0, int(pos * 3), int(255 - pos * 3))

# 2. Smoothly cycle colors in a loop
counter = 0
while True:
    pixel[0] = wheel(counter & 255)
    pixel.show()
    counter = (counter + 1) % 256
    time.sleep(0.02)