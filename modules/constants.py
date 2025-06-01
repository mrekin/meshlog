from enum import Enum

#App constants
VERSION = "0.3"
TITLE = f"Meshtastic Serial Logger ({VERSION})"
SUB_TITLE = "Useful serial monitor with small extentions for meshtastic logs"
CSS_PATH = "css.tcss"
LOG_FILENAME = "service.log"
LOG_DIR = "logs"
CONFIG_DIR = "config"
FILES_DIR = "files"
LABELS_FILE = "labels.txt"
DEF_CONFIG_URL = "https://api.github.com/repos/mrekin/meshlog/contents/config"

#RichLog
LOG_INITIAL_TEXT = '''
> Use `Tab`,`Arrows`,`Space` and/or `Mouse` to navigate
> Use `Shift`+`LeftMButton` to select text
> Use `Enter` to copy selected text
> Use `ESC` to cancel selection
\n\n
'''

# Settings ({label text}, {cfg param})
CFG_LOG2FILE = 'logToFile'
CFG_LOGS_BY_PORT = 'separatePortLogs'
CFG_LOGS_BY_SESSION = 'separateSessionLogs'
CFG_AUTO_RECONNECT = 'autoReconnect'
CFG_BAUDRATE = 'baudrate'
CFG_SENDTO = 'sendTo'
CFG_BOOTLOADER_URL = 'bootloaderURL'
CFG_FULLERASE_URL = 'fulleraseURL'
CFG_FIRMWARE_URL = 'firmwareURL'

cfg_labels = {
    'logToFile': 'Log to file',
    'separatePortLogs': 'Separate port logs',
    'separateSessionLogs': 'Separate session logs',
    'sendTo': 'Send to',
    'nrf52BootloaderURL': 'NRF52 Bootloader URL',
    'nrf52FulleraseURL': 'NRF52 Fullerase URL',
}


def getVarName(key) -> str:
    if key in cfg_labels:
        return cfg_labels[key]
    return key

#Ports
PORTS_RENEWAL_DELAY = 1 #sec

# Platforms
class PLATFORMS(Enum):
    NRF52 = 0
    RP2040 = 1
    ESP32 = 2
    
UF2_TXT_TOKENS = {
    'board_id': r'Board-ID: (.*)$',
    'softdevice' : r'SoftDevice: (.*)$',
    'bootloader' : r'UF2 Bootloader v*([0-9\\.]+)',
}