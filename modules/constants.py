#App constants
VERSION = "0.13"
TITLE = "Meshtastic Serial Logger"
SUB_TITLE = "Usefull serial monitor with small extentions for meshtastic logs"
CSS_PATH = "css.tcss"
LOG_FILENAME = "service.log"
LOG_DIR = "logs"
CONFIG_DIR = "config"
LABELS_FILE = "labels.txt"

#RichLog
LOG_INITIAL_TEXT = '''
> Use `Tab`,`Arrows`,`Space` and/or `Mouse` to navigate
> Use `Shift`+`LeftMButton` to select text
> Use `Enter` to copy selected text
> Use `ESC` to cancel selection
\n\n
'''

# Settings
CFG_LOG2FILE = 'Log to file'
CFG_LOGS_BY_PORT = 'Separate port logs'
CFG_LOGS_BY_SESSION = 'Separate session logs'
CFG_AUTO_RECONNECT = 'autoReconnect'
CFG_BAUDRATE = 'baudrate'
CFG_SENDTO = 'Send to'

#Ports
PORTS_RENEWAL_DELAY = 1 #sec