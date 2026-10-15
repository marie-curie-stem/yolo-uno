from utility import say
from setting import *

DEFAULT_I2C_ADDRESS = 0x25

# R/W registers
REG_RESET = const(0)
REG_CALIB = const(2)

# Read-only registers
REG_FW_VERSION = const(8)
REG_WHO_AM_I = const(9)
REG_DECIBEL = const(10)
REG_DECIBEL_MIN = const(11)
REG_DECIBEL_MAX = const(12)


class SoundLevelSensor:
    def __init__(self, i2c_bus, address=DEFAULT_I2C_ADDRESS):
        self._i2c = i2c_bus
        self._addr = address
        self.decibel = 0
        self.decibel_max = 0
        self.decibel_min = 0

        # check connection
        try:
            who_am_i = self._read_8(REG_WHO_AM_I)
        except OSError:
            who_am_i = 0

        if who_am_i != DEFAULT_I2C_ADDRESS:
            say("Sound level module not found")
        else:
            say("Sound level module init done")

    def fw_version(self):
        return self._read_8(REG_FW_VERSION)

    def read_decibel(self):
        self.decibel = self._read_8(REG_DECIBEL)
        return self.decibel

    def read_decibel_max(self):
        self.decibel_max = self._read_8(REG_DECIBEL_MAX)
        return self.decibel_max

    def read_decibel_min(self):
        self.decibel_min = self._read_8(REG_DECIBEL_MIN)
        return self.decibel_min

    def reset(self):
        self._write_8(REG_RESET, 0)

    # def calibrate(self, calibrate_value):
    #     self._write_8_signed(REG_CALIB, calibrate_value)
    def calibrate(self, calibrate_value):
        if not -32768 <= calibrate_value <= 32767:
            raise ValueError("Giá trị phải nằm trong khoảng [-32768, 32767]")
        
        calibrate_value = calibrate_value * 10;

        # Convert to two bytes in little-endian format
        low_byte = calibrate_value & 0xFF
        high_byte = (calibrate_value >> 8) & 0xFF
        data_bytes = bytes([low_byte, high_byte])

        print(data_bytes.hex())  # prints like: 'b0fb'

        self._i2c.writeto_mem(self._addr, REG_CALIB, data_bytes)

    # ---------- I2C utility methods ----------

    def _write_8_signed(self, register, data):
        # Allow signed input, convert to unsigned 8-bit
        self._i2c.writeto_mem(self._addr, register, bytes([data & 0xFF]))

    def _read_8(self, register):
        self._i2c.writeto(self._addr, bytes([register]))
        result = self._i2c.readfrom(self._addr, 1)
        return result[0]

    def _read_8_array(self, register, result_array):
        l = len(result_array)
        self._i2c.writeto(self._addr, bytes([register]))
        in_buffer = self._i2c.readfrom(self._addr, l)
        for i in range(l):
            result_array[i] = in_buffer[i]