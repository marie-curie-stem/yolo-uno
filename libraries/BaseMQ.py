## Ported from https://github.com/amperka/TroykaMQ
## Author: Alexey Tveritinov [kartun@yandex.ru]

from machine import Pin, ADC
from micropython import const
import time, asyncio
import asyncio
from math import exp, log

class BaseMQ(object):
    ## Measuring attempts in cycle
    MQ_SAMPLE_TIMES = const(5)

    ## Delay after each measurement, in ms
    MQ_CALIB_SAMPLE_INTERVAL = const(5000)

    MQ_SAMPLE_INTERVAL = const(3000)

    ## Heating period, in ms
    MQ_HEATING_PERIOD = const(60000)

    ## Cooling period, in ms
    MQ_COOLING_PERIOD = const(90000)

    ## This strategy measure values immideatly, so it might be inaccurate. Should be
    #  suitable for tracking dynamics, raither than actual values
    STRATEGY_FAST = const(1)

    ## This strategy measure values separatelly. For a single measurement
    #    MQ_SAMPLE_TIMES measurements are taken in interval MQ_SAMPLE_INTERVAL.
    #    I.e. for multi-data sensors, like MQ2 it would take a while to receive full data
    STRATEGY_ACCURATE = const(2)    

    ## Initialization. 
    #  @param pinData Data pin. Should be ADC pin
    #  @param pinHeater Pass -1 if heater connected to main power supply. Otherwise pass another pin capable of PWM
    #  @param boardResistance On troyka modules there is 10K resistor, on other boards could be other values
    #  @param baseVoltage Optionally board could run on 3.3 Volds, base voltage is 5.0 Volts. Passing incorrect values
    #  would cause incorrect measurements
    #  @param measuringStrategy Currently two main strategies are implemented:
    #  - STRATEGY_FAST = 1 In this case data would be taken immideatly. Could be unreliable
    #  - STRATEGY_ACCURATE = 2 In this case data would be taken MQ_SAMPLE_TIMES times with MQ_SAMPLE_INTERVAL delay
    #  For sensor with different gases it would take a while
    def __init__(self, pinData, pinHeater=-1, boardResistance = 10, baseVoltage = 3.3, measuringStrategy = STRATEGY_FAST):
        ## Heater is enabled
        self._heater = False
        ## Heater is enabled
        self._cooler = False
        ## Base resistance of module         
        self._ro = -1       

        self._useSeparateHeater = False
        self._baseVoltage = baseVoltage

        ## @var _lastMeasurement - when last measurement was taken
        self._lastMesurement = time.ticks_ms()
        self._rsCache = None
        self.dataIsReliable = False
        self.pinData = ADC(Pin(pinData, Pin.IN))
        self.pinData.atten(ADC.ATTN_11DB)
        self.pinData.width(ADC.WIDTH_12BIT)
        self.measuringStrategy = measuringStrategy
        self._boardResistance = boardResistance
        if pinHeater != -1:
            self.useSeparateHeater = True
            self.pinHeater = Pin(pinHeater, Pin.OUTPUT)

    ## Abstract method, should be implemented in specific sensor driver.
    #  Base RO differs for every sensor family
    def getRoInCleanAir(self):
        raise NotImplementedError("Please Implement this method")

    ## Sensor calibration
    #  @param ro For first time sensor calibration do not pass RO. It could be saved for
    #  later reference, to bypass calibration. For sensor calibration with known resistance supply value 
    #  received from pervious runs After calibration is completed @see _ro attribute could be stored for 
    #  speeding up calibration
    async def calibrate(self, ro=-1):
        if ro == -1:
            ro = 0
            print("Calibrating:")
            for i in range(0, self.MQ_SAMPLE_TIMES + 1):        
                print("Step {0}".format(i))
                ro += self.__calculateResistance__(self.pinData.read())
                await asyncio.sleep_ms(self.MQ_CALIB_SAMPLE_INTERVAL)
         
            ro = ro/(self.getRoInCleanAir() * self.MQ_SAMPLE_TIMES )
            print("Base resistance:{0}".format(ro))

        self._ro = ro
        self._stateCalibrate = True    

    ## Enable heater. Is not applicable for 3-wire setup
    def heaterPwrHigh(self):
        #digitalWrite(_pinHeater, HIGH)
        #_pinHeater(1)
        if self._useSeparateHeater:
            self._pinHeater.on()
            pass
        self._heater = True
        self._prMillis = time.ticks_ms()


    ## Move heater to energy saving mode. Is not applicable for 3-wire setup
    def heaterPwrLow(self):
        #analogWrite(_pinHeater, 75)
        self._heater = True
        self._cooler = True
        self._prMillis = time.ticks_ms()


    ## Turn off heater. Is not applicable for 3-wire setup
    def heaterPwrOff(self):
        if self._useSeparateHeater:
            self._pinHeater.off()
            pass
        #digitalWrite(_pinHeater, LOW)
        #_pinHeater(0)
        self._heater = False


    ## Measure sensor current resistance value, ere actual measurement is performed
    def __calculateResistance__(self, rawAdc):
        if rawAdc < 1:
            rawAdc = 1
        elif rawAdc >= 4000:
            rawAdc = 4000

        vrl = rawAdc*(self._baseVoltage / 4095)
        rsAir = (self._baseVoltage - vrl)/vrl*self._boardResistance
        return rsAir


    ## Data reading     
    # If data is taken frequently, data reading could be unreliable. Check @see dataIsReliable flag
    # Also refer to measuring strategy
    async def __readRs__(self):
        if self.measuringStrategy == self.STRATEGY_ACCURATE :            
                rs = 0
                for i in range(0, self.MQ_SAMPLE_TIMES + 1): 
                    rs += self.__calculateResistance__(self.pinData.read()-1)
                    await asyncio.sleep_ms(self.MQ_SAMPLE_INTERVAL)

                rs = rs/self.MQ_SAMPLE_TIMES
                self._rsCache = rs
                self.dataIsReliable = True
                self._lastMesurement = time.ticks_ms()                            

        else:
            rs = self.__calculateResistance__(self.pinData.read())
            self.dataIsReliable = False

        return rs


    async def readScaled(self, a, b):        
        return exp((log(await self.readRatio())-b)/a)


    async def readRatio(self):
        return (await self.__readRs__())/self._ro


    ## Checks if sensor heating is completed. Is not applicable for 3-wire setup
    def heatingCompleted(self):
        if (self._heater) and (not self._cooler) and (time.ticks_diff(time.ticks_ms(),self._prMillis) > MQ_HEATING_PERIOD):
            return True
        else:
            return False

    ## Checks if sensor cooling is completed. Is not applicable for 3-wire setup 
    def coolanceCompleted(self):
        if (self._heater) and (self._cooler) and (time.ticks_diff(time.ticks_ms(), self._prMillis) > MQ_COOLING_PERIOD):
            return True
        else:
            return False

    ## Starts sensor heating. @see heatingCompleted if heating is completed
    def cycleHeat(self):
        self._heater = False
        self._cooler = False
        self.heaterPwrHigh()
    #ifdef MQDEBUG
        print("Heated sensor")
    #endif #MQDEBUG
        pass

    ## Use this to automatically bounce heating and cooling states
    def atHeatCycleEnd(self):
        if self.heatingCompleted():
            self.heaterPwrLow()
    #ifdef MQDEBUG
            print("Cool sensor")
    #endif #MQDEBUG
            return False

        elif self.coolanceCompleted():
            self.heaterPwrOff()
            return True

        else:
            return False
    
    def readRawADC(self):
        return self.pinData.read()
    
    ## Measure liquefied hydrocarbon gas, LPG
    async def readLPG(self):
        return -1
        
    ## Measure methane    
    async def readMethane(self):
        return -1

    ## Measure smoke
    async def readSmoke(self):
        return -1

    ## Measure hydrogen
    async def readHydrogen(self):
        return -1
    
    async def readAlcoholMgL(self):
        return -1


    def readAlcoholPpm(self):
        return -1
    
    ## Measure Carbon monooxide
    def readCarbonMonoxide(self):
        return -1
    
    def readHydrogen(self):
        return -1
    
    def mode(self, mode):
        if mode == self.STRATEGY_ACCURATE or mode == self.STRATEGY_FAST:
            self.measuringStrategy = mode
