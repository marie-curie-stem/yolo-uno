from machine import SoftI2C, Pin
import time
from yolo_uno import *

CMD_CHANNEL_CTRL = 0x10
CMD_SAVE_I2C_ADDR = 0x11
I2C_ADDR = 0x11

class RelayController:
    def __init__(self, addr=I2C_ADDR):
        self.i2c = SoftI2C(scl=SCL_PIN, sda=SDA_PIN, freq=100000)
        self.addr = addr
        self.channel_state = 0x00
    
    def change_relay_address(self, new_addr):
        self.i2c.writeto_mem(self.addr, CMD_SAVE_I2C_ADDR, bytes([new_addr]))


    def get_relay(self, index):
        if index == 0:
            return self.channel_state  
        else:
            return (self.channel_state >> (index - 1)) & 0x01  

    def set_relay(self, index, value):
        if index == 0:
            self.channel_state = 0x0F if value == 1 else 0x00  
        else:
            if value == 1:
                self.channel_state |= (1 << (index - 1)) 
            else:
                self.channel_state &= ~(1 << (index - 1))  
        self.i2c.writeto_mem(self.addr, CMD_CHANNEL_CTRL, bytes([self.channel_state]))

    def toggle_relay(self, index):
        if index == 0:
            self.channel_state ^= 0x0F  
        else:
            self.channel_state ^= (1 << (index - 1))  
        self.i2c.writeto_mem(self.addr, CMD_CHANNEL_CTRL, bytes([self.channel_state]))

relay = RelayController()