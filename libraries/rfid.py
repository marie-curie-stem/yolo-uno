'''
This address needs to match the RFID Module pad:
[OFF:OFF] 0x2C
[ON :OFF] 0x2D
[OFF:ON ] 0x2E
[ON :ON ] 0x2F
'''

from yolo_uno import *
import json
from time import sleep, sleep_ms
from rfid_expansion import *
import os
import os
from machine import SoftI2C, Pin

_SYSNAME = os.uname().sysname

_I2C_ADDRESS        = 0x2C

_REG_COMMAND        = 0x01
_REG_COM_I_EN       = 0x02
_REG_DIV_I_EN       = 0x03
_REG_COM_IRQ        = 0x04
_REG_DIV_IRQ        = 0x05
_REG_ERROR          = 0x06
_REG_STATUS_1       = 0x07
_REG_STATUS_2       = 0x08
_REG_FIFO_DATA      = 0x09
_REG_FIFO_LEVEL     = 0x0A
_REG_CONTROL        = 0x0C
_REG_BIT_FRAMING    = 0x0D
_REG_MODE           = 0x11
_REG_TX_CONTROL     = 0x14
_REG_TX_ASK         = 0x15
_REG_CRC_RESULT_MSB = 0x21
_REG_CRC_RESULT_LSB = 0x22
_REG_T_MODE         = 0x2A
_REG_T_PRESCALER    = 0x2B
_REG_T_RELOAD_HI    = 0x2C
_REG_T_RELOAD_LO    = 0x2D
_REG_AUTO_TEST      = 0x36
_REG_VERSION        = 0x37
_CMD_IDLE           = 0x00
_CMD_CALC_CRC       = 0x03
_CMD_TRANCEIVE      = 0x0C
_CMD_MF_AUTHENT     = 0x0E
_CMD_SOFT_RESET     = 0x0F

# RFID Tag (Proximity Integrated Circuit Card)
_TAG_CMD_REQIDL  = 0x26
_TAG_CMD_REQALL  = 0x52
_TAG_CMD_ANTCOL1 = 0x93
_TAG_CMD_ANTCOL2 = 0x95
_TAG_CMD_ANTCOL3 = 0x97

# Classic
_TAG_AUTH_KEY_A = 0x60
_CLASSIC_KEY = [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]

class RFID:
    OK = 1
    NOTAGERR = 2
    ERR = 3

    def __init__(self, i2c, address=_I2C_ADDRESS, asw=None, suppress_warnings=False):

        self.i2c = i2c
        self.lists = {}
        
        if type(asw) is list: # determine address from ASW switch positions (if provided)
            assert max(asw) <= 1 and min(asw) >= 0 and len(asw) is 2, "asw must be a list of 1/0, length=2"
            self.address=_I2C_ADDRESS+asw[0]+2*asw[1]
        else:
            self.address = address # fall back on using address argument
            
        self._tag_present = False
        self._read_tag_id_success = False
        self.reset()
        sleep_ms(50)
        self._wreg(_REG_T_MODE, 0x80)
        self._wreg(_REG_T_PRESCALER, 0xA9)
        self._wreg(_REG_T_RELOAD_HI, 0x03)
        self._wreg(_REG_T_RELOAD_LO, 0xE8)
        self._wreg(_REG_TX_ASK, 0x40)
        self._wreg(_REG_MODE, 0x3D)
        self._wreg(_REG_DIV_I_EN, 0x80) # CMOS Logic for IRQ pin
        self._wreg(_REG_COM_I_EN, 0x20) # allows the receiver interrupt request (RxIRq bit) to be propagated to pin IRQ
        self.antennaOn()
        if _SYSNAME == 'microbit' and not suppress_warnings:
            print("Due to micro:bit's limited flash storage this library is running with reduced features.\nFor advanced features, use a Raspberry Pi or Pico instead.\nSuppress this warning: initialise with PiicoDev_RFID(suppress_warnings=True)\n")
    
    # I2C write to register
    def _wreg(self, reg, val):
        self.i2c.writeto_mem(self.address, reg, bytes([val]))

    # I2C write to FIFO buffer
    def _wfifo(self, reg, val):
        self.i2c.writeto_mem(self.address, reg, bytes(val))

    # I2C read from register
    def _rreg(self, reg):
        val = self.i2c.readfrom_mem(self.address, reg, 1)
        return val[0]
    
    # Set register flags
    def _sflags(self, reg, mask):
        current_value = self._rreg(reg)
        self._wreg(reg, current_value | mask)

    # Clear register flags
    def _cflags(self, reg, mask):
        self._wreg(reg, self._rreg(reg) & (~mask))

    # Communicates with the tag
    def _tocard(self, cmd, send):
        recv = []
        bits = irq_en = wait_irq = n = 0
        stat = self.ERR

        if cmd == _CMD_MF_AUTHENT:
            irq_en = 0x12
            wait_irq = 0x10
        elif cmd == _CMD_TRANCEIVE:
            irq_en = 0x77
            wait_irq = 0x30
        self._wreg(_REG_COMMAND, _CMD_IDLE)      # Stop any active command.
        self._wreg(_REG_COM_IRQ, 0x7F)           # Clear all seven interrupt request bits
        self._sflags(_REG_FIFO_LEVEL, 0x80)      # FlushBuffer = 1, FIFO initialization
        self._wfifo(_REG_FIFO_DATA, send)        # Write to the FIFO
        if cmd == _CMD_TRANCEIVE:
            self._sflags(_REG_BIT_FRAMING, 0x00) # This starts the transceive operation
        self._wreg(_REG_COMMAND, cmd)
        if cmd == _CMD_TRANCEIVE:
            self._sflags(_REG_BIT_FRAMING, 0x80) # This starts the transceive operation

        i = 20000  #2000
        while True:
            n = self._rreg(_REG_COM_IRQ)
            i -= 1
            if n & wait_irq:
                break
            if n & 0x01:
                break
            if i == 0:
                break
        self._cflags(_REG_BIT_FRAMING, 0x80)
        
        if i:
            if (self._rreg(_REG_ERROR) & 0x1B) == 0x00:
                stat = self.OK

                if n & irq_en & 0x01:
                    stat = self.NOTAGERR
                elif cmd == _CMD_TRANCEIVE:
                    n = self._rreg(_REG_FIFO_LEVEL)
                    lbits = self._rreg(_REG_CONTROL) & 0x07
                    if lbits != 0:
                        bits = (n - 1) * 8 + lbits
                    else:
                        bits = n * 8
                    if n == 0:
                        n = 1
                    elif n > 16:
                        n = 16

                    for _ in range(n):
                        recv.append(self._rreg(_REG_FIFO_DATA))
            else:
                stat = self.ERR
        return stat, recv, bits

    # Use the co-processor on the RFID module to obtain CRC
    def _crc(self, data):
        self._wreg(_REG_COMMAND, _CMD_IDLE)
        self._cflags(_REG_DIV_IRQ, 0x04)
        self._sflags(_REG_FIFO_LEVEL, 0x80)

        for c in data:
            self._wreg(_REG_FIFO_DATA, c)
        self._wreg(_REG_COMMAND, _CMD_CALC_CRC)

        i = 0xFF
        while True:
            n = self._rreg(_REG_DIV_IRQ)
            i -= 1
            if not ((i != 0) and not (n & 0x04)):
                break
        self._wreg(_REG_COMMAND, _CMD_IDLE)
        return [self._rreg(_REG_CRC_RESULT_LSB), self._rreg(_REG_CRC_RESULT_MSB)]
    
    # Invites tag in state IDLE to go to READY
    def _request(self, mode):
        self._wreg(_REG_BIT_FRAMING, 0x07)
        (stat, recv, bits) = self._tocard(_CMD_TRANCEIVE, [mode])
        if (stat != self.OK) | (bits != 0x10):
            stat = self.ERR
        return stat, bits

    # Perform anticollision check
    def _anticoll(self, anticolN=_TAG_CMD_ANTCOL1):
        ser_chk = 0
        ser = [anticolN, 0x20]

        self._wreg(_REG_BIT_FRAMING, 0x00)
        (stat, recv, bits) = self._tocard(_CMD_TRANCEIVE, ser)
        if stat == self.OK:
            if len(recv) == 5:
                for i in range(4):
                    ser_chk = ser_chk ^ recv[i]
                if ser_chk != recv[4]:
                    stat = self.ERR
            else:
                stat = self.ERR
        return stat, recv
    
    # Select the desired tag
    def _selectTag(self, serNum,anticolN):
        backData = []
        buf = []
        buf.append(anticolN)
        buf.append(0x70)
        for i in serNum:
            buf.append(i)
        pOut = self._crc(buf)
        buf.append(pOut[0])
        buf.append(pOut[1])
        (status, backData, backLen) = self._tocard( 0x0C, buf)
        if (status == self.OK) and (backLen == 0x18):
            return  1
        else:
            return 0
    
    # Returns detailed information about the tag 
    def _readTagID(self):
        result = {'success':False, 'id_integers':[], 'id_formatted':'', 'type':''}
        valid_uid=[]
        (status,uid)= self._anticoll(_TAG_CMD_ANTCOL1)
        if status != self.OK:
            return result
        
        if self._selectTag(uid,_TAG_CMD_ANTCOL1) == 0:
            return result
        
        if uid[0] == 0x88 : # NTAG
            valid_uid.extend(uid[1:4])
            (status,uid)=self._anticoll(_TAG_CMD_ANTCOL2)
            if status != self.OK:
                return result
            rtn =  self._selectTag(uid,_TAG_CMD_ANTCOL2)
            if rtn == 0:
                return result
            #now check again if uid[0] is 0x88
            if uid[0] == 0x88 :
                valid_uid.extend(uid[1:4])
                (status , uid) = self._anticoll(_TAG_CMD_ANTCOL3)
                if status != self.OK:
                    return result
        valid_uid.extend(uid[0:5])
        id_formatted = ''
        id = valid_uid[:len(valid_uid)-1]
        for i in range(0,len(id)):
            if i > 0:
                id_formatted = id_formatted + ':'
            if id[i] < 16:
                id_formatted = id_formatted + '0'
            id_formatted = id_formatted + hex(id[i])[2:]
        type = 'ntag'
        if len(id) == 4:
            type = 'classic'
        return {'success':True, 'id_integers':id, 'id_formatted':id_formatted.upper(), 'type':type}
    
    # Detect the presence of a tag
    def _detectTag(self):
        (stat, ATQA) = self._request(_TAG_CMD_REQIDL)
        _present = False
        if stat is self.OK:
            _present = True
        self._tag_present = _present
        return {'present':_present, 'ATQA':ATQA}
    
    # Resets the RFID module
    def reset(self):
        self._wreg(_REG_COMMAND, _CMD_SOFT_RESET)

    # Turns the antenna on
    def antennaOn(self):
        if ~(self._rreg(_REG_TX_CONTROL) & 0x03):
            self._sflags(_REG_TX_CONTROL, 0x83)
    
    # Turns the antenna off
    def antennaOff(self):
        if not (~(self._rreg(_REG_TX_CONTROL) & 0x03)):
            self._cflags(_REG_TX_CONTROL, b'\x03')

    # Stand-alone function that puts the tag into the correct state
    # Returns detailed information about the tag
    def readTagID(self):
        detect_tag_result = self._detectTag()
        if detect_tag_result['present'] is False: #Try again, the card may not be in the correct state
            detect_tag_result = self._detectTag()
        if detect_tag_result['present']:
            read_tag_id_result = self._readTagID()
            if read_tag_id_result['success']:
                self._read_tag_id_success = True
                return {'success':read_tag_id_result['success'], 'id_integers':read_tag_id_result['id_integers'], 'id_formatted':read_tag_id_result['id_formatted'], 'type':read_tag_id_result['type']}
        self._read_tag_id_success = False
        return {'success':False, 'id_integers':[0], 'id_formatted':'', 'type':''}

    # Wrapper for readTagID
    def readID(self, detail=False):
        if detail is False:
            tagId = self.readTagID()
            return tagId['id_formatted']
        else: return self.readTagID()

    # Wrapper for readTagID
    def tagPresent(self):
        id = self.readTagID()
        return id['success']
    
    def load_list(self, list_name):
        filename = f"{list_name}.json"
        try:
            with open(filename, "r") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    data = []
        except (OSError, ValueError):
            data = []
        
        self.lists[list_name] = data  
        return data  

    def save_list(self, list_name):
        if list_name in self.lists:
            filename = f"{list_name}.json"
            with open(filename, "w") as f:
                json.dump(self.lists[list_name], f)

    def scan_card(self):
        if self.tagPresent():
            return self.readID()
        return ""

    def scan_and_add_card(self, list_name):
        if list_name not in self.lists:
            self.load_list(list_name) 

        uuid = self.scan_card()
        if not uuid:
            return

        if uuid not in self.lists[list_name]:  
            self.lists[list_name].append(uuid)
            self.save_list(list_name) 
            print("Add card success!") 

    def scan_and_check(self, list_name):
        if list_name not in self.lists:
            self.load_list(list_name)  

        uuid = self.scan_card()
        if not uuid:
            return False
        
        return uuid in self.lists[list_name]

    def get_list(self, list_name):
        if list_name not in self.lists:
            self.load_list(list_name)  
        return self.lists.get(list_name, [])

    def scan_and_remove_card(self, list_name):
        if list_name not in self.lists:
            self.load_list(list_name)  

        uuid = self.scan_card()
        if uuid in self.lists[list_name]:  
            self.lists[list_name].remove(uuid)

            if not self.lists[list_name]:  
                filename = f"{list_name}.json"
                try:
                    os.remove(filename) 
                except OSError:  
                    pass  

                del self.lists[list_name]  
            else:
                self.save_list(list_name)
                print("Remove card success!")  
            
    def clear_list(self, list_name):
        filename = f"{list_name}.json"
        if list_name in self.lists:
            del self.lists[list_name]
        try:
            os.remove(filename)
            print("Remove list success!")
        except OSError:
            pass  

i2c = SoftI2C(scl=SCL_PIN, sda=SDA_PIN, freq=100000)
rfid = RFID(i2c)