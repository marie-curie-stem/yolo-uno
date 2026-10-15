from yolo_uno import *
import json
import time, gc
from machine import Pin
from machine import Timer, Pin
from array import array
from time import sleep_ms, ticks_us, ticks_diff
from machine import Pin, PWM
from esp32 import RMT

STOP = const(0)

class IR_RX:
    Timer_id = 3  # Hardware timer 3; MicroPython >= 1.23 rejects -1
    # Result/error codes
    # Repeat button code
    REPEAT = -1
    # Error codes
    BADSTART = -2
    BADBLOCK = -3
    BADREP = -4
    OVERRUN = -5
    BADDATA = -6
    BADADDR = -7

    def __init__(self, pin, nedges, tblock, callback, *args):  # Optional args for callback
        self._pin = pin
        self._nedges = nedges
        self._tblock = tblock
        self.callback = callback
        self.args = args
        self._errf = lambda _: None
        self.verbose = False

        self._times = array("i", (0 for _ in range(nedges + 1)))  # +1 for overrun
        pin.irq(handler=self._cb_pin, trigger=(Pin.IRQ_FALLING | Pin.IRQ_RISING))
        self.edge = 0
        self.tim = Timer(self.Timer_id)  # Defaul is sofware timer
        self.cb = self.decode

    # Pin interrupt. Save time of each edge for later decode.
    def _cb_pin(self, line):
        t = ticks_us()
        # On overrun ignore pulses until software timer times out
        if self.edge <= self._nedges:  # Allow 1 extra pulse to record overrun
            if not self.edge:  # First edge received
                self.tim.init(period=self._tblock, mode=Timer.ONE_SHOT, callback=self.cb)
            self._times[self.edge] = t
            self.edge += 1

    def do_callback(self, cmd, addr, ext, thresh=0):
        self.edge = 0
        if cmd >= thresh:
            self.callback(cmd, addr, ext, *self.args)
        else:
            self._errf(cmd)

    def error_function(self, func):
        self._errf = func

    def close(self):
        self._pin.irq(handler=None)
        self.tim.deinit()
        
_errors = {IR_RX.BADSTART : 'Invalid start pulse',
           IR_RX.BADBLOCK : 'Error: bad block',
           IR_RX.BADREP : 'Error: repeat',
           IR_RX.OVERRUN : 'Error: overrun',
           IR_RX.BADDATA : 'Error: invalid data',
           IR_RX.BADADDR : 'Error: invalid address'}

def print_error(data):
    if data in _errors:
        print(_errors[data])
    else:
        print('Unknown error code:', data)


class IR_GET(IR_RX):
    def __init__(self, pin, nedges=100, twait=100, display=True):
        self.display = display
        super().__init__(pin, nedges, twait, lambda *_ : None)
        self.data = None

    def decode(self, _):
        def near(v, target):
            return target * 0.8 < v < target * 1.2
        lb = self.edge - 1  # Possible length of burst
        if lb < 3:
            return  # Noise
        burst = []
        for x in range(lb):
            dt = ticks_diff(self._times[x + 1], self._times[x])
            if x > 0 and dt > 10000:  # Reached gap between repeats
                break
            burst.append(dt)
        lb = len(burst)  # Actual length
        # Duration of pulse train 24892 for RC-5 22205 for RC-6
        duration = ticks_diff(self._times[lb - 1], self._times[0])

        if self.display:
            for x, e in enumerate(burst):
                print('{:03d} {:5d}'.format(x, e))
            print()
            # Attempt to determine protocol
            ok = False  # Protocol not yet found
            if near(burst[0], 9000) and lb == 67:
                print('NEC')
                ok = True

            if not ok and near(burst[0], 2400) and near(burst[1], 600):  # Maybe Sony
                try:
                    nbits = {25:12, 31:15, 41:20}[lb]
                except KeyError:
                    pass
                else:
                    ok = True
                    print('Sony {}bit'.format(nbits))

            if not ok and near(burst[0], 889):  # Maybe RC-5
                if near(duration, 24892) and near(max(burst), 1778):
                    print('Philps RC-5')
                    ok = True

            if not ok and near(burst[0], 2666) and near(burst[1], 889):  # RC-6?
                if near(duration, 22205) and near(burst[1], 889) and near(burst[2], 444):
                    print('Philips RC-6 mode 0')
                    ok = True

            if not ok and near(burst[0], 2000) and near(burst[1], 1000):
                if near(duration, 19000):
                    print('Microsoft MCE edition protocol.')
                    # Constant duration, variable burst length, presumably bi-phase
                    print('Protocol start {} {} Burst length {} duration {}'.format(burst[0], burst[1], lb, duration))
                    ok = True

            if not ok and near(burst[0], 4500) and near(burst[1], 4500) and lb == 67:  # Samsung
                print('Samsung')
                ok = True

            if not ok and near(burst[0], 3500) and near(burst[1], 1680):  # Panasonic?
                print('Unsupported protocol. Panasonic?')
                ok = True

            if not ok:
                print('Unknown protocol start {} {} Burst length {} duration {}'.format(burst[0], burst[1], lb, duration))

            print()
        self.data = burst
        # Set up for new data burst. Run null callback
        self.do_callback(0, 0, 0)

    def acquire(self):
        while self.data is None:
            sleep_ms(5)
        self.close()
        return self.data

class MCE(IR_RX):
    init_cs = 4  # http://www.hifi-remote.com/johnsfine/DecodeIR.html#OrtekMCE says 3
    def __init__(self, pin, callback, *args):
        # Block lasts ~19ms and has <= 34 edges
        super().__init__(pin, 34, 25, callback, *args)

    def decode(self, _):
        def check(v):
            if self.init_cs == -1:
                return True
            csum = v >> 12
            cs = self.init_cs
            for _ in range(12):
                if v & 1:
                    cs += 1
                v >>= 1
            return cs == csum

        try:
            t0 = ticks_diff(self._times[1], self._times[0])  # 2000μs mark
            t1 = ticks_diff(self._times[2], self._times[1])  # 1000μs space
            if not ((1800 < t0 < 2200) and (800 < t1 < 1200)):
                raise RuntimeError(self.BADSTART)
            nedges = self.edge  # No. of edges detected
            if not 14 <= nedges <= 34:
                raise RuntimeError(self.OVERRUN if nedges > 28 else self.BADSTART)
            # Manchester decode
            mask = 1
            bit = 1
            v = 0
            x = 2
            for _ in range(16):
                # -1 convert count to index, -1 because we look ahead
                if x > nedges - 2:
                    raise RuntimeError(self.BADBLOCK)
                # width is 500/1000 nominal
                width = ticks_diff(self._times[x + 1], self._times[x])
                if not 250 < width < 1350:
                    self.verbose and print('Bad block 3 Width', width, 'x', x)
                    raise RuntimeError(self.BADBLOCK)
                short = int(width < 750)
                bit ^= short ^ 1
                v |= mask if bit else 0
                mask <<= 1
                x += 1 + short

            self.verbose and print(bin(v))
            if not check(v):
                raise RuntimeError(self.BADDATA)
            val = (v >> 6) & 0x3f
            addr = v & 0xf  # Constant for all buttons on my remote
            ctrl = (v >> 4) & 3

        except RuntimeError as e:
            val, addr, ctrl = e.args[0], 0, 0
        # Set up for new data burst and run user callback/error function
        self.do_callback(val, addr, ctrl)

class NEC_ABC(IR_RX):
    def __init__(self, pin, extended, samsung, callback, *args):
        # Block lasts <= 80ms (extended mode) and has 68 edges
        super().__init__(pin, 68, 80, callback, *args)
        self._extended = extended
        self._addr = 0
        self._leader = 2500 if samsung else 4000  # 4.5ms for Samsung else 9ms

    def decode(self, _):
        try:
            if self.edge > 68:
                raise RuntimeError(self.OVERRUN)
            width = ticks_diff(self._times[1], self._times[0])
            if width < self._leader:  # 9ms leading mark for all valid data
                raise RuntimeError(self.BADSTART)
            width = ticks_diff(self._times[2], self._times[1])
            if width > 3000:  # 4.5ms space for normal data
                if self.edge < 68:  # Haven't received the correct number of edges
                    raise RuntimeError(self.BADBLOCK)
                # Time spaces only (marks are always 562.5µs)
                # Space is 1.6875ms (1) or 562.5µs (0)
                # Skip last bit which is always 1
                val = 0
                for edge in range(3, 68 - 2, 2):
                    val >>= 1
                    if ticks_diff(self._times[edge + 1], self._times[edge]) > 1120:
                        val |= 0x80000000
            elif width > 1700: # 2.5ms space for a repeat code. Should have exactly 4 edges.
                raise RuntimeError(self.REPEAT if self.edge == 4 else self.BADREP)  # Treat REPEAT as error.
            else:
                raise RuntimeError(self.BADSTART)
            addr = val & 0xff  # 8 bit addr
            cmd = (val >> 16) & 0xff
            if cmd != (val >> 24) ^ 0xff:
                raise RuntimeError(self.BADDATA)
            if addr != ((val >> 8) ^ 0xff) & 0xff:  # 8 bit addr doesn't match check
                if not self._extended:
                    raise RuntimeError(self.BADADDR)
                addr |= val & 0xff00  # pass assumed 16 bit address to callback
            self._addr = addr
        except RuntimeError as e:
            cmd = e.args[0]
            addr = self._addr if cmd == self.REPEAT else 0  # REPEAT uses last address
        # Set up for new data burst and run user callback
        self.do_callback(cmd, addr, 0, self.REPEAT)

class NEC_8(NEC_ABC):
    def __init__(self, pin, callback, *args):
        super().__init__(pin, False, False, callback, *args)

class NEC_16(NEC_ABC):
    def __init__(self, pin, callback, *args):
        super().__init__(pin, True, False, callback, *args)

class SAMSUNG(NEC_ABC):
    def __init__(self, pin, callback, *args):
        super().__init__(pin, True, True, callback, *args)

class RC5_IR(IR_RX):
    def __init__(self, pin, callback, *args):
        # Block lasts <= 30ms and has <= 28 edges
        super().__init__(pin, 28, 30, callback, *args)

    def decode(self, _):
        try:
            nedges = self.edge  # No. of edges detected
            if not 14 <= nedges <= 28:
                raise RuntimeError(self.OVERRUN if nedges > 28 else self.BADSTART)
            # Regenerate bitstream
            bits = 1
            bit = 1
            v = 1  # 14 bit bitstream, MSB always 1
            x = 0
            while bits < 14:
                # -1 convert count to index, -1 because we look ahead
                if x > nedges - 2:
                    print('Bad block 1 edges', nedges, 'x', x)
                    raise RuntimeError(self.BADBLOCK)
                # width is 889/1778 nominal
                width = ticks_diff(self._times[x + 1], self._times[x])
                if not 500 < width < 2100:
                    self.verbose and print('Bad block 3 Width', width, 'x', x)
                    raise RuntimeError(self.BADBLOCK)
                short = width < 1334
                if not short:
                    bit ^= 1
                v <<= 1
                v |= bit
                bits += 1
                x += 1 + int(short)
            self.verbose and print(bin(v))
            # Split into fields (val, addr, ctrl)
            val = (v & 0x3f) | (0 if ((v >> 12) & 1) else 0x40)  # Correct the polarity of S2
            addr = (v >> 6) & 0x1f
            ctrl = (v >> 11) & 1

        except RuntimeError as e:
            val, addr, ctrl = e.args[0], 0, 0
        # Set up for new data burst and run user callback
        self.do_callback(val, addr, ctrl)


class RC6_M0(IR_RX):
    # Even on Pyboard D the 444μs nominal pulses can be recorded as up to 705μs
    # Scope shows 360-520 μs (-84μs +76μs relative to nominal)
    # Header nominal 2666, 889, 444, 889, 444, 444, 444, 444 carrier ON at end
    hdr = ((1800, 4000), (593, 1333), (222, 750), (593, 1333), (222, 750), (222, 750), (222, 750), (222, 750))
    def __init__(self, pin, callback, *args):
        # Block lasts 23ms nominal and has <=44 edges
        super().__init__(pin, 44, 30, callback, *args)

    def decode(self, _):
        try:
            nedges = self.edge  # No. of edges detected
            if not 22 <= nedges <= 44:
                raise RuntimeError(self.OVERRUN if nedges > 28 else self.BADSTART)
            for x, lims in enumerate(self.hdr):
                width = ticks_diff(self._times[x + 1], self._times[x])
                if not (lims[0] < width < lims[1]):
                    self.verbose and print('Bad start', x, width, lims)
                    raise RuntimeError(self.BADSTART)
            x += 1
            width = ticks_diff(self._times[x + 1], self._times[x])
            # 2nd bit of last 0 is 444μs (0) or 1333μs (1)
            if not 222 < width < 1555:
                self.verbose and print('Bad block 1 Width', width, 'x', x)
                raise RuntimeError(self.BADBLOCK)
            short = width < 889
            v = int(not short)
            bit = v
            bits = 1  # Bits decoded
            x += 1 + int(short)
            width = ticks_diff(self._times[x + 1], self._times[x])
            if not 222 < width < 1555:
                self.verbose and print('Bad block 2 Width', width, 'x', x)
                raise RuntimeError(self.BADBLOCK)
            short = width < 1111
            if not short:
                bit ^= 1
            x += 1 + int(short)  # If it's short, we know width of next
            v <<= 1
            v |= bit  # MSB of result
            bits += 1
            # Decode bitstream
            while bits < 17:
                # -1 convert count to index, -1 because we look ahead
                if x > nedges - 2:
                    raise RuntimeError(self.BADBLOCK)
                # width is 444/889 nominal
                width = ticks_diff(self._times[x + 1], self._times[x])
                if not 222 < width < 1111:
                    self.verbose and print('Bad block 3 Width', width, 'x', x)
                    raise RuntimeError(self.BADBLOCK)
                short = width < 666
                if not short:
                    bit ^= 1
                v <<= 1
                v |= bit
                bits += 1
                x += 1 + int(short)

            if self.verbose:
                 ss = '20-bit format {:020b} x={} nedges={} bits={}'
                 print(ss.format(v, x, nedges, bits))

            val = v & 0xff
            addr = (v >> 8) & 0xff
            ctrl = (v >> 16) & 1
        except RuntimeError as e:
            val, addr, ctrl = e.args[0], 0, 0
        # Set up for new data burst and run user callback
        self.do_callback(val, addr, ctrl)

class SONY_ABC(IR_RX):  # Abstract base class
    def __init__(self, pin, bits, callback, *args):
        # 20 bit block has 42 edges and lasts <= 39ms nominal. Add 4ms to time
        # for tolerances except in 20 bit case where timing is tight with a
        # repeat period of 45ms.
        t = int(3 + bits * 1.8) + (1 if bits == 20 else 4)
        super().__init__(pin, 2 + bits * 2, t, callback, *args)
        self._addr = 0
        self._bits = 20

    def decode(self, _):
        try:
            nedges = self.edge  # No. of edges detected
            self.verbose and print('nedges', nedges)
            if nedges > 42:
                raise RuntimeError(self.OVERRUN)
            bits = (nedges - 2) // 2
            if nedges not in (26, 32, 42) or bits > self._bits:
                raise RuntimeError(self.BADBLOCK)
            self.verbose and print('SIRC {}bit'.format(bits))
            width = ticks_diff(self._times[1], self._times[0])
            if not 1800 < width < 3000:  # 2.4ms leading mark for all valid data
                raise RuntimeError(self.BADSTART)
            width = ticks_diff(self._times[2], self._times[1])
            if not 350 < width < 1000:  # 600μs space
                raise RuntimeError(self.BADSTART)

            val = 0  # Data received, LSB 1st
            x = 2
            bit = 1
            while x <= nedges - 2:
                if ticks_diff(self._times[x + 1], self._times[x]) > 900:
                    val |= bit
                bit <<= 1
                x += 2
            cmd = val & 0x7f  # 7 bit command
            val >>= 7
            if nedges < 42:
                addr = val & 0xff  # 5 or 8 bit addr
                val = 0
            else:
                addr = val & 0x1f  # 5 bit addr
                val >>= 5  # 8 bit extended
        except RuntimeError as e:
            cmd = e.args[0]
            addr = 0
            val = 0
        self.do_callback(cmd, addr, val)

class SONY_12(SONY_ABC):
    def __init__(self, pin, callback, *args):
        super().__init__(pin, 12, callback, *args)

class SONY_15(SONY_ABC):
    def __init__(self, pin, callback, *args):
        super().__init__(pin, 15, callback, *args)

class SONY_20(SONY_ABC):
    def __init__(self, pin, callback, *args):
        super().__init__(pin, 20, callback, *args)

class IR:
    _active_high = True  # Hardware turns IRLED on if pin goes high.
    _space = 0  # Duty ratio that causes IRLED to be off
    timeit = False  # Print timing info

    @classmethod
    def active_low(cls):
        if ESP32:
            raise ValueError('Cannot set active low on ESP32')
        cls._active_high = False
        cls._space = 100

    def __init__(self, pin, cfreq, asize, duty, verbose):
        self._rmt = RMT(0, pin=pin, clock_div=80, tx_carrier = (cfreq, duty, 1))
            # 1μs resolution
        self._tcb = self._cb  # Pre-allocate
        self._arr = array('H', 0 for _ in range(asize))  # on/off times (μs)
        self._mva = memoryview(self._arr)
        # Subclass interface
        self.verbose = verbose
        self.carrier = False  # Notional carrier state while encoding biphase
        self.aptr = 0  # Index into array
        self._busy = False

    def _cb(self, t):  # T5 callback, generate a carrier mark or space
        self._busy = True
        t.deinit()
        p = self.aptr
        v = self._arr[p]
        if v == STOP:
            self._ch.pulse_width_percent(self._space)  # Turn off IR LED.
            self._busy = False
            return
        self._ch.pulse_width_percent(self._space if p & 1 else self._duty)
        self._tim.init(prescaler=84, period=v, callback=self._tcb)
        self.aptr += 1

    def busy(self):
        return not self._rmt.wait_done()
        return self._busy

    # Public interface
    # Before populating array, zero pointer, set notional carrier state (off).
    def transmit(self, addr, data, toggle=0, validate=False):  # NEC: toggle is unused
        while self.busy():
            pass
        t = ticks_us()
        if validate:
            if addr > self.valid[0] or addr < 0:
                raise ValueError('Address out of range', addr)
            if data > self.valid[1] or data < 0:
                raise ValueError('Data out of range', data)
            if toggle > self.valid[2] or toggle < 0:
                raise ValueError('Toggle out of range', toggle)
        self.aptr = 0  # Inital conditions for tx: index into array
        self.carrier = False
        self.tx(addr, data, toggle)  # Subclass populates ._arr
        self.trigger()  # Initiate transmission
        if self.timeit:
            dt = ticks_diff(ticks_us(), t)
            print('Time = {}μs'.format(dt))
        sleep_ms(1)  # Ensure ._busy is set prior to return

    # Subclass interface
    def trigger(self):  # Used by NEC to initiate a repeat frame
        self._rmt.write_pulses(tuple(self._mva[0 : self.aptr]))
    
    def append(self, *times):  # Append one or more time peiods to ._arr
        for t in times:
            self._arr[self.aptr] = t
            self.aptr += 1
            self.carrier = not self.carrier  # Keep track of carrier state
            self.verbose and print('append', t, 'carrier', self.carrier)

    def add(self, t):  # Increase last time value (for biphase)
        assert t > 0
        self.verbose and print('add', t)
        # .carrier unaffected
        self._arr[self.aptr - 1] += t


# Given an iterable (e.g. list or tuple) of times, emit it as an IR stream.
class Player(IR):

    def __init__(self, pin, freq=38000, verbose=False, asize=68):  # NEC specifies 38KHz
        super().__init__(pin, freq, asize, 33, verbose)  # Measured duty ratio 33%

    def play(self, lst):
        for x, t in enumerate(lst):
            self._arr[x] = t
        self.aptr = x + 1
        self.trigger()

_TBIT = const(500)  # Time (μs) for pulse of carrier


class MCE_TX(IR):
    valid = (0xf, 0x3f, 3)  # Max addr, data, toggle
    init_cs = 4  # http://www.hifi-remote.com/johnsfine/DecodeIR.html#OrtekMCE says 3

    def __init__(self, pin, freq=38000, verbose=False):
        super().__init__(pin, freq, 34, 30, verbose)

    def tx(self, addr, data, toggle):
        def checksum(v):
            cs = self.init_cs
            for _ in range(12):
                if v & 1:
                    cs += 1
                v >>= 1
            return cs

        self.append(2000, 1000, _TBIT)
        d = ((data & 0x3f) << 6) | (addr & 0xf)  | ((toggle & 3) << 4)
        d |= checksum(d) << 12
        self.verbose and print(bin(d))

        mask = 1
        while mask < 0x10000:
            bit = bool(d & mask)
            if bit ^ self.carrier:
                self.add(_TBIT)
                self.append(_TBIT)
            else:
                self.append(_TBIT, _TBIT)
            mask <<= 1

_TBURST = const(563)
_T_ONE = const(1687)

class NEC_TX(IR):
    valid = (0xffff, 0xff, 0)  # Max addr, data, toggle
    samsung = False

    def __init__(self, pin, freq=38000, verbose=False):  # NEC specifies 38KHz also Samsung
        super().__init__(pin, freq, 68, 33, verbose)  # Measured duty ratio 33%

    def _bit(self, b):
        self.append(_TBURST, _T_ONE if b else _TBURST)

    def tx(self, addr, data, _):  # Ignore toggle
        if self.samsung:
            self.append(4500, 4500)
        else:
            self.append(9000, 4500)
        if addr < 256:  # Short address: append complement
            if self.samsung:
              addr |= addr << 8
            else:
              addr |= ((addr ^ 0xff) << 8)
        for _ in range(16):
            self._bit(addr & 1)
            addr >>= 1
        data |= ((data ^ 0xff) << 8)
        for _ in range(16):
            self._bit(data & 1)
            data >>= 1
        self.append(_TBURST)

    def repeat(self):
        self.aptr = 0
        self.append(9000, 2250, _TBURST)
        self.trigger()  # Initiate physical transmission.

_T_RC5 = const(889)  # Time for pulse of carrier


class RC5_TX(IR):
    valid = (0x1f, 0x7f, 1)  # Max addr, data, toggle

    def __init__(self, pin, freq=36000, verbose=False):
        super().__init__(pin, freq, 28, 30, verbose)

    def tx(self, addr, data, toggle):  # Fix RC5X S2 bit polarity
        d = (data & 0x3f) | ((addr & 0x1f) << 6) | (((data & 0x40) ^ 0x40) << 6) | ((toggle & 1) << 11)
        self.verbose and print(bin(d))
        mask = 0x2000
        while mask:
            if mask == 0x2000:
                self.append(_T_RC5)
            else:
                bit = bool(d & mask)
                if bit ^ self.carrier:
                    self.add(_T_RC5)
                    self.append(_T_RC5)
                else:
                    self.append(_T_RC5, _T_RC5)
            mask >>= 1

# Philips RC6 mode 0 protocol
_T_RC6 = const(444)
_T2_RC6 = const(889)

class RC6_M0_TX(IR):
    valid = (0xff, 0xff, 1)  # Max addr, data, toggle

    def __init__(self, pin, freq=36000, verbose=False):
        super().__init__(pin, freq, 44, 30, verbose)

    def tx(self, addr, data, toggle):
        # leader, 1, 0, 0, 0
        self.append(2666, _T2_RC6, _T_RC6, _T2_RC6, _T_RC6, _T_RC6, _T_RC6, _T_RC6, _T_RC6)
        # Append a single bit of twice duration
        if toggle:
            self.add(_T2_RC6)
            self.append(_T2_RC6)
        else:
            self.append(_T2_RC6, _T2_RC6)
        d = (data & 0xff) | ((addr & 0xff) << 8)
        mask = 0x8000
        self.verbose and print('toggle', toggle, self.carrier, bool(d & mask))
        while mask:
            bit = bool(d & mask)
            if bit ^ self.carrier:
                self.append(_T_RC6, _T_RC6)
            else:
                self.add(_T_RC6)
                self.append(_T_RC6)
            mask >>= 1

class SONY_ABC_TX(IR):

    def __init__(self, pin, bits, freq, verbose):
        super().__init__(pin, freq, 3 + bits * 2, 30, verbose)
        if bits not in (12, 15, 20):
            raise ValueError('bits must be 12, 15 or 20.')
        self.bits = bits

    def tx(self, addr, data, ext):
        self.append(2400, 600)
        bits = self.bits
        v = data & 0x7f
        if bits == 12:
            v |= (addr & 0x1f) << 7
        elif bits == 15:
            v |= (addr & 0xff) << 7
        else:
            v |= (addr & 0x1f) << 7
            v |= (ext & 0xff) << 12
        for _ in range(bits):
            self.append(1200 if v & 1 else 600, 600)
            v >>= 1

# Sony specifies 40KHz
class SONY_12_TX(SONY_ABC):
    valid = (0x1f, 0x7f, 0)  # Max addr, data, toggle
    def __init__(self, pin, freq=40000, verbose=False):
        super().__init__(pin, 12, freq, verbose)

class SONY_15_TX(SONY_ABC):
    valid = (0xff, 0x7f, 0)  # Max addr, data, toggle
    def __init__(self, pin, freq=40000, verbose=False):
        super().__init__(pin, 15, freq, verbose)

class SONY_20_TX(SONY_ABC):
    valid = (0x1f, 0x7f, 0xff)  # Max addr, data, toggle
    def __init__(self, pin, freq=40000, verbose=False):
        super().__init__(pin, 20, freq, verbose)

class IRBlaster:
    def __init__(self, rx_pin=D3_PIN, tx_pin=D4_PIN, json_file='ir_codes.json'):
        self.rx_pin = Pin(rx_pin, Pin.IN)
        self.tx_pin = Pin(tx_pin, Pin.OUT)
        self.file = json_file
        self.signal_data = self._load_json()

        self.recv_classes = (NEC_8, NEC_16, SONY_12, SONY_15, SONY_20, RC5_IR, RC6_M0, MCE, SAMSUNG)
        self.recv_names = ("NEC_8", "NEC_16", "SONY_12", "SONY_15", "SONY_20", "RC5", "RC6", "MCE", "SAMSUNG")

        self.tx_classes = {
            "NEC_8": NEC_TX, "NEC_16": NEC_TX, "SAMSUNG": NEC_TX,
            "SONY_12": SONY_12_TX, "SONY_15": SONY_15_TX, "SONY_20": SONY_20_TX,
            "RC5": RC5_TX, "RC6": RC6_M0_TX
        }

        self.received = False
        self.result = {}
        self.tx_instances = {}

    def _load_json(self):
        try:
            with open(self.file, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_all_to_file(self):
        try:
            with open(self.file, 'w') as f:
                json.dump(self.signal_data, f)
        except Exception as e:
            print("❌ Lỗi ghi file:", e)

    def _save_to_signal_data(self):
        new_entry = (self.result["device"], self.result["protocol"], self.result["data"], self.result["addr"])

        updated = False
        for i, entry in enumerate(self.signal_data):
            if isinstance(entry, (list, tuple)) and entry[0] == self.result["device"]:
                self.signal_data[i] = new_entry
                updated = True
                print("♻️ Đã cập nhật tín hiệu cho thiết bị:", new_entry)
                break

        if not updated:
            self.signal_data.append(new_entry)
            print("💾 Đã thêm mới tín hiệu:", new_entry)

        self._save_all_to_file()


    def checkscan(self, signal_name):
        for entry in self.signal_data:
            if isinstance(entry, (list, tuple)) and entry[0] == signal_name:
                return True
        return False

    async def scan(self, signal_name):
        self.received = False
        self.result = {}
        self.tx_pin.value(0)

        print(f"🚀 Bắt đầu quét cho thiết bị: {signal_name}")

        while not self.received:
            for i, cls in enumerate(self.recv_classes):
                print(f"🔍 Đang thử: {self.recv_names[i]}")

                self.invalid = False  # Cờ để phát hiện giao thức không hợp lệ

                def make_cb(index):
                    def cb(data, addr, ctrl):
                        if data >= 0:
                            print(f"✅ Đã nhận: {signal_name} | {self.recv_names[index]} | 0x{data:02x}")
                            self.result = {
                                "device": signal_name,
                                "protocol": self.recv_names[index],
                                "data": data,
                                "addr": addr
                            }
                            self.received = True
                        else:
                            self.invalid = True  # Giao thức không phù hợp
                    return cb

                ir = cls(self.rx_pin, make_cb(i))
                ir.error_function(lambda msg: None)  # Ẩn thông báo lỗi

                try:
                    t0 = time.ticks_ms()
                    while time.ticks_diff(time.ticks_ms(), t0) < 700:
                        if self.received or self.invalid:
                            break
                        time.sleep(0.05)
                finally:
                    ir.close()
                    gc.collect()

                if self.received:
                    break

        print("🎉 Đã nhận tín hiệu, lưu vào RAM và file.")
        self._save_to_signal_data()


    async def send(self, signal_name):
        match = None
        for d in self.signal_data:
            if d[0] == signal_name:
                match = d
                break

        if not match:
            print(f"⚠️ Không tìm thấy tín hiệu '{signal_name}' trong RAM.")
            return

        _, proto_name, data, addr = match
        cls = self.tx_classes.get(proto_name)

        if not cls:
            print(f"❌ Không hỗ trợ giao thức: {proto_name}")
            return

        if proto_name not in self.tx_instances:
            try:
                self.tx_instances[proto_name] = cls(self.tx_pin, 38000)
            except OSError as e:
                print(f"❌ Lỗi transmitter: {e}")
                return

        irb = self.tx_instances[proto_name]
        irb.transmit(addr, data, 0, True)
        print(f"📤 Đã gửi: {signal_name} | {proto_name} | addr={addr}, data={data}")

    def show_signal_list(self):
        if not self.signal_data:
            print("📭 Chưa có tín hiệu nào được lưu.")
            return

        print("📋 Danh sách tín hiệu đã lưu:")
        for i, entry in enumerate(self.signal_data):
            device, proto, data, addr = entry
            print(f"{i+1}. {device} | {proto} | data=0x{data:02X} | addr={addr}")

    def delete_signal(self, signal_name):
        found = False
        for i, entry in enumerate(self.signal_data):
            if isinstance(entry, (list, tuple)) and entry[0] == signal_name:
                del self.signal_data[i]
                found = True
                print(f"🗑️ Đã xóa tín hiệu: {signal_name}")
                break

        if not found:
            print(f"⚠️ Không tìm thấy tín hiệu có tên: {signal_name}")
        else:
            self._save_all_to_file()

