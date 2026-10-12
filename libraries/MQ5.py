#include "MQ5.h"
# Ported from https://github.com/amperka/TroykaMQ
# Author: Alexey Tveritinov [kartun@yandex.ru]
from BaseMQ import BaseMQ

class MQ5(BaseMQ):
    # резистор установленный на плату (кОм)
    MQ5_RL_BOARD = 20.0

    ## Clean air coefficient
    MQ5_RO_BASE = float(6.5)

    def __init__(self, pinData, pinHeater=-1, boardResistance = 10, baseVoltage = 3.3, measuringStrategy = BaseMQ.STRATEGY_ACCURATE):
        # Call superclass to fill attributes
        super().__init__(pinData, pinHeater, boardResistance, baseVoltage, measuringStrategy)
        
    ## Measure liquefied hydrocarbon gas, LPG
    async def readLPG(self):
        return await self.readScaled(-0.39, 1.73)

    ## Measure methane    
    async def readMethane(self):
        return await self.readScaled(-0.38, 1.97)

    ##  Base RO differs for every sensor family
    def getRoInCleanAir(self):
        return self.MQ5_RO_BASE
