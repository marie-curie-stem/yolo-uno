#include "MQ6.h"
# Ported from https://github.com/amperka/TroykaMQ
# Author: Alexey Tveritinov [kartun@yandex.ru]
from BaseMQ import BaseMQ

class MQ6(BaseMQ):
    # резистор установленный на плату (кОм)
    MQ6_RL_BOARD = 20.0

    ## Clean air coefficient
    MQ6_RO_BASE = float(10.0)

    def __init__(self, pinData, pinHeater=-1, boardResistance = 10, baseVoltage = 3.3, measuringStrategy = BaseMQ.STRATEGY_ACCURATE):
        # Call superclass to fill attributes
        super().__init__(pinData, pinHeater, boardResistance, baseVoltage, measuringStrategy)
        
    ## Measure liquefied hydrocarbon gas, LPG
    async def readLPG(self):
        return await self.readScaled(-0.42, 2.91)
    
    ##  Base RO differs for every sensor family
    def getRoInCleanAir(self):
        return self.MQ6_RO_BASE
