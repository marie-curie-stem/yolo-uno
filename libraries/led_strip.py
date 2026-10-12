import machine, math, random, neopixel, time
from machine import Pin
from setting import *
from utility import *
import asyncio

class Led_Strip:
    def __init__(self, pin, NUM_PIXELS):
        self.NUM_PIXELS = NUM_PIXELS
        self.np = neopixel.NeoPixel(Pin(pin),self.NUM_PIXELS)

    def hex_to_rgb(self,color):
        color = color.lstrip('#')
        lv = len(color)
        return tuple(int(color[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))

    def set_hex_color(self,color):
        for j in range(self.NUM_PIXELS):
            self.np[j] = self.hex_to_rgb(color)
            self.np.write()

    def set_all(self,color):
        for j in range(self.NUM_PIXELS):
            self.np[j] = color
            self.np.write()

    async def wipe_effect(self):
        for i in range(self.NUM_PIXELS):
            self.np[i] = (255, 255, 255)
            self.np.write()
            await asyncio.sleep_ms(100)
        for i in range(self.NUM_PIXELS):
            self.np[i] = (0, 0, 0)
            self.np.write()
            await asyncio.sleep_ms(100)

    def show_index_led(self, index, color, delay=None):

      if index == 0:
            for j in range(self.NUM_PIXELS):
                self.np[j] = color
            self.np.write()
      elif (index > 0) and (index <= self.NUM_PIXELS) :
            self.np[index - 1] = color
            self.np.write()
      if delay != None:
            time.sleep(delay)
            if index == 0:
                for j in range(self.NUM_PIXELS):
                    self.np[j] = (0, 0, 0)
                self.np.write()
            elif (index > 0) and (index <= self.NUM_PIXELS) :
                self.np[index - 1] = (0, 0, 0)
                self.np.write()
    
    async def dim_effect(self):
        RED = 0
        GREEN = 0
        BLUE = 0
        for i in range(3):
            if i == 0:
                for j in range(255):
                    RED += 1
                    color = (RED, 0, 0)
                    self.set_all(color)
                    await asyncio.sleep_ms(10)
                for k in range(255):
                    RED += -1
                    color = (RED, 0, 0)
                    self.set_all(color)
                    await asyncio.sleep_ms(10)
            if i == 1:
                for j in range(255):
                    GREEN += 1
                    color = (0, GREEN, 0)
                    self.set_all(color)
                    await asyncio.sleep_ms(10)
                for k in range(255):
                    GREEN += -1
                    color = (0, GREEN, 0)
                    self.set_all(color)
                    await asyncio.sleep_ms(10)
            if i == 2:
                for j in range(255):
                    BLUE += 1
                    color = (0, 0, BLUE)
                    self.set_all(color)
                    await asyncio.sleep_ms(10)
                for k in range(255):
                    BLUE += -1
                    color = (0, 0, BLUE)
                    self.set_all(color)
                    await asyncio.sleep_ms(10)

    async def twinkle_effect(self):
        for k in range(3):  
            for i in range (self.NUM_PIXELS):
                pixel = random.randint(0, self.NUM_PIXELS - 1)
                Random = random.randint(0, 255)
                self.np[pixel] = (Random, Random, Random)
                self.np.write()
                await asyncio.sleep_ms(100)
                color = (0,0,0)
                self.set_all(color)

    async def spakle_effect(self):
        for k in range(2):
            for i in range (self.NUM_PIXELS):
                pixel = random.randint(1, self.NUM_PIXELS - 1)
                self.np[pixel] = (255, 255, 255)
                self.np.write()  
                await asyncio.sleep_ms(100)
            self.np[pixel] = (0, 0, 0)
            self.np.write()

    async def theaterChase_effect(self):
        for j in range(10):
            for q in range(3):
                for i in range(0, self.NUM_PIXELS, 3):
                    self.np[i-q] = (255,0,0)
                self.np.write()
                await asyncio.sleep_ms(100)
                for i in range(0, self.NUM_PIXELS, 3):
                    self.np[i-q] = (0,0,0)

    async def bounce_effect(self):
        n = self.np.n
        for i in range(4 * n):
            for j in range(n):
                self.np[j] = (0, 0, 128)
            if (i // n) % 2 == 0:
                self.np[i % n] = (255, 255, 255)
            else:
                self.np[n - 1 - (i % n)] = (255, 255, 255)
            self.np.write()
            await asyncio.sleep_ms(100)

    async def firework_effect(self):
        for i in range(20,5,-5):
            for j in range(self.NUM_PIXELS-i):
                self.np[j] = (150+(j*5),100+(j*5),50+(j*5))
                self.np.write()
                await asyncio.sleep_ms(300)
            color = (0,0,0)
            self.set_all(color)
            self.np[self.NUM_PIXELS-i] = (255,255,255)
            self.np[self.NUM_PIXELS-(i+2)] = (0,255,0)
            self.np[self.NUM_PIXELS-(i+1)] = (0,255,0)
            self.np[self.NUM_PIXELS-(i-2)] = (0,255,0)    
            self.np[self.NUM_PIXELS-(i-1)] = (0,255,0)
            self.np.write()
            await asyncio.sleep_ms(200)
            self.np[self.NUM_PIXELS-(i+4)] = (255,255,0)
            self.np[self.NUM_PIXELS-(i+3)] = (255,255,0)
            self.np[self.NUM_PIXELS-(i-4)] = (255,255,0)
            self.np[self.NUM_PIXELS-(i-3)] = (255,255,0)
            self.np.write()
            await asyncio.sleep_ms(200)
            self.np[self.NUM_PIXELS-(i+6)] = (0,0,255)
            self.np[self.NUM_PIXELS-(i+5)] = (0,0,255)
            self.np[self.NUM_PIXELS-(i-6)] = (0,0,255)
            self.np[self.NUM_PIXELS-(i-5)] = (0,0,255)
            self.np.write()
            await asyncio.sleep_ms(1000)
            color = (0,0,0)
            self.set_all(color)

    def wheel(self,pos):
        if pos < 0 or pos > 255:
            return (0, 0, 0)
        if pos < 85:
            return (255 - pos * 3, pos * 3, 0)
        if pos < 170:
            pos -= 85
            return (0, 255 - pos * 3, pos * 3)
        pos -= 170
        return (pos * 3, 0, 255 - pos * 3)

    async def rainbow_effect(self):
        for j in range(255):
            for i in range(self.NUM_PIXELS):
                rc_index = (i * 256 // self.NUM_PIXELS) + j
                self.np[i] = self.wheel(rc_index & 255)
            self.np.write()
            await asyncio.sleep_ms(1)

    async def cycle_effect(self):
        n = self.np.n
        for i in range(4 * n):
            for j in range(n):
                self.np[j] = (0, 0, 0)
            self.np[i % n] = (255, 255, 255)
            self.np.write()
            await asyncio.sleep_ms(25)

    def set_effect(self,i):
        switcher={
        1:self.wipe_effect(),
        2:self.dim_effect(),
        3:self.twinkle_effect(),
        4:self.spakle_effect(),
        5:self.theaterChase_effect(),
        6:self.bounce_effect(),
        7:self.firework_effect(),
        8:self.rainbow_effect(),
        9:self.cycle_effect()
        }
        return switcher.get(i)

    def clear(self):
        color = (0,0,0)
        self.set_all(color)


