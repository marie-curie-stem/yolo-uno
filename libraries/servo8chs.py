from micropython import const
from machine import SoftI2C
from yolo_uno import *

motion_servos_pos = {}

SV_DEFAULT_I2C_ADDRESS = 0x31

SV_REG_SERVO1 = const(0)
SV_REG_SERVO2 = const(2)
SV_REG_SERVO3 = const(4)
SV_REG_SERVO4 = const(6)
SV_REG_SERVO5 = const(8)
SV_REG_SERVO6 = const(10)
SV_REG_SERVO7 = const(12)
SV_REG_SERVO8 = const(14)
SV_REG_SERVOS = [SV_REG_SERVO1, SV_REG_SERVO2, SV_REG_SERVO3, SV_REG_SERVO4, SV_REG_SERVO5, SV_REG_SERVO6, SV_REG_SERVO7, SV_REG_SERVO8]

# Read-only registers
SV_REG_FW_VERSION     = const(16)
SV_REG_WHO_AM_I       = const(18)

class Servo8chs():
    def __init__(self, address=SV_DEFAULT_I2C_ADDRESS):
        self._i2c = SoftI2C(scl=SCL_PIN, sda=SDA_PIN, freq=100000)
        self._addr = address
        self._speeds = [0, 0]

        # check i2c connection
        try:
            who_am_i = self._read_8(SV_REG_WHO_AM_I)
        except OSError:
            who_am_i = 0

        if who_am_i != SV_DEFAULT_I2C_ADDRESS:
            raise RuntimeError("Servo8chs kit module not found. Expected: " + str(address) + ", scanned: " + str(who_am_i))
        else:
            print(who_am_i)
            self.motion_servos_pos = {}
      
    def fw_version(self):
        minor = self._read_8(SV_REG_FW_VERSION)
        major = self._read_8(SV_REG_FW_VERSION + 1)
        return("{}.{}".format(major, minor))
	
	#################### SERVO CONTROL ####################

    def set_servo(self, index, angle):
        angle = int(angle*180/180)
        self._write_16(SV_REG_SERVOS[index], angle)
        self.motion_servos_pos[index] = angle

    def set_servo_position(self, pin, next_position, speed=70):        
        if speed < 0:
            speed = 0
        elif speed > 100:
            speed = 100
        
        sleep = int(translate(speed, 0, 100, 100, 0))

        if pin in self.motion_servos_pos:
            current_position = self.motion_servos_pos[pin]
        else:
            current_position = 0
            self.set_servo(pin, 0) # first time control

        if next_position < current_position:
            for i in range(current_position, next_position, -1):
                self.set_servo(pin, i)
                time.sleep_ms(sleep)
        else:
            for i in range(current_position, next_position):
                self.set_servo(pin, i)
                time.sleep_ms(sleep)

    def move_servo_position(self, pin, angle):
        if pin in self.motion_servos_pos:
            current_position = self.motion_servos_pos[pin]
        else:
            current_position = 0
        next_position = current_position + angle
        if next_position < 0:
            next_position = 0
        if next_position > 180:
            next_position = 180
        self.set_servo(pin, next_position)

    #################### I2C COMMANDS ####################

    def _write_8(self, register, data):
        # Write 1 byte of data to the specified  register address.
        self._i2c.writeto_mem(self._addr, register, bytes([data]))

    def _write_8_array(self, register, data):
        # Write multiple bytes of data to the specified  register address.
        self._i2c.writeto_mem(self._addr, register, data)

    def _write_16(self, register, data):
        # Write a 16-bit little endian value to the specified register
        # address.
        self._i2c.writeto_mem(self._addr, register, bytes(
            [data & 0xFF, (data >> 8) & 0xFF]))

    def _write_16_array(self, register, data):
        # write an array of litte endian 16-bit values  to specified register address
        l = len(data)
        buffer = bytearray(2*l)
        for i in range(l):
            buffer[2*i] = data[i] & 0xFF
            buffer[2*i+1] = (data[i] >> 8) & 0xFF
        self._i2c.writeto_mem(self._addr, register, buffer)

    def _read_8(self, register):
        # Read and return a byte from  the specified register address.
        self._i2c.writeto(self._addr, bytes([register]))
        result = self._i2c.readfrom(self._addr, 1)
        return result[0]

    def _read_8_array(self, register, result_array):
        # Read and  saves into result_arrray a sequence of bytes
        # starting from the specified  register address.
        l = len(result_array)
        self._i2c.writeto(self._addr, bytes([register]))
        in_buffer = self._i2c.readfrom(self._addr, l)
        for i in range(l):
            result_array[i] = in_buffer[i]

    def _read_16(self, register):
        # Read and return a 16-bit signed little  endian value  from the
        # specified  register address.
        self._i2c.writeto(self._addr, bytes([register]))
        in_buffer = self._i2c.readfrom(self._addr, 2)
        raw = (in_buffer[1] << 8) | in_buffer[0]
        if (raw & (1 << 15)):  # sign bit is set
            return (raw - (1 << 16))
        else:
            return raw

    def _read_16_array(self, register, result_array):
        # Read and  saves into result_arrray a sequence of 16-bit little  endian
        # values  starting from the specified  register address.
        l = len(result_array)
        self._i2c.writeto(self._addr, bytes([register]))
        in_buffer = self._i2c.readfrom(self._addr, 2*l)
        for i in range(l):
            raw = (in_buffer[2*i+1] << 8) | in_buffer[2*i]
            if (raw & (1 << 15)):  # sign bit is set
                result_array[i] = (raw - (1 << 16))
            else:
                result_array[i] = raw

sv = Servo8chs()