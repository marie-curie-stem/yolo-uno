from pins import Pins

class Anemometer:
    def __init__(self, pin=0):
        self.adc = Pins(pin)

    def read_raw(self):
        return self.adc.read_analog()

    def read_wind_speed(self, pin):
        self.adc = Pins(pin)
        speed_raw = 0
        for _ in range(100):
            speed_raw = speed_raw + self.read_raw()
        speed_raw = speed_raw / 100

        speed = speed_raw * 60 / 4095
        return round(speed, 1)
