#include "MQ8.h"

# Ported from https://github.com/amperka/TroykaMQ
# Author: Alexey Tveritinov [kartun@yandex.ru]
from BaseMQ import BaseMQ

class MQ8(BaseMQ):
    # резистор установленный на плату (кОм)
    MQ8_RL_BOARD = 10.0

    ## Clean air coefficient
    MQ8_RO_BASE = float(27.0)

    def __init__(self, pinData, pinHeater=-1, boardResistance = 10, baseVoltage = 3.3, measuringStrategy = BaseMQ.STRATEGY_ACCURATE):
        # Call superclass to fill attributes
        super().__init__(pinData, pinHeater, boardResistance, baseVoltage, measuringStrategy)
        
    async def readHydrogen(self):
        return await self.readScaled(-1.52, 10.49)
    
    ##  Base RO differs for every sensor family
    def getRoInCleanAir(self):
        return self.MQ8_RO_BASE


