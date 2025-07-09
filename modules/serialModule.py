try:
    import serial
    import serial.tools.list_ports
    from serial import Serial
    from serial.tools.list_ports_common import ListPortInfo
except ImportError:
    msg = """ERROR: pyserial library not found
    Install pyserial library
    pip install pyserial"""
    print(msg)
    exit(1)

import asyncio
import binascii
import platform
import re

# Other Imports
import time
from enum import Enum
from queue import Empty

if platform.system() != "Windows":
    import termios


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
    retry = False
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
            t(self.state, self.prevState, self.port, self.baud)

    def setPort(self, port=None, baud=115200):
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

    async def stopLoopM(self):
        self.stopLoop = True
        while self.state in (States.Active, States.Reconnecting, States.Closing):
            asyncio.sleep(0.1)

    def mainLoop(
        self,
        prt: ListPortInfo = None,
        baud=115200,
        retry=False,
        reconnectDelay=0.2,
        waitNewPort=False,
        ports=None,
        sendOnConnect: str = None,
    ):
        if waitNewPort:
            prt = self.catch_new_port(ports)
        self.setPort(prt, baud)
        self.stopLoop = False
        self.retry = retry
        res = False
        ## Begin

        ser = None
        self.log.info(
            f"> Opening port: {self.port.name} ({self.port.device}, {self.port.hwid})"
        )
        self.setState(States.Idle)
        while not self.stopLoop:
            try:
                squit = self.queue.get(block=False, timeout=0.1)
            except Empty:
                squit = False
            if squit:
                self.log.info("Exiting logging")
                if ser:
                    ser.close()
                res = True
                break

            if ser is None:
                try:
                    if not self.port:
                        raise Exception("No port selected")
                    if platform.system() != "Windows":
                        with open(self.devPath, encoding="utf8") as f:
                            attrs = termios.tcgetattr(f)
                            attrs[2] = attrs[2] & ~termios.HUPCL
                            termios.tcsetattr(f, termios.TCSAFLUSH, attrs)
                            f.close()
                        time.sleep(0.1)
                    # ser = Serial(self.port.device,baud,timeout=1)
                    ser = Serial()
                    ser.port = self.port.device
                    ser.baudrate = baud
                    ser.timeout = 1
                    # ser.dtr =0
                    ser.open()
                except Exception as e:
                    ser = None
                    if not self.retry:
                        self.log.error(f"Connection error - {e}")
                        break
                    # self.log.info(".")
                    self.setState(States.Reconnecting)
                    time.sleep(reconnectDelay)
                    continue

            if ser:
                try:
                    data = ser.readline()
                    self.setState(States.Active)
                    if len(data) > 0:
                        try:
                            line = data.decode("utf-8").rstrip()
                        except UnicodeDecodeError:
                            hex_data = binascii.hexlify(data)
                            line = hex_data
                        clean_text = re.sub(
                            r"\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?",
                            "",
                            line,
                        )
                        clean_text = clean_text.replace("\x00", "")
                        if len(clean_text) > 0:
                            self.log.info(clean_text)

                        if "any key" in clean_text:
                            self.log.info("> Sending \\n for factory erase")
                            ser.write("\\n".encode())
                            self.log.info("> Done. Enter DFU mode and flash firmware.")
                            self.stopLoop = True
                            res = True
                    if sendOnConnect:
                        self.log.info(f"> Sending '{sendOnConnect}'")
                        ser.write(sendOnConnect.encode())
                        self.log.info("> Done.")
                        self.stopLoop = not retry
                except KeyboardInterrupt:
                    self.queue.put(True)
                    self.log.info("Ctrl + C pressed")
                except Exception:
                    # self.log.info('Serial readLine error happens, reconnecting')
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
        ports = [p for p in ports if p.hwid != "n/a"]
        return ports, self.port

    def catch_new_port(self, ports):
        if not ports:
            #            ports = self.get_available_ports()[0]
            ports = []
        w = True
        while w:
            newPorts = self.get_available_ports()[0]
            # find port in new ports which not in old ports
            if ports != newPorts:
                for p in newPorts:
                    if p not in ports:
                        return p
                ports = newPorts

    def check_new_port(self, ports):
        if not ports:
            ports = self.get_available_ports()[0]

        newPorts = self.get_available_ports()[0]
        # find port in new ports which not in old ports
        if ports != newPorts:
            for p in newPorts:
                if p not in ports:
                    return p
        return None

    async def readNewSerial(self, ports=None, sendOnConnect: str = None):
        await self.stopLoopM()
        # asyncio.create_task(asyncio.to_thread(self.mainLoop(retry= False, waitNewPort= True, ports= ports, sendOnConnect= sendOnConnect)))
        return self.mainLoop(
            retry=False, waitNewPort=True, ports=ports, sendOnConnect=sendOnConnect
        )


def get_available_ports():
    ports = list(serial.tools.list_ports.comports())
    return ports
