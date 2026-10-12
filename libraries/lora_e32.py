from setting import *
from utility import *
from machine import Pin, UART
import time
import json



class ebyteE32:
    ''' class to interface an ESP32 via serial commands to the EBYTE E32 Series LoRa modules '''
    
    # UART ports
    PORT = { 'U1':1, 'U2':2 }
    # UART parity strings
    PARSTR = { '8N1':'00', '8O1':'01', '8E1':'10' }
    PARINV = { v:k for k, v in PARSTR.items() }
    # UART parity bits
    PARBIT = { 'N':None, 'E':0, 'O':1 }
    # UART baudrate
    BAUDRATE = { 1200:'000', 2400:'001', 4800:'010', 9600:'011',
                 19200:'100', 38400:'101', 57600:'110', 115200:'111' }
    BAUDRINV = { v:k for k, v in BAUDRATE.items() }
    # LoRa datarate
    DATARATE = { '0.3k':'000', '1.2k':'001', '2.4k':'010',
                 '4.8k':'011', '9.6k':'100', '19.2k':'101' }
    DATARINV = { v:k for k, v in DATARATE.items() }
    # Commands
    CMDS = { 'setConfigPwrDwnSave':0xC0,
             'getConfig':0xC1,
             'setConfigPwrDwnNoSave':0xC2,
             'getVersion':0xC3,
             'reset':0xC4 }
    # operation modes (set with M0 & M1)
    OPERMODE = { 'normal':'00', 'wakeup':'10', 'powersave':'01', 'sleep':'11' }
    # model frequency ranges (MHz)
    FREQ = { 170:[160, 170, 173], 400:[410, 470, 525], 433:[410, 433, 441],
             868:[862, 868, 893], 915:[900, 915, 931] }
    # version info frequency
    FREQV = { '0x32':433, '0x38':470, '0x45':868, '0x44':915, '0x46':170 }
    # model maximum transmision power
    # 20dBm = 100mW - 27dBm = 500 mW - 30dBm = 1000 mW (1 W)
    MAXPOW = { 'T20':0, 'T27':1, 'T30':2 }
    # transmission mode
    TRANSMODE = { 0:'transparent', 1:'fixed' }
    # IO drive mode
    IOMODE = { 0:'TXD AUX floating output, RXD floating input',
               1:'TXD AUX push-pull output, RXD pull-up input' }
    # wireless wakeup times from sleep mode
    WUTIME = { 0b000:'250ms', 0b001:'500ms', 0b010:'750ms', 0b011:'1000ms',
               0b100:'1250ms', 0b101:'1500ms', 0b110:'1750ms', 0b111:'2000ms' }
    # Forward Error Correction (FEC) mode
    FEC = { 0:'off', 1:'on' }
    # transmission power T20/T27/T30 (dBm)
    TXPOWER = { 0b00:['20dBm', '27dBm', '30dBm'],
                0b01:['17dBm', '24dBm', '27dBm'],
                0b10:['14dBm', '21dBm', '24dBm'],
                0b11:['10dBm', '18dBm', '21dBm'] }
    

    def __init__(self, tx_pin, rx_pin, debug=False):
        ''' constructor for ebyte E32 LoRa module '''
        # configuration in dictionary
        self.config = {}
        self.config['model'] = '433T20S'           # E32 model (default 868T20D)
        self.config['port'] = 'U1'                 # UART channel on the ESP (default U1)
        self.config['baudrate'] = 9600             # UART baudrate (default 9600)
        self.config['parity'] = '8N1'              # UART Parity (default 8N1)
        self.config['datarate'] = '2.4k'           # wireless baudrate (default 2.4k)
        self.config['address'] = 0x0000            # target address (default 0x0000)
        self.config['channel'] = 0x06              # target channel (0-31, default 0x06)
        self.calcFrequency()                       # calculate frequency (min frequency + channel*1 MHz)
        self.config['transmode'] = 0       # transmission mode (default 0 - tranparent)
        self.config['iomode'] = 1                  # IO mode (default 1 = not floating)
        self.config['wutime'] = 0                  # wakeup time from sleep mode (default 0 = 250ms)
        self.config['fec'] = 1                     # forward error correction (default 1 = on)
        self.config['txpower'] = 0                 # transmission power (default 0 = 20dBm/100mW)
        self.debug = debug
        self.received_data = None
        self.serdev = UART(1, baudrate=9600, tx=tx_pin, rx=rx_pin)
        par = ebyteE32.PARBIT.get(str(self.config['parity'])[1])
        print(f"Setting UART parity: {par}")  # Debug
        self.serdev.init(baudrate=self.config['baudrate'], bits=8, parity=par, stop=1)
                

    def start(self, address, channel, transmode):
        ''' Start the ebyte E32 LoRa module '''
        try:
            self.config['address'] = address        
            self.config['channel'] = channel             
            self.config['transmode'] = transmode       
            # check parameters
            print("Current config: ", self.config)
            if int(self.config['model'].split('T')[0]) not in ebyteE32.FREQ:
                self.config['model'] = '868T20D'
            if self.config['port'] not in ebyteE32.PORT:
                self.config['port'] = 'U1'
            if int(self.config['baudrate']) not in ebyteE32.BAUDRATE:    
                self.config['baudrate'] = 9600
            if self.config['parity'] not in ebyteE32.PARSTR:
                self.config['parity'] = '8N1'
            if self.config['datarate'] not in ebyteE32.DATARATE:
                self.config['datarate'] = '2.4k'
            if self.config['channel'] > 31:
                self.config['channel'] = 31
            
            # set config to the ebyte E32 LoRa module
            print("Sending config to E32 LoRa module...")
            self.setConfig('setConfigPwrDwnSave')
            return "OK"
        
        except Exception as E:
            if self.debug:
                print(f"Error during UART initialization: {E}")
            return "NOK"
        

    def sendMessageTo(self, to_address, to_channel, payload, useChecksum=False):
        try:
            # check payload
            if type(payload) != dict:
                print('payload is not a dictionary')
                return 'NOK'
            # encode message
            msg = []
            if self.config['transmode'] == 1:     # only for fixed transmission mode
                msg.append(to_address//256)          # high address byte
                msg.append(to_address%256)           # low address byte
                msg.append(to_channel)               # channel
            js_payload = json.dumps(payload)     # convert payload to JSON string 
            for i in range(len(js_payload)):      # message
                msg.append(ord(js_payload[i]))    # ascii code of character
            if useChecksum:                       # attach 2's complement checksum
                msg.append(int(self.calcChecksum(js_payload), 16))
            # debug
            if self.debug:
                print(msg)
            # wait for idle module
            time.sleep_ms(300)
            # send the message
            self.serdev.write(bytes(msg))
            print('done')
            return "OK"
        
        except Exception as E:
            if self.debug:
                print('Error on sendMessage: ',E)
            return "NOK"
            
    def sendMessage(self, payload, useChecksum=False):
        try:
            # check payload
            if type(payload) != dict:
                print('payload is not a dictionary')
                return 'NOK'
            # encode message
            msg = []
            js_payload = json.dumps(payload)     # convert payload to JSON string 
            for i in range(len(js_payload)):      # message
                msg.append(ord(js_payload[i]))    # ascii code of character
            if useChecksum:                       # attach 2's complement checksum
                msg.append(int(self.calcChecksum(js_payload), 16))
            # debug
            if self.debug:
                print(msg)
            # wait for idle module
            time.sleep_ms(300)
            # send the message
            self.serdev.write(bytes(msg))
            print('done')
            return "OK"
        
        except Exception as E:
            if self.debug:
                print('Error on sendMessage: ',E)
            return "NOK"
        
    def recvMessage(self, useChecksum=False):
        ''' Receive payload messages from ebyte E32 LoRa modules in transparent or fixed mode. '''
        try:
            # receive message
            js_payload = self.serdev.read()
            if self.debug:
                print(js_payload)

            if js_payload is None:
                self.received_data = None
                return None

            # decode bytes to string
            msg = ''.join([chr(b) for b in js_payload])

            # checksum check
            if useChecksum:
                cs = int(self.calcChecksum(msg), 16)
                if cs != 0:
                    return None
                msg = msg[:-1]  # remove checksum byte
            # JSON to dictionary
            try:
                self.received_data = json.loads(msg)   
            except Exception as e:
                if self.debug:
                    print("Error decoding JSON:", e)
                self.received_data = None
            return self.received_data

        except Exception as E:
            if self.debug:
                print('Error on recvMessage:', E)
            return None
        
    
    def calcChecksum(self, payload):
        ''' Calculates checksum for sending/receiving payloads. Sums the ASCII character values mod256 and returns
            the lower byte of the two's complement of that value in hex notation. '''

        return '%2X' % (-(sum(ord(c) for c in payload) % 256) & 0xFF)

    def reset(self):
        ''' Reset the ebyte E32 Lora module '''
        try:
            # send the command
            res = self.sendCommand('reset')
            # discard result
            return "OK"
          
        except Exception as E:
            if self.debug:
                print("error on reset", E)
            return "NOK"


    def stop(self):
        ''' Stop the ebyte E32 LoRa module '''
        try:
            if self.serdev != None:
                self.serdev.deinit()
                del self.serdev
            return "OK"
            
        except Exception as E:
            if self.debug:
                print("error on stop UART", E)
            return "NOK"
        
    
    def sendCommand(self, command):
        ''' Send a command to the ebyte E32 LoRa module.
            The module has to be in sleep mode '''
        try:
            # put into sleep mode
            self.setOperationMode('sleep')
            # send command
            HexCmd = ebyteE32.CMDS.get(command)
            if HexCmd in [0xC0, 0xC2]:        # set config to device
                header = HexCmd
                HexCmd = self.encodeConfig()
                HexCmd[0] = header
            else:                             # get config, get version, reset
                HexCmd = [HexCmd]*3
            if self.debug:
                print(HexCmd)
            self.serdev.write(bytes(HexCmd))
            # wait for result
            time.sleep_ms(50)
            # read result
            if command == 'reset':
                result = ''
            else:
                result = self.serdev.read()
                # wait for result
                time.sleep_ms(50)
                # debug
                if self.debug:
                    print(result)
            return result
        
        except Exception as E:
            if self.debug:
                print('Error on sendCommand: ',E)
            return "NOK"
        
        
    
    def getVersion(self):
        ''' Get the version info from the ebyte E32 LoRa module '''
        try:
            # send the command
            result = self.sendCommand('getVersion')
            # check result
            if len(result) != 4:
                return "NOK"
            # decode result
            freq = ebyteE32.FREQV.get(hex(result[1]),'unknown')
            # show version
            if result[0] == 0xc3:
                print('================= E32 MODULE ===================')
                print('model       \t%dMhz'%(freq))
                print('version     \t%d'%(result[2]))
                print('features    \t%d'%(result[3]))
                print('================================================')
            return "OK"
        
        except Exception as E:
            if self.debug:
                print('Error on getVersion: ',E)
            return "NOK"
        
    
    def getConfig(self):
        ''' Get config parameters from the ebyte E32 LoRa module '''
        try:
            # send the command
            result = self.sendCommand('getConfig')
            print(result)
            # check result
            if len(result) != 6:
                return "NOK"
            # decode result
            self.decodeConfig(result)
            # show config
            self.showConfig()
            return "OK"

        except Exception as E:
            if self.debug:
                print('Error on getConfig: ',E)
            return "NOK"  
    

    def decodeConfig(self, message):
        ''' decode the config message from the ebyte E32 LoRa module to update the config dictionary '''
        # message byte 0 = header
        header = int(message[0])
        # message byte 1 & 2 = address
        self.config['address'] = int(message[1])*256 + int(message[2])
        # message byte 3 = speed (parity, baudrate, datarate)
        bits = '{0:08b}'.format(message[3])
        self.config['parity'] = ebyteE32.PARINV.get(bits[0:2])
        self.config['baudrate'] = ebyteE32.BAUDRINV.get(bits[2:5])
        self.config['datarate'] = ebyteE32.DATARINV.get(bits[5:])
        # message byte 4 = channel
        self.config['channel'] = int(message[4])
        # message byte 5 = option (transmode, iomode, wutime, fec, txpower)
        bits = '{0:08b}'.format(message[5])
        self.config['transmode'] = int(bits[0:1])
        self.config['iomode'] = int(bits[1:2])
        self.config['wutime'] = int(bits[2:5])
        self.config['fec'] = int(bits[5:6])
        self.config['txpower'] = int(bits[6:])
        
    
    def encodeConfig(self):
        ''' encode the config dictionary to create the config message of the ebyte E32 LoRa module '''
        # Initialize config message
        message = []
        # message byte 0 = header
        message.append(0xC0)
        # message byte 1 = high address
        message.append(self.config['address']//256)
        # message byte 2 = low address
        message.append(self.config['address']%256)
        # message byte 3 = speed (parity, baudrate, datarate)
        bits = '0b'
        bits += ebyteE32.PARSTR.get(self.config['parity'])
        bits += ebyteE32.BAUDRATE.get(self.config['baudrate'])
        bits += ebyteE32.DATARATE.get(self.config['datarate'])
        message.append(int(bits))
        # message byte 4 = channel
        message.append(self.config['channel'])
        # message byte 5 = option (transmode, iomode, wutime, fec, txpower)
        bits = '0b'
        bits += str(self.config['transmode'])
        bits += str(self.config['iomode'])
        bits += '{0:03b}'.format(self.config['wutime'])
        bits += str(self.config['fec'])
        bits += '{0:02b}'.format(self.config['txpower'])
        message.append(int(bits))
        return message
    

    def showConfig(self):
        ''' Show the config parameters of the ebyte E32 LoRa module on the shell '''
        print('=================== CONFIG =====================')
        print('model       \tE32-%s'%(self.config['model']))
        print('frequency   \t%dMhz'%(self.config['frequency']))
        print('address     \t0x%04x'%(self.config['address']))
        print('channel     \t0x%02x'%(self.config['channel']))
        print('datarate    \t%sbps'%(self.config['datarate']))                
        print('port        \t%s'%(self.config['port']))
        print('baudrate    \t%dbps'%(self.config['baudrate']))
        print('parity      \t%s'%(self.config['parity']))
        print('transmission\t%s'%(ebyteE32.TRANSMODE.get(self.config['transmode'])))
        print('IO mode     \t%s'%(ebyteE32.IOMODE.get(self.config['iomode'])))
        print('wakeup time \t%s'%(ebyteE32.WUTIME.get(self.config['wutime'])))
        print('FEC         \t%s'%(ebyteE32.FEC.get(self.config['fec'])))
        maxp = ebyteE32.MAXPOW.get(self.config['model'][3:6], 0)
        print('TX power    \t%s'%(ebyteE32.TXPOWER.get(self.config['txpower'])[maxp]))
        print('================================================')


    def waitForDeviceIdle(self):
        ''' Wait for the E32 LoRa module to become idle (AUX pin high) '''
        count = 0
        # loop for device busy
        while not self.AUX.value():
            # increment count
            count += 1
            # maximum wait time 100 ms
            if count == 10:
                break
            # sleep for 10 ms
            time.sleep_ms(10)
            
            
    def saveConfigToJson(self):
        ''' Save config dictionary to JSON file ''' 
        with open('E32config.json', 'w') as outfile:  
            json.dump(self.config, outfile)    


    def loadConfigFromJson(self):
        ''' Load config dictionary from JSON file ''' 
        with open('E32config.json', 'r') as infile:
            result = json.load(infile)
        print(self.config)
        
    
    def calcFrequency(self):
        ''' Calculate the frequency (= minimum frequency + channel * 1MHz)''' 
        # get minimum and maximum frequency
        freqkey = int(self.config['model'].split('T')[0])
        minfreq = ebyteE32.FREQ.get(freqkey)[0]
        maxfreq = ebyteE32.FREQ.get(freqkey)[2]
        # calculate frequency
        freq = minfreq + self.config['channel']
        if freq > maxfreq:
            self.config['frequency'] = maxfreq
            self.config['channel'] = hex(maxfreq - minfreq)
        else:
            self.config['frequency'] = freq

        
    def setTransmissionMode(self, transmode):
        ''' Set the transmission mode of the E32 LoRa module '''
        if transmode != self.config['transmode']:
            self.config['transmode'] = transmode
            self.setConfig('setConfigPwrDwnSave')
            
            
    def setConfig(self, save_cmd):
        ''' Set config parameters for the ebyte E32 LoRa module '''
        try:
            # send the command
            result = self.sendCommand(save_cmd)
            # check result
            if len(result) != 6:
                return "NOK"
            # debug
            if self.debug:
                # decode result
                self.decodeConfig(result)
                # show config
                self.showConfig()
            # save config to json file
            self.saveConfigToJson()
            return "OK"
        
        except Exception as E:
            if self.debug:
                print('Error on setConfig: ',E)
            return "NOK"  


    def setOperationMode(self, mode):
        ''' Set operation mode of the E32 LoRa module '''
        # get operation mode settings (default normal)
        bits = ebyteE32.OPERMODE.get(mode, '00')
        # wait a moment
        time.sleep_ms(50)