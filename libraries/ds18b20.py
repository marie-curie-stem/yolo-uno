import machine, onewire, ds18x20
 
class DS18B20:
    def __init__(self, pin):
        self._pin = machine.Pin(pin)
        self._sensor = ds18x20.DS18X20(onewire.OneWire(self._pin))
        self._roms = self._sensor.scan()
        print('Found DS18B20 devices: ', self._roms)

    def read(self, index=0):
        if index > len(self._roms):
            return
        self._sensor.convert_temp()
        return self._sensor.read_temp(self._roms[index])