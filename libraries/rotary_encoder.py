# The MIT License (MIT)
# Copyright (c) 2020 Mike Teachman
# https://opensource.org/licenses/MIT

# Platform-specific MicroPython code for the rotary encoder module
# ESP8266/ESP32 implementation

# Documentation:
#   https://github.com/MikeTeachman/micropython-rotary

from machine import Pin
from sys import platform

from setting import *
from utility import *

_esp8266_deny_pins = [16]
_DIR_CW = const(0x10)  # Clockwise step
_DIR_CCW = const(0x20) # Counter-clockwise step

# Rotary Encoder States
_R_START =   const(0x0)
_R_CW_1 =    const(0x1)
_R_CW_2 =    const(0x2)
_R_CW_3 =    const(0x3)
_R_CCW_1 =   const(0x4)
_R_CCW_2 =   const(0x5)
_R_CCW_3 =   const(0x6)
_R_ILLEGAL = const(0x7)

_transition_table = [

  #|------------- NEXT STATE -------------|            |CURRENT STATE|
  # CLK/DT    CLK/DT     CLK/DT    CLK/DT               
  #   00        01         10        11
  [_R_START, _R_CCW_1,  _R_CW_1,  _R_START],            # _R_START
  [_R_CW_2,  _R_START,  _R_CW_1,  _R_START],            # _R_CW_1
  [_R_CW_2,  _R_CW_3,   _R_CW_1,  _R_START],            # _R_CW_2
  [_R_CW_2,  _R_CW_3,   _R_START, _R_START | _DIR_CW],  # _R_CW_3    
  [_R_CCW_2, _R_CCW_1,  _R_START, _R_START],            # _R_CCW_1  
  [_R_CCW_2, _R_CCW_1,  _R_CCW_3, _R_START],            # _R_CCW_2  
  [_R_CCW_2, _R_START,  _R_CCW_3, _R_START | _DIR_CCW], # _R_CCW_3
  [_R_START, _R_START,  _R_START, _R_START]]            # _R_ILLEGAL

_STATE_MASK = const(0x07)
_DIR_MASK = const(0x30)  

def _wrap(value, incr, lower_bound, upper_bound):
    range = upper_bound - lower_bound + 1
    value = value + incr    
    
    if value < lower_bound:
        value += range * ((lower_bound - value) // range + 1)
    
    return lower_bound + (value - lower_bound) % range     

def _bound(value, incr, lower_bound, upper_bound):
    return min(upper_bound, max(lower_bound, value + incr))

class RotaryEncoder(object): 
 
    RANGE_UNBOUNDED = const(1)  
    RANGE_WRAP = const(2)
    RANGE_BOUNDED = const(3)
 
    def __init__(self, min_val, max_val, reverse, range_mode):
        self._min_val = min_val
        self._max_val = max_val
        self._reverse = -1 if reverse else 1
        self._range_mode = range_mode
        self._value = min_val
        self._old_value = min_val
        self._state = _R_START
        
    def set(self, value=None, min_val=None, max_val=None, reverse=None, range_mode=None):
        # disable DT and CLK pin interrupts
        self._hal_disable_irq()
        
        if value != None:
            self._value = value
        if min_val != None:
            self._min_val = min_val
        if max_val != None:
            self._max_val = max_val
        if reverse != None:
            self._reverse = -1 if reverse else 1
        if range_mode != None:
            self._range_mode = range_mode
        self._state = _R_START

        # enable DT and CLK pin interrupts
        self._hal_enable_irq()
    
    def value(self):
        return self._value

    def reset(self):
        self._value = 0
        
    def close(self):
        self._hal_close()
        
    def _process_rotary_pins(self, pin):
        clk_dt_pins = (self._hal_get_clk_value() << 1) | self._hal_get_dt_value()
        # Determine next state
        self._state = _transition_table[self._state & _STATE_MASK][clk_dt_pins]
        direction = self._state & _DIR_MASK

        incr = 0        
        if direction == _DIR_CW:
            incr = 1
        elif direction == _DIR_CCW:
            incr  = -1
            
        incr *= self._reverse
            
        if self._range_mode == self.RANGE_WRAP:
            self._value = _wrap(self._value, incr, self._min_val, self._max_val)
        elif self._range_mode == self.RANGE_BOUNDED:
            self._value = _bound(self._value, incr, self._min_val, self._max_val)
        else:
            self._value = self._value + incr

class RotaryEncoderIRQ(RotaryEncoder): 
    
    def __init__(self, clk, dt, min_val=0, max_val=10, reverse=False, range_mode=RotaryEncoder.RANGE_UNBOUNDED, pull_up=False):
        
        if platform == 'esp8266':
            if clk in _esp8266_deny_pins:
                raise ValueError('%s: Pin %d not allowed. Not Available for Interrupt: %s' % (platform, clk,_esp8266_deny_pins))
            if dt in _esp8266_deny_pins:
                raise ValueError('%s: Pin %d not allowed. Not Available for Interrupt: %s' % (platform, dt,_esp8266_deny_pins))

        super().__init__(min_val, max_val, reverse, range_mode)
        
        if pull_up == True:
            self._pin_clk = Pin(clk, Pin.IN, Pin.PULL_UP)
            self._pin_dt = Pin(dt, Pin.IN, Pin.PULL_UP)
        else:
            self._pin_clk = Pin(clk, Pin.IN)
            self._pin_dt = Pin(dt, Pin.IN)

        self._enable_clk_irq(self._process_rotary_pins)        
        self._enable_dt_irq(self._process_rotary_pins)   
        
    def _enable_clk_irq(self, callback=None):
        self._pin_clk.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=callback)
        
    def _enable_dt_irq(self, callback=None):
        self._pin_dt.irq(trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING, handler=callback)
        
    def _disable_clk_irq(self):
        self._pin_clk.irq(handler=None)
        
    def _disable_dt_irq(self):
        self._pin_dt.irq(handler=None)     
    
    def _hal_get_clk_value(self):
        return self._pin_clk.value()
        
    def _hal_get_dt_value(self):
        return self._pin_dt.value()   
    
    def _hal_enable_irq(self):
        self._enable_clk_irq(self._process_rotary_pins)        
        self._enable_dt_irq(self._process_rotary_pins)   

    def _hal_disable_irq(self): 
        self._disable_clk_irq()
        self._disable_dt_irq()     

    def _hal_close(self):
        self._hal_disable_irq()

    def get_steps(self):
        changed_steps = self._value - self._old_value
        self._old_value = self._value
        return changed_steps
