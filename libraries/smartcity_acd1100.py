from yolo_uno import *
import time
from machine import SoftI2C, Pin

ACD10_DEFAULT_ADDRESS = 0x2A

# Error Codes
ACD10_OK = 0x00
ACD10_NOT_READY = 0x10
ACD10_REQUEST_ERROR = 0x11
ACD10_CRC_ERROR = 0x12

# Calibration Modes
ACD10_CALIBRATE_MANUAL = 0x00
ACD10_CALIBRATE_AUTO = 0x01


class ACD1100:
    def __init__(self, i2c_bus, address=ACD10_DEFAULT_ADDRESS):
        self.i2c = i2c_bus
        self.address = address
        self._last_read = 0
        self._concentration = 0
        self._temperature = 0
        self._preheat_start = time.ticks_ms()
        self._request_time = 80
        self._request_start = 0
        self._error = 0

    def begin(self):
        if not self.is_connected():
            return False
        self._last_read = 0
        self._concentration = 0
        self._temperature = 0
        self._request_time = 80
        self._request_start = 0
        return True

    def is_connected(self):
        try:
            self.i2c.writeto(self.address, b'')
            return True
        except:
            return False

    def preheat_done(self):
        return self.preheat_millis_left() == 0

    def preheat_millis_left(self):
        elapsed = time.ticks_diff(time.ticks_ms(), self._preheat_start)
        return max(0, 120000 - elapsed)

    def request_sensor(self):
        self._request_start = time.ticks_ms()
        return self._command(bytes([0x03, 0x00]))

    def request_ready(self):
        if self._request_start == 0:
            return False
        return time.ticks_diff(time.ticks_ms(), self._request_start) > self._request_time

    def read_sensor(self):
        if not self.request_ready():
            return ACD10_NOT_READY
        buf = self._request(9)
        if buf is None:
            return ACD10_REQUEST_ERROR

        if buf[2] != self._crc8(buf[0:2]) or buf[5] != self._crc8(buf[3:5]) or buf[8] != self._crc8(buf[6:8]):
            return ACD10_CRC_ERROR

        self._concentration = (buf[0] << 24) | (buf[1] << 16) | (buf[3] << 8) | buf[4]
        self._temperature = (buf[6] << 8) | buf[7]
        self._last_read = time.ticks_ms()
        return ACD10_OK

    def get_co2_concentration(self):
        self._command(bytes([0x03, 0x00]))
        buf = self._request(9)
        if buf is None:
            print("no data")
            return ACD10_REQUEST_ERROR

        if buf[2] != self._crc8(buf[0:2]) or buf[5] != self._crc8(buf[3:5]) or buf[8] != self._crc8(buf[6:8]):
            print("crc error")
            return ACD10_CRC_ERROR

        return (buf[0] << 24) | (buf[1] << 16) | (buf[3] << 8) | buf[4]

    def get_temperature(self):
        return self._temperature

    def last_read(self):
        return self._last_read

    def set_request_time(self, ms=80):
        self._request_time = ms

    def get_request_time(self):
        return self._request_time

    def set_calibration_mode(self, mode):
        if mode > ACD10_CALIBRATE_AUTO:
            return False
        buf = bytearray([0x53, 0x06, 0x00, mode, 0])
        buf[4] = self._crc8(buf[2:4])
        return self._command(buf) == 0

    def read_calibration_mode(self):
        self._command(bytes([0x53, 0x06]))
        resp = self._request(3)
        return resp[1] if resp else 0xFF

    def set_manual_calibration(self, value):
        if not (400 <= value <= 5000):
            return False
        buf = bytearray([0x52, 0x04, (value >> 8) & 0xFF, value & 0xFF, 0])
        buf[4] = self._crc8(buf[2:4])
        return self._command(buf) == 0

    def read_manual_calibration(self):
        self._command(bytes([0x52, 0x04]))
        buf = self._request(3)
        return (buf[0] << 8) | buf[1] if buf else 0xFFFF

    def factory_reset(self):
        self._command(bytes([0x52, 0x02, 0x00]))

    def read_factory_set(self):
        self._command(bytes([0x52, 0x02]))
        buf = self._request(3)
        return buf and buf[0] == 0x00 and buf[1] == 0x01

    def read_firmware_version(self):
        self._command(bytes([0xD1, 0x00]))
        return bytes(self._request(10)).decode("utf-8")

    def read_sensor_code(self):
        self._command(bytes([0xD2, 0x01]))
        return bytes(self._request(10)).decode("utf-8")

    def get_last_error(self):
        return self._error

    def _command(self, data: bytes):
        try:
            self.i2c.writeto(self.address, data)
            return 0
        except Exception as e:
            self._error = 1
            return 1

    def _request(self, size):
        try:
            return self.i2c.readfrom(self.address, size)
        except Exception as e:
            self._error = 2
            return None

    def _crc8(self, data):
        crc = 0xFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if (crc & 0x80):
                    crc = (crc << 1) ^ 0x31
                else:
                    crc <<= 1
                crc &= 0xFF
        return crc
