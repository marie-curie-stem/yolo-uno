import machine, time, struct
from micropython import const
from machine import SoftI2C, Pin

from setting import *
from utility import *
#const = lambda x:x

_COMMAND_BIT = const(0x80)

_REGISTER_ENABLE = const(0x00)
_REGISTER_ATIME = const(0x01)

_REGISTER_AILT = const(0x04)
_REGISTER_AIHT = const(0x06)

_REGISTER_ID = const(0x12)

_REGISTER_APERS = const(0x0c)

_REGISTER_CONTROL = const(0x0f)

_REGISTER_SENSORID = const(0x12)

_REGISTER_STATUS = const(0x13)
_REGISTER_CDATA = const(0x14)
_REGISTER_RDATA = const(0x16)
_REGISTER_GDATA = const(0x18)
_REGISTER_BDATA = const(0x1a)

_ENABLE_AIEN = const(0x10)
_ENABLE_WEN = const(0x08)
_ENABLE_AEN = const(0x02)
_ENABLE_PON = const(0x01)

_GAINS = (1, 4, 16, 60)
_CYCLES = (0, 1, 2, 3, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60)

COLOR = {
    'r': 0 ,
    'g': 1 ,
    'b': 2 ,
    'd': 3 ,
    'w': 4 ,
    'y': 5
}

class TCS34725:
    def __init__(self, address=0x29):
        self.address = address
        try:
            self.i2c = machine.SoftI2C(scl=machine.Pin(SCL_PIN), sda=machine.Pin(SDA_PIN))
            #self.i2c = TCS34725(i2c, self.address)
        except:
            print('TCS34725 not found')
            raise Exception('TCS34725 not found')

        self._active = False
        self.integration_time(2.4)
        sensor_id = self.sensor_id()
        if sensor_id not in (0x44, 0x10):
            raise RuntimeError("wrong sensor id 0x{:x}".format(sensor_id))


    def _register8(self, register, value=None):
        register |= _COMMAND_BIT
        if value is None:
            return self.i2c.readfrom_mem(self.address, register, 1)[0]
        data = struct.pack('<B', value)
        self.i2c.writeto_mem(self.address, register, data)

    def _register16(self, register, value=None):
        register |= _COMMAND_BIT
        if value is None:
            data = self.i2c.readfrom_mem(self.address, register, 2)
            return struct.unpack('<H', data)[0]
        data = struct.pack('<H', value)
        self.i2c.writeto_mem(self.address, register, data)

    def active(self, value=None):
        if value is None:
            return self._active
        value = bool(value)
        if self._active == value:
            return
        self._active = value
        enable = self._register8(_REGISTER_ENABLE)
        if value:
            self._register8(_REGISTER_ENABLE, enable | _ENABLE_PON)
            time.sleep_ms(3)
            self._register8(_REGISTER_ENABLE,
                enable | _ENABLE_PON | _ENABLE_AEN)
        else:
            self._register8(_REGISTER_ENABLE,
                enable & ~(_ENABLE_PON | _ENABLE_AEN))

    def sensor_id(self):
        return self._register8(_REGISTER_SENSORID)

    def integration_time(self, value=None):
        if value is None:
            return self._integration_time
        value = min(614.4, max(2.4, value))
        cycles = int(value / 2.4)
        self._integration_time = cycles * 2.4
        return self._register8(_REGISTER_ATIME, 256 - cycles)

    def gain(self, value):
        if value is None:
            return _GAINS[self._register8(_REGISTER_CONTROL)]
        if value not in _GAINS:
            raise ValueError("gain must be 1, 4, 16 or 60")
        return self._register8(_REGISTER_CONTROL, _GAINS.index(value))

    def _valid(self):
        return bool(self._register8(_REGISTER_STATUS) & 0x01)

    def read(self, raw=False):
        was_active = self.active()
        self.active(True)
        while not self._valid():
            time.sleep_ms(int(self._integration_time + 0.9))
        data = tuple(self._register16(register) for register in (
            _REGISTER_RDATA,
            _REGISTER_GDATA,
            _REGISTER_BDATA,
            _REGISTER_CDATA,
        ))
        self.active(was_active)
        if raw:
            return data
        return self._temperature_and_lux(data)

    def _temperature_and_lux(self, data):
        r, g, b, c = data
        x = -0.14282 * r + 1.54924 * g + -0.95641 * b
        y = -0.32466 * r + 1.57837 * g + -0.73191 * b
        z = -0.68202 * r + 0.77073 * g +  0.56332 * b
        d = x + y + z
        n = (x / d - 0.3320) / (0.1858 - y / d)
        cct = 449.0 * n**3 + 3525.0 * n**2 + 6823.3 * n + 5520.33
        return cct, y

    def threshold(self, cycles=None, min_value=None, max_value=None):
        if cycles is None and min_value is None and max_value is None:
            min_value = self._register16(_REGISTER_AILT)
            max_value = self._register16(_REGISTER_AILT)
            if self._register8(_REGISTER_ENABLE) & _ENABLE_AIEN:
                cycles = _CYCLES[self._register8(_REGISTER_APERS) & 0x0f]
            else:
                cycles = -1
            return cycles, min_value, max_value
        if min_value is not None:
            self._register16(_REGISTER_AILT, min_value)
        if max_value is not None:
            self._register16(_REGISTER_AIHT, max_value)
        if cycles is not None:
            enable = self._register8(_REGISTER_ENABLE)
            if cycles == -1:
                self._register8(_REGISTER_ENABLE, enable & ~(_ENABLE_AIEN))
            else:
                self._register8(_REGISTER_ENABLE, enable | _ENABLE_AIEN)
                if cycles not in _CYCLES:
                    raise ValueError("invalid persistence cycles")
                self._register8(_REGISTER_APERS, _CYCLES.index(cycles))

    def interrupt(self, value=None):
        if value is None:
            return bool(self._register8(_REGISTER_STATUS) & _ENABLE_AIEN)
        if value:
            raise ValueError("interrupt can only be cleared")
        self.i2c.writeto(self.address, b'\xe6')


    def html_rgb(self):
        r, g, b, c = self.read(True)
        #print(c)
        # if c == 0:
        #     c = 1
        # Avoid divide by zero errors ... if clear = 0 return black
        if c == 0:
            return (0, 0, 0)
        red = int(pow((int((r/c) * 256) / 255), 2.5) * 255)
        green = int(pow((int((g/c) * 256) / 255), 2.5) * 255)
        blue = int(pow((int((b/c) * 256) / 255), 2.5) * 255)

        # Handle possible 8-bit overflow
        if red > 255:
            red = 255
        if green > 255:
            green = 255
        if blue > 255:
            blue = 255
        return (red, green, blue)        
        #return red, green, blue

    def html_hex(self):
        r, g, b = self.html_rgb()
        return "{0:02x}{1:02x}{2:02x}".format(int(r),int(g),int(b))

    def read_color(self, color):
        '''
        To read value R of color sensor at port 0: 
        color_sensor.read(0, 'r')
        range of value return: 0 - 255 (type int)
        '''
        return self.html_rgb()[COLOR[color]]

    def detect(self, color, limit = 40):
        '''
        Maybe the readings from the sensor will be different: white (45, 45, 45) or red (90, 0, 0)
        Below is the lowest value the sensor reads for each color:
        Color:  red (45, 0, 0)  
                green(0, 45, 0)
                blue (0, 45, 0)
                dark (0, 0, 0)
                white(16, 16, 16)
                yellow (30, 15, 4)
        '''
        r, g, b = self.html_rgb()
        if max(r, g, b, limit) == r:
            #red
            return 0 == COLOR[color]
        elif max(r, g, b, limit) == g:
            #green
            return 1 == COLOR[color]
        elif max(r, g, b, limit) == b:
            #blue
            return 2 == COLOR[color]
        elif max(r, g, b) < (limit/3):
            #black
            return 3 == COLOR[color]
        elif min(r, g, b) > (limit/3):
            #white
            return 4 == COLOR[color]
        elif ((26 < r < 36) and (14 < g < 24) and (0 < b < 8)):
            #yellow
            return 5 == COLOR[color]
        else:
            #other colors
            return False