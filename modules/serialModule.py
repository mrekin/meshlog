try:
    import serial
    from serial import Serial
    import serial.tools.list_ports
except (ImportError):
    msg = """ERROR: pyserial library not found
    Install pyserial library
    pip install pyserial"""
    print(msg)
    exit(1)

# Other Imports
import time
from signal import signal, SIGINT
from sys import exit
from queue import Empty
import time
from time import asctime
import binascii
import queue
from enum import Enum

# Port Configuration
class States(Enum):
    Idle = 0
    Active = 1
    Reconnecting = 2
    Closing = 3
    Stopped = 4
    
class SerialModule(object):
    log = None
    queue = None
    port = None
    baud = None
    stopLoop = False
    tgSubs = []
    state = States.Idle
    prevState = States.Idle
    
    def __init__(self, logger, queue):
        self.log = logger
        self.queue = queue
        
    def stateInfoSubscribe(self, callback):
        # append callback to triggerSubs
        self.tgSubs.append(callback)
    
    def stateInfoUnSubscribe(self, callback):
        # remove callback from triggerSubs
        if callback in self.tgSubs:
            self.tgSubs.remove(callback)
    
    def triggerSubs(self):
        for t in self.tgSubs:
            t(self.state,self.prevState, self.port, self.baud)
    
    def setPort(self, port = None, baud = 115200):
        self.port = port
        self.baud = baud

    def clean(self):
        self.port = None
        self.baud = None        

    def setState(self, state):
        changed = self.state != state
        self.prevState = self.state
        self.state = state
        if changed or state == States.Reconnecting:
            self.triggerSubs()
        
    def stopLoop(self):
        self.stopLoop = True
        
    def mainLoop(self, prt = None, baud = 115200, retry = False):
        self.setPort(prt, baud)
        self.stopLoop = False
        res = False
        ## Begin
        ser = None
        self.log.info(f"> Opening port: {prt}")
        self.setState(States.Idle)
        while not self.stopLoop:
            try:
                squit = self.queue.get(block=False, timeout=0.1)
            except Empty as e:
                squit = False            
            if squit == True:
                self.log.info("Exiting logging")
                if ser:
                    ser.close()
                res = True
                break

            if ser == None:
                try:
                    if not prt: raise Exception("No port selected")
                    ser = Serial(prt,baud,timeout=1)
                except Exception as e:
                    ser = None
                    if retry == False:
                        self.log.error(f"Connection error - {e}")
                        break
                    #self.log.info(".")
                    self.setState(States.Reconnecting)
                    time.sleep(0.2)
                    continue

            if ser !=None:
                try:
                    data = ser.readline()
                    self.setState(States.Active)
                    if len(data) > 0:
                        try:
                            self.log.info(data.decode("utf-8").rstrip())
                        except UnicodeDecodeError as e:
                            hex_data = binascii.hexlify(data)
                            self.log.info(hex_data)
                except KeyboardInterrupt as e:
                    self.queue.put(True)
                    self.log.info("Ctrl + C pressed")
                except Exception as ee:
                    #self.log.info('Serial readLine error happens, reconnecting')
                    ser = None
        self.setState(States.Closing)
        if ser:
            ser.close()
        ser = None
        self.clean()
        self.setState(States.Stopped)
        return res    

    def get_available_ports(self):
        ports = list(serial.tools.list_ports.comports())
        return ports, self.port 
        
def get_available_ports():
    ports = list(serial.tools.list_ports.comports())
    return ports   