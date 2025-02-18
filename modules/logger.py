import logging
from logging.handlers import RotatingFileHandler



class CustomHandler(logging.Handler):
    def __init__(self, callback):
        #super().__init__()
        self.callback = callback
        logging.Handler.__init__(self=self)

    def emit(self, record):
        msg = self.format(record)
        self.callback(msg)
        
class SLogger():
    logger = None
    
    def __init__(self):
        self.logger = self.getLogger()
        self.logger.setLevel(logging.DEBUG)
    
    def addCustomLogger(self, callback):
        ch = CustomHandler(callback)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter(fmt='%(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        #ch.callback("Test1111")
        #self.logger.info("Test message")
    
    def addConsoleLogger(self):
        self.logger = logging.getLogger('Serial Logger')
        self.logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('\033[34m%(asctime)s\033[0m  21~  %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)    
    
    def addFileHandler(self, filename, maxbytes = 500000):    
        # create file handler which logs even debug messages
        fh = RotatingFileHandler(filename, maxBytes=maxbytes)
        fh.setLevel(logging.DEBUG)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s ~  %(message)s')
        fh.setFormatter(formatter)
        # add the handlers to the logger
        self.logger.addHandler(fh)

    def getLogger(self):
        if not self.logger:
            self.logger = logging.getLogger('Logger')
        return self.logger
    


