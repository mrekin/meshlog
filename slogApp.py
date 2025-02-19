from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, RadioSet, RadioButton, Input, RichLog, TextArea, Checkbox, Label, TabbedContent, TabPane, Static
from textual.widget import Widget
from textual.reactive import reactive
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.events import Blur
import modules.serialModule as serialModule
import modules.logger as logger
import modules.constants as constants
import modules.labelFilter as lfilter
from signal import signal, SIGINT
import yaml, os, pathlib, time
from queue import Queue
from enum import Enum
from textual import work
from textual.containers import Container
from rich.highlighter import ReprHighlighter
import asyncio, re

config_dir = "config"
default_config = {"logToFile": True,
                  "separatePortLogs":False,
                  "autoReconnect": True,
                  "baudrate": 115200}

class States(Enum):
    Starting = 0
    Active = 1
    Suspend = 2
    Closing = 3

class Lbl(Widget):
    text = reactive('empty label', layout=True)
    
    def __init__(self, *children, name = None, id = None, classes = None, disabled = False, text = None):
        super().__init__(*children, name=name, id=id, classes=classes, disabled=disabled)
        if text: self.text = text
    def render(self) -> str:
        return f"{self.text}"


class PortSelector(App[None]):
    version = constants.VERSION
    TITLE = constants.TITLE
    SUB_TITLE = constants.SUB_TITLE
    CSS_PATH = constants.CSS_PATH
    ports =reactive([])
    ps = reactive([])
    portsRB = reactive([])
    config = reactive({}, always_update=True)
    isFullscreen = False
    logger = None
    sm = None
    logUI = None
    fileHandler = None
    lastLogName = None
    text = reactive('')
    
    # Vars for labels filtering
    ruller = None
    labelsList = reactive({})
    filledLabels = []
    highlighter = ReprHighlighter()
    
    state = States.Starting
    
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
        Binding(key='ctrl+a', action="expand_log('#vlogs')", description="Fullscreen logs"),
        Binding(key='ctrl+r', action="clear_log('#rclogs')", description="Clear logs"),
    ]
    
    def __init__(self, driver_class = None, css_path = None, watch_css = False, ansi_color = False, config = default_config):
        super().__init__(driver_class, css_path, watch_css, ansi_color)
        self.logger = logger.SLogger()
        self.sm = serialModule.SerialModule(logger=self.logger.getLogger(), queue=Queue())  
        self.config = config
     
    def action_quit(self):
        self.sm.stopLoop = True
        self.logger = None
        self.state = States.Closing
        return super().action_quit()
    
    def action_expand_log(self, id = None) -> None:
        if not self.isFullscreen:
            self.query_one(id).styles.widthOld = self.query_one(id).styles.width
            self.query_one(id).styles.width = '99%'
            for w in self.query(".mui"):
                w.styles.visibility = 'hidden'
            self.isFullscreen = True
        else:
            self.query_one(id).styles.width = self.query_one(id).styles.widthOld
            self.isFullscreen = False
            for w in self.query(".mui"):
                w.styles.visibility = 'visible'

    def action_clear_log(self, id = None) -> None:
        self.logUI.clear()
  
    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
                with TabPane("Main", id="main-tab"):
                    with Horizontal():
                        with Vertical(id="leftColumn",classes="mui"):
                            #self.createPortsRB()
                            pl = RadioSet( *self.portsRB, id='portList', name='Ports list')
                            yield pl
                            yield Container(*[],id="labelsContainer")

                        with Vertical(id="vlogs"):
                            self.logUI = RichLog(id='rclogs',highlight=True)
                            yield self.logUI
                            
                with TabPane("Settings", id="settings-tab"):
                    with Container(classes="settings_tab", id = "settings"):
                        for key in self.config.get('config',{}).keys():
                            value = self.config.get('config',{}).get(key)
                            if isinstance(value, bool):
                                yield Checkbox(id = key, label=key,value=value, classes="settings_checkbox settings_element")
                            elif isinstance(value, (int,str)):
                                with Horizontal(classes="settings_label_input"):
                                        yield Label(f"{key}:", classes="settings_label settings_element")
                                        inp = Input(value=str(value), id = key, tooltip=key, type="integer", classes="settings_input settings_element")
                                        inp.oldValue = str(value)
                                        yield inp
                                    
                with TabPane("Info", id="info-tab"):
                    with Vertical(classes="info_tab"):
                        yield TextArea(text = self.config.get('info',{}).get('text',''), id="taAbout", disabled=True)
                        v = f"App version: {self.config.get('info',{}).get('version',self.version)}"
                        yield Static(content = v, id="version")
                    
        yield Footer()
    
    async def on_ready(self) -> None:
        self.logger.addCustomLogger(self.write)
        self.state = States.Active
        asyncio.create_task(asyncio.to_thread(self.updatePortsTh))
        self.ruller = lfilter.LabelFiller(self.config.get('labels',[]))
        htext = self.highlighter(constants.LOG_INITIAL_TEXT)
        htext.style = 'gray 40%'
        htext.highlight_words(await self.ruller.getKeywords(htext.plain,"`([^`]+)`"), style='green italic')
        self.logUI.write(htext)
        self.sm.stateInfoSubscribe(self.serialPortStateUpdate)
        pass
    
    # Rules is a set of tuples (regexp, style) for highlighting
    async def hltext(self, text: str| ReprHighlighter, *rules):
        t = self.highlighter(text)
        for r in rules:
            if isinstance(r ,tuple):
                try:
                    t.highlight_words(await self.ruller.getKeywords(t.plain, r[0]), style=r[1])
                except Exception as e:
                    pass
        return t
    
    smState = reactive(())
    def serialPortStateUpdate(self, state: serialModule.States, prevState : serialModule.States, port, baud):
        self.smState = (state, prevState, port, baud, time.time())

    async def watch_smState(self):
        if not self.smState:
            return
        state = self.smState[0]
        prevState = self.smState[1]
        port = self.smState[2]
        baud = self.smState[3]
        rb = None
        rsb = None
        try:
            try:
                rsb = self.query_one(f"#stopRB",RadioButton)
                rb = self.query_one(f"#{port.name}",RadioButton)
            except Exception as e:
                pass
            if state == serialModule.States.Reconnecting:
                if not rb: rb = rsb
                with rb.prevent(rb.Changed):
                    rb.toggle()
            elif state == serialModule.States.Active and rb.value == False and rsb.value == False:
                with rb.prevent(rb.Changed):
                    rb.toggle()   
        except Exception as e:
            pass
        finally:
            try:
                #rb.refresh()
                pass
            except:
                pass
    
    @work(exclusive=True)
    async def write(self,msg):
        #clean_text = await PortSelector.cleanText(msg)
        self.logUI.write(msg)
        self.run_worker(self.labelFilterWrapper(msg))
    
    async def cleanText(msg):
        clean_text = re.sub(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?', '', msg)
        clean_text = clean_text.replace('\x00', '')
        return clean_text

    async def labelFilterWrapper(self, string):
        self.filledLabels, self.labelsList  = await self.ruller.labelFilter(string, self.labelsList.copy())
    
    def watch_config(self):
        #set actual file handlers (logToFile, separatePortLogs)
        self.updateLogger()
        # Set autoReconnect
        self.sm.retry = self.config.get('config',default_config).get('autoReconnect',False)
        pass
    
    def updateLogger(self, port = None):
        if not port: port = self.sm.port.name if self.sm.state == serialModule.States.Active else None
        cfg = self.config.get('config',default_config)
        fname =constants.LOG_FILENAME
        fprefix = port if port and ('separatePortLogs' in cfg and cfg.get('separatePortLogs', False)) else None
        currentLogName = f"{fprefix}.{fname}" if fprefix else fname
        if self.lastLogName != currentLogName:
            self.logger.removeFileHandlers()
            self.fileHandler = None
        if 'logToFile' in cfg and cfg.get('logToFile', False):
                self.fileHandler = self.logger.addFileHandler(currentLogName, encoding='utf-8')
                self.lastLogName = currentLogName
        elif self.fileHandler:
            self.logger.removeFileHandlers()
            self.fileHandler = None
            self.lastLogName = None
        
        
    
    async def watch_portsRB(self):
        try:
            pl = self.query_one("#portList")
            if pl:
                with self.app.batch_update():
                    await pl.remove_children("*")
                    # Make active port selected
                    if self.sm.state == serialModule.States.Active and self.sm.port:
                        for b in self.portsRB:
                            if b.id == self.sm.port.name and b.value == False:
                                with b.prevent(b.Changed):
                                    b.toggle()   
                    await pl.mount_all(self.portsRB)
        except:
            pass
    
    async def watch_ports(self):
        self.createPortsRB()    
    
    # Check if labels changed. If true -sort them. For each label create Static widget and add it to labels container
    async def watch_labelsList(self):
        if self.labelsList:
            self.query_one("#labelsContainer").remove_children("*")
            for label in self.labelsList:
                if label in self.filledLabels:
                    style = "green"
                else:
                    style = "white"
                lt = await self.hltext(f"{label}: {self.labelsList.get(label)}",("(\w+):",style))
                lbl = Static(content=lt, classes='labels')
                await self.query_one("#labelsContainer").mount(lbl)

    def updatePortsTh(self):
        while self.state == States.Active:
            avports, currentPort = self.sm.get_available_ports()

            if self.ports != avports or currentPort:
                self.setPorts(avports)
            time.sleep(constants.PORTS_RENEWAL_DELAY)
    
    def createPortsRB(self):
        arr = []
        rsbState = False
        try:
            rsbState = self.query_one("#stopRB").value
        except Exception as e: pass
        if self.ports:
            arr =[RadioButton(t,tooltip=self.ports[i].description, id=self.ports[i].name) for i, t in enumerate(self.ps)]
        if self.sm.port and self.sm.port not in [p.device for p in self.ports] and self.sm.state == serialModule.States.Reconnecting:
            recB = RadioButton(self.sm.port.name,tooltip=self.sm.port.description, id =self.sm.port.name)
            arr.append(recB)
        stop = RadioButton("Stop",tooltip="Stop logging", id ="stopRB", value=rsbState)
        arr.append(stop)
        for b in arr:
            b.can_focus = False
        self.portsRB = arr
    
    @work(exclusive=True) 
    async def on_radio_button_changed(self, event: RadioButton.Changed) -> None:
        pass
        
    @work(exclusive=True)
    async def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self.sm.stopLoop = True
        if event.pressed.id != 'stopRB':
            try:
                indx= self.ps.index(event.pressed.label.plain)
                port = self.ports[indx]
                self.updateLogger(port = port.device)
                asyncio.create_task(asyncio.to_thread(self.runSerial,port))
            except Exception as e:
                pass
    
    def runSerial(self, port):
        self.sm.mainLoop(port, int(self.config.get('config').get('baudrate',115200)), bool(self.config.get('config').get('autoReconnect',False)))
            
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        self.config['config'][event.checkbox.id] = event.checkbox.value
        # Hack for reactive dict https://github.com/Textualize/textual/issues/1098
        self.config = self.config
        #TODO need to use async io library
        writeConfigFile(self.config, "config")
        self.notify(message="Config saved",timeout=1)

    @on(Input.Submitted,selector='.settings_element')
    @on(Input.Blurred,selector='.settings_element')
    async def on_submit(self, event: Input.Submitted) -> None:
        if event.input._initial_value:
            return
        if event.input.oldValue != event.input.value:
            event.input.oldValue = event.input.value
            self.config['config'][event.input.id] = event.input.value
            #TODO need to use async io library
            writeConfigFile(self.config, "config")
            self.notify(message=f"Config saved: {event.input.id}",timeout=2)        

    
    def setPorts(self, ports: list):
        self.ps = [f"{port.name}" for port in ports]
        self.ports = ports
    
    def getPortByName(self, name):
        for p in self.ports:
            if p.name == name:
                return p
        return None
        

def readConfig():
    
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    #Read all yaml files in config folder and return them as common dictionary

    config_files = [f for f in os.listdir(config_dir) if f.endswith('.yaml')]
    config_dict = {}
    for file in config_files:
        with open(os.path.join(config_dir, file), 'r') as stream:
            
            config_dict[pathlib.Path(file).stem] = yaml.safe_load(stream)
    default_config.update(config_dict.get('config',{}))
    config_dict['config'] = default_config
    
    return config_dict


def writeConfigFile(config_dict, filename):
    with open(os.path.join(config_dir, f"{filename}.yaml"), 'w') as f:
        yaml.dump(config_dict.get(filename), f)
    

def init():
    return   

def handler(signal_received, frame):
    # Handle any cleanup here
    print('SIGINT or CTRL-C detected. Exiting logging gracefully')
    #q.put(True)
    
if __name__ == "__main__":
    signal(SIGINT, handler)
    print('Running. Press CTRL-C to exit.')
    loop = True
    app = PortSelector(config=readConfig())
    #app.config = readConfig()
    app.setPorts(serialModule.get_available_ports())
    app.run()
    