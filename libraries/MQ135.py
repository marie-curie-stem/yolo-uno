#include "MQ135.h"
# Ported from https://github.com/amperka/TroykaMQ
# Author: Alexey Tveritinov [kartun@yandex.ru]
from BaseMQ import BaseMQ
from math import exp, log

class MQ135(BaseMQ):
    # резистор установленный на плату (кОм)
    MQ135_RL_BOARD = 10.0

    ## Clean air coefficient
    MQ9_RO_BASE = float(9.8)
    PPM_CO2_IN_CLEAR_AIR = float(397.13)

    def __init__(self, pinData, pinHeater=-1, boardResistance = 10, baseVoltage = 3.3, measuringStrategy = BaseMQ.STRATEGY_ACCURATE):
        # Call superclass to fill attributes
        super().__init__(pinData, pinHeater, boardResistance, baseVoltage, measuringStrategy)

    async def readCO2(self):
        return await self.readScaled(-0.42 , 1.92)

    ##  Base RO differs for every sensor family
    def getRoInCleanAir(self):
        return exp((log(self.PPM_CO2_IN_CLEAR_AIR) * -0.42) + 1.92)