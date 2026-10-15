# Author: Peter Hinch
# Copyright Peter Hinch 2020-2021 Released under the MIT license

import gc
from machine import Timer, Pin
from array import array
from time import ticks_us, ticks_diff
from micropython import const

import asyncio
from setting import *
from utility import *
from threadsafe_queue_ir import ThreadSafeQueue

# Save RAM
from micropython import alloc_emergency_exception_buf
alloc_emergency_exception_buf(100)


# On 1st edge start a block timer. While the timer is running, record the time
# of each edge. When the timer times out decode the data. Duration must exceed
# the worst case block transmission time, but be less than the interval between
# a block start and a repeat code start (~108ms depending on protocol)

# Result/error codes
# Repeat button code
_REPEAT = const(-1)
# Error codes
_BADSTART = const(-2)
_BADBLOCK = const(-3)
_BADREP = const(-4)
_OVERRUN = const(-5)
_BADDATA = const(-6)
_BADADDR = const(-7)

IR_REMOTE_A = const(0x45)
IR_REMOTE_B = const(0x46)
IR_REMOTE_C = const(0x47)
IR_REMOTE_D = const(0x44)
IR_REMOTE_E = const(0x43)
IR_REMOTE_F = const(0x0d)
IR_REMOTE_UP = const(0x40)
IR_REMOTE_DOWN = const(0x19)
IR_REMOTE_LEFT = const(0x7)
IR_REMOTE_RIGHT = const(0x9)
IR_REMOTE_SETUP = const(0x15)
IR_REMOTE_0 = const(0x16)
IR_REMOTE_1 = const(0x0c)
IR_REMOTE_2 = const(0x18)
IR_REMOTE_3 = const(0x5e)
IR_REMOTE_4 = const(0x08)
IR_REMOTE_5 = const(0x1c)
IR_REMOTE_6 = const(0x5a)
IR_REMOTE_7 = const(0x42)
IR_REMOTE_8 = const(0x52)
IR_REMOTE_9 = const(0x4a)

_errors = {_BADSTART : 'Invalid start pulse',
           _BADBLOCK : 'Error: bad block',
           _BADREP : 'Error: repeat',
           _OVERRUN : 'Error: overrun',
           _BADDATA : 'Error: invalid data',
           _BADADDR : 'Error: invalid address'}

# IR remote control NEC protocol decoder using synchronous code
# For a remote using NEC see https://www.adafruit.com/products/389
_EDGES = const(68)
_TBLOCK = const(80)

class IR_RX():
    def __init__(self, pin, callback=None, error_callback=None, *args): # Optional args for callback
        self._pin = Pin(pin, Pin.IN)
        self._callback = callback
        self._error_callback = error_callback
        self.args = args
        self._tim = None
        self.verbose = False

        self._extended = False
        self._addr = 0

        self._key_pressed = None
        self._last_key_pressed = None
        self._raw_code = None

        self._times = array('i',  (0 for _ in range(_EDGES + 1)))  # +1 for overrun
        self.edge = 0
        self.cb = self._decode
        self.queue = ThreadSafeQueue([0 for _ in range(10)])
        self.start()

    # Pin interrupt. Save time of each edge for later decode.
    def _cb_pin(self, line):
        t = ticks_us()
        # On overrun ignore pulses until software timer times out
        if self.edge <= _EDGES:  # Allow 1 extra pulse to record overrun
            if not self.edge:  # First edge received
                self._tim.init(period=_TBLOCK, mode=Timer.ONE_SHOT, callback=self.cb)
            self._times[self.edge] = t
            self.edge += 1

    def _decode(self, _):
        if self.verbose:
            self._print_raw()

        try:
            if self.edge > 68:
                raise RuntimeError(_OVERRUN)
            width = ticks_diff(self._times[1], self._times[0])
            #if width < 4000:  # 9ms leading mark for all valid data
            #    raise RuntimeError(BADSTART)
            width = ticks_diff(self._times[2], self._times[1])
            if width > 2500:  # 4.5ms space for normal data
                #if self.edge < 68:  # Haven't received the correct number of edges
                #    raise RuntimeError(BADBLOCK)
                # Time spaces only (marks are always 562.5s)
                # Space is 1.6875ms (1) or 562.5s (0)
                # Skip last bit which is always 1
                val = 0
                for edge in range(3, 68 - 2, 2):
                    val >>= 1
                    if ticks_diff(self._times[edge + 1], self._times[edge]) > 1120:
                        val |= 0x80000000
            elif width > 110: # 2.5ms space for a repeat code. Should have exactly 4 edges.
                raise RuntimeError(_REPEAT if (self.edge >= 3 or self.edge <= 8) else _BADREP)  # Treat REPEAT as error.
            else:
                raise RuntimeError(_BADSTART)
            addr = val & 0xff  # 8 bit addr
            cmd = (val >> 16) & 0xff
            #if cmd != (val >> 24) ^ 0xff:
            #    raise RuntimeError(_BADDATA)
            if addr != ((val >> 8) ^ 0xff) & 0xff:  # 8 bit addr doesn't match check
                #if not self._extended:
                #    raise RuntimeError(_BADADDR)
                addr |= val & 0xff00  # pass assumed 16 bit address to callback
            self._addr = addr
        except RuntimeError as e:
            cmd = e.args[0]
            addr = self._addr if cmd == _REPEAT else 0  # REPEAT uses last address
        # Set up for new data burst and run user callback
        self.do_callback(cmd, addr, 0, _REPEAT)
        gc.collect()

    def _print_raw(self):
        lb = self.edge - 1  # Possible length of burst
        burst = []
        for x in range(lb):
            dt = ticks_diff(self._times[x + 1], self._times[x])
            if x > 0 and dt > 10000:  # Reached gap between repeats
                break
            burst.append(dt)
        lb = len(burst)  # Actual length
        print('\n')
        for x, e in enumerate(burst):
            print('{:03d} {:5d}'.format(x, e))
    
    def do_callback(self, cmd, addr, ext, thresh=0):
        self.edge = 0
        if cmd >= thresh:
            if cmd < 0:  # NEC protocol sends repeat codes.
                #self._raw_code = 'Repeat code'
                if self.verbose:
                    print('Repeat code.')
                #keep data old
                self._key_pressed = self._last_key_pressed
            else:
                self._raw_code = 'Data: {:d}, Addr: {:d}'.format(cmd, addr)
                if self.verbose:
                    print(self._raw_code)
                self._key_pressed = cmd
                self._last_key_pressed = self._key_pressed

            if self._callback:
                self._callback(self._key_pressed, addr, ext, *self.args)
            if not self.queue.full():
                self.queue.put_sync((self._key_pressed, addr))
        else:
            self._raw_code = 'Unsupported code'
            if self.verbose:
                if cmd in _errors:
                    print(_errors[cmd])
                else:
                    print('Unknown error code:', cmd)

            self._key_pressed = None
            self._last_key_pressed = None
            if self._error_callback:
                self._error_callback(cmd)

    def on_received(self, cb):
        self._callback = cb
    
    def on_error(self, cb):
        self._error_callback = cb

    def get_code(self):
        return self._key_pressed
    
    def get_raw_code(self):
        return self._raw_code
    
    def clear_code(self):
        self._raw_code = None
        self._key_pressed = None

    def start(self):
        self.stop()
        self._pin.irq(handler = self._cb_pin, trigger = (Pin.IRQ_FALLING | Pin.IRQ_RISING))
        self._tim = Timer(3)  # Sofware timer
    
    def stop(self):
        self._pin.irq(handler = None)
        if self._tim:
            self._tim.deinit()