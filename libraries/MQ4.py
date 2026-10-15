#include "MQ4.h"
# Ported from https://github.com/amperka/TroykaMQ
# Author: Alexey Tveritinov [kartun@yandex.ru]
from BaseMQ import BaseMQ

class MQ4(BaseMQ):
    # резистор установленный на плату (кОм)
    MQ4_RL_BOARD = 20.0

    ## Clean air coefficient
    MQ4_RO_BASE = float(4.4)

    def __init__(self, pinData, pinHeater=-1, boardResistance = 10, baseVoltage = 3.3, measuringStrategy = BaseMQ.STRATEGY_ACCURATE):
        # Call superclass to fill attributes
        super().__init__(pinData, pinHeater, boardResistance, baseVoltage, measuringStrategy)
        
    ## Measure methane    
    async def readMethane(self):
        return await self.readScaled(-0.36, 2.54)

    ##  Base RO differs for every sensor family
    def getRoInCleanAir(self):
        return self.MQ4_RO_BASE
