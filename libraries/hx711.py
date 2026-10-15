from machine import Pin
from time import sleep_us
from time import ticks_ms, ticks_diff
from micropython import const

class HX711Exception(Exception):
    pass

class InvalidMode(HX711Exception):
    pass

class DeviceIsNotReady(HX711Exception):
    pass

class HX711:
    CHANNEL_A_128 = const(1)
    CHANNEL_A_64  = const(3)
    CHANNEL_B_32  = const(2)

    DATA_BITS = const(24)
    READY_TIMEOUT_MS = const(5000)

    def __init__(self, d_out, pd_sck, channel=CHANNEL_A_128):
        self.d_out = Pin(d_out, Pin.IN)
        self.pd_sck = Pin(pd_sck, Pin.OUT, value=0)
        self._channel = channel
        self.SCALE = 1.0
        self.offset = 0
        self._set_channel()

    def is_ready(self):
        return self.d_out.value() == 0

    def _wait_ready(self):
        start = ticks_ms()
        while not self.is_ready():
            if ticks_diff(ticks_ms(), start) > self.READY_TIMEOUT_MS:
                raise DeviceIsNotReady()
            sleep_us(50)

    @property
    def channel(self):
        if self._channel == self.CHANNEL_A_128:
            return ("A", 128)
        elif self._channel == self.CHANNEL_A_64:
            return ("A", 64)
        else:
            return ("B", 32)

    @channel.setter
    def channel(self, value):
        if value not in (self.CHANNEL_A_128, self.CHANNEL_A_64, self.CHANNEL_B_32):
            raise InvalidMode("Invalid channel mode")
        self._channel = value
        self._set_channel()

    def _set_channel(self):
        self._wait_ready()
        for _ in range(24):
            self.pd_sck.value(1)
            self.pd_sck.value(0)

        pulses = self._channel
        for _ in range(pulses):
            self.pd_sck.value(1)
            self.pd_sck.value(0)

    def _read_raw(self):
        self._wait_ready()

        raw = 0
        for _ in range(24):
            self.pd_sck.value(1)
            raw = (raw << 1) | self.d_out.value()
            self.pd_sck.value(0)

        self._set_channel()

        # Convert two's complement
        if raw & 0x800000:
            raw -= 0x1000000

        return raw

    def read_average(self, times=10):
        total = 0
        for _ in range(times):
            total += self._read_raw()
            sleep_us(200)
        return total / times

    def tare(self, times=16):
        self.offset = self.read_average(times)

    def set_scale(self, scale):
        self.SCALE = float(scale)

    def get_grams(self, times=8):
        value = self.read_average(times) - self.offset
        return value / self.SCALE

    def raw_value(self):
        return self._read_raw() - self.offset

    def power_off(self):
        self.pd_sck.value(1)
        sleep_us(60)

    def power_on(self):
        self.pd_sck.value(0)
        self._set_channel()

