#include "MQ2.h"
# Ported from https://github.com/amperka/TroykaMQ
# Author: Alexey Tveritinov [kartun@yandex.ru]
from BaseMQ import BaseMQ

class MQ2(BaseMQ):
    ## Clean air coefficient
    MQ2_RO_BASE = float(9.83)

    def __init__(self, pinData, pinHeater=-1, boardResistance = 10, baseVoltage = 3.3, measuringStrategy = BaseMQ.STRATEGY_ACCURATE):
        # Call superclass to fill attributes
        super().__init__(pinData, pinHeater, boardResistance, baseVoltage, measuringStrategy)

    ## Measure liquefied hydrocarbon gas, LPG
    async def readLPG(self):
        return await self.readScaled(-0.45, 2.95)
        
    ## Measure methane    
    async def readMethane(self):
        return await self.readScaled(-0.38, 3.21)

    ## Measure smoke
    async def readSmoke(self):
        return await self.readScaled(-0.42, 3.54)

    ## Measure hydrogen
    async def readHydrogen(self):
        return await self.readScaled(-0.48, 3.32)

    ##  Base RO differs for every sensor family
    def getRoInCleanAir(self):
        return self.MQ2_RO_BASE