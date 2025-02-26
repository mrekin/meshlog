#App constants
VERSION = "0.13"
TITLE = "Meshtastic Serial Logger"
SUB_TITLE = "Usefull serial monitor with small extentions for meshtastic logs"
CSS_PATH = "css.tcss"
LOG_FILENAME = "service.log"
LOG_DIR = "logs"
CONFIG_DIR = "config"
FILES_DIR = "files"
LABELS_FILE = "labels.txt"

#RichLog
LOG_INITIAL_TEXT = '''
> Use `Tab`,`Arrows`,`Space` and/or `Mouse` to navigate
> Use `Shift`+`LeftMButton` to select text
> Use `Enter` to copy selected text
> Use `ESC` to cancel selection
\n\n
'''

# Settings ({label text}, {cfg param})
CFG_LOG2FILE = ('Log to file','logToFile')
CFG_LOGS_BY_PORT = ('Separate port logs','separatePortLogs')
CFG_LOGS_BY_SESSION = ('Separate session logs', 'separateSessionLogs')
CFG_AUTO_RECONNECT = ('autoReconnect', 'autoReconnect')
CFG_BAUDRATE = ('baudrate', 'baudrate')
CFG_SENDTO = ('Send to', 'sendTo')
CFG_NRF52_BOOTLOADER_URL = ('NRF52 Bootloader URL', 'nrf52BootloaderURL')
CFG_NRF52_FULLERASE_URL = ('NRF52 Fullerase URL', 'nrf52FulleraseURL')

def get_variable(key) -> tuple|list|None: 
    vars = [globals()[var] for var in globals() if var.startswith('CFG_') and isinstance(globals()[var], tuple)]
    if key:
        for v in vars:
            if v[1] == key:
                return v
        return None
    return vars


#Ports
PORTS_RENEWAL_DELAY = 1 #sec