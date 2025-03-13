from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, RadioSet, RadioButton, Input, RichLog, TextArea, Checkbox, Label
from textual.widgets import TabbedContent, TabPane, Static, OptionList, Button
from textual.widgets.option_list import Option
from textual.widget import Widget
from textual.reactive import reactive
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
#from textual.events import Blur
import modules.serialModule as serialModule
import modules.meshtools as meshtools
import modules.logger as logger
import modules.constants as constants
import modules.labelFilter as lfilter
from signal import signal, SIGINT
import yaml, os, pathlib, time
from queue import Queue
from enum import Enum
from textual import work
from textual.containers import Container, ScrollableContainer
from rich.highlighter import ReprHighlighter
import asyncio, re


default_config = {constants.CFG_LOG2FILE: True,
                  constants.CFG_LOGS_BY_PORT:False,
                  constants.CFG_LOGS_BY_SESSION:False,
                  constants.CFG_AUTO_RECONNECT: True,
                  constants.CFG_BAUDRATE: 115200,
                  }
def idf(text):
    text = text.replace(' ','_')
    return text

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
    driveList = reactive([])
    ps = reactive([])
    portsRB = reactive([])
    config = reactive({}, always_update=True, init=False)
    isFullscreen = False
    logger = None
    sm = None
    mt = None
    logUI = None
    fileHandler = None
    lastLogName = None
    text = reactive('')
    mt_logs = None
    
    # Vars for labels filterings
    ruller = None
    labelsList = reactive({})
    filledLabels = []
    highlighter = ReprHighlighter()
    
    state = States.Starting
    
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
        Binding(key='ctrl+a', action="expand_log('#vlogs')", description="Fullscreen logs"),
        Binding(key='ctrl+r', action="clear_log('#rclogs')", description="Clear logs"),
        Binding(key='ctrl+l', action="save_labels()", description="Save labels"),
    ]
    
    def __init__(self, driver_class = None, css_path = None, watch_css = False, ansi_color = False, config = default_config):
        super().__init__(driver_class, css_path, watch_css, ansi_color)
        self.logger = logger.SLogger()
        self.sm = serialModule.SerialModule(logger=self.logger.getLogger(), queue=Queue())  
        self.mt = meshtools.MeshTools(config)
        self.config = config
    
    '''
    Actions
    '''
     
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
    
    # Save labelsList to file
    def action_save_labels(self) -> None:
        with open(constants.LABELS_FILE, 'w') as f:
            yaml.dump(self.labelsList, f)
            self.notify(f"Labes saved to {constants.LABELS_FILE}",timeout=2)

    def action_sendto(self):
        pass
    
    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
                with TabPane("Serial", id="main-tab"):
                    with Horizontal():
                        with Vertical(id="sm_leftColumn",classes="mui leftColumn"):
                            #self.createPortsRB()
                            pl = RadioSet( *self.portsRB, id='portList', name='Ports list')
                            yield pl
                            yield ScrollableContainer(*[],id="labelsContainer")

                        with Vertical(id="vlogs"):
                            self.logUI = RichLog(id='rclogs',highlight=True)
                            yield self.logUI
                            
                with TabPane("MeshTools", id="meshtools-tab"):
                        with Horizontal(id='mt_btnh', classes="mui"):
                            with Horizontal(id='mmh_uf2', classes="") as uf2_container:
                                uf2_container.border_title = 'UF2 boards tools'
                                
                                with Vertical(id="mt_leftColumn",classes="leftColumn"):
                                    with OptionList(*self.mt.getBoardsList(),id='platformList', name='Platforms') as l:
                                        l.border_title = 'Boards types'
                                    with OptionList(id='driveList', name='Drives') as l:
                                        l.border_title = 'Drives'
                                with Vertical(id='buttons', classes='buttonsList'):
                                    with Container(id='mmh_steps'):
                                        for s in meshtools.mmhSteps:
                                            yield Checkbox(id = f"mmh_{s.value}", label=f"{s.name}", classes="mmh_checkbox settings_element")
                                    yield Button("Make me happy!",id = 'mmh_btn', classes='buttons', variant='primary')
                        with Horizontal(id="mt_logsh"):
                            yield RichLog(id='mt_logs',highlight=True)
                            
                with TabPane("Settings", id="settings-tab"):
                    with Container(classes="settings_tab", id = "settings"):
                        for key in self.config.get('config',{}).keys():
                            value = self.config.get('config',{}).get(key)
                            if isinstance(value, bool):
                                yield Checkbox(id = key, label=constants.getVarName(key),value=value, classes="settings_checkbox settings_element")
                            elif isinstance(value, (int,str)):
                                with Horizontal(classes="settings_label_input"):
                                        yield Label(f"{constants.getVarName(key)}:", classes="settings_label settings_element")
                                        inp = Input(value=str(value), id = key, tooltip=key, type="integer", classes="settings_input settings_element")
                                        inp.oldValue = str(value)
                                        yield inp
                                    
                with TabPane("Info", id="info-tab"):
                    with Vertical(classes="info_tab"):
                        yield TextArea(text = self.config.get('info',{}).get('text',''), id="taAbout", disabled=True)
                        v = f"App version: {self.config.get('info',{}).get('version',self.version)}"
                        yield Static(content = v, id="version")
                    
        yield Footer()
    def on_mount(self):
        pass
    
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
        # Process static labels
        self.run_worker(self.labelFilterWrapper(''))
        cfg = self.config.get('config',{})
        self.mt_logs = self.query_one('#mt_logs', RichLog)
        self.mt.setLogCallback(self.mt_logs.write)
        '''
        if constants.CFG_SENDTO in cfg and cfg[constants.CFG_SENDTO]:
            self.bind(keys='ctrl+m' , action="sendto" , description='123')
        '''
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
    '''
    smState update callback. 
    TODO time.time added to always update smState, but need to ne changed to always_update property of reactive
    '''
    smState = reactive(())
    def serialPortStateUpdate(self, state: serialModule.States, prevState : serialModule.States, port, baud):
        self.smState = (state, prevState, port, baud, time.time())

    '''
    Check serial monitor state changes
    Do NOT use this method to add/remove UI elements or something similar
    Some states catches not in 100% cases (like Closing or stopped), so you can miss something
    '''
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
            elif state == serialModule.States.Closing and rb.value == True:
                with rb.prevent(rb.Changed):
                    rb.toggle()
        except Exception as e:
            pass
        finally:
            pass

            
    # Write callback for logging to UI RichLog and fill labels
    @work(exclusive=True)
    async def write(self,msg):
        #clean_text = await PortSelector.cleanText(msg)
        self.logUI.write(msg)
        self.run_worker(self.labelFilterWrapper(msg))
    
    # Remove non ANSII chars from text
    # Not used, moved to serialModule TODO need to remove or do something
    async def cleanText(msg):
        clean_text = re.sub(r'\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?', '', msg)
        clean_text = clean_text.replace('\x00', '')
        return clean_text

    async def labelFilterWrapper(self, string):
        self.filledLabels, self.labelsList  = await self.ruller.labelFilter(string, self.labelsList.copy())
    
    # Do jobs when config changed
    def watch_config(self):
        #set actual file handlers (logToFile, separatePortLogs)
        self.updateLogger()
        # Set autoReconnect
        self.sm.retry = self.config.get('config',default_config).get(constants.CFG_AUTO_RECONNECT,False)
        pass
    
    # Add/remove logger handlers when settings changed or other port selected
    def updateLogger(self, port = None):
        if not os.path.exists(constants.LOG_DIR):
            os.makedirs(constants.LOG_DIR)
        if not port: port = self.sm.port.name if self.sm.state == serialModule.States.Active else None
        cfg = self.config.get('config',default_config)
        fname =constants.LOG_FILENAME
        fprefix = port if port and (constants.CFG_LOGS_BY_PORT in cfg and cfg.get(constants.CFG_LOGS_BY_PORT, False)) else None
        if constants.CFG_LOGS_BY_SESSION in cfg and cfg.get(constants.CFG_LOGS_BY_SESSION, False):
            formatted_time = time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(time.time()))
            fprefix = f"{fprefix}.{formatted_time}" if fprefix else formatted_time
        path =pathlib.Path(constants.LOG_DIR, f"{fprefix}.{fname}" if fprefix else fname)
        #currentLogName = f"{fprefix}.{fname}" if fprefix else fname
        currentLogName = path.as_posix()
        if self.lastLogName != currentLogName:
            self.logger.removeFileHandlers()
            self.fileHandler = None
        if constants.CFG_LOG2FILE in cfg and cfg.get(constants.CFG_LOG2FILE, False):
                self.fileHandler = self.logger.addFileHandler(currentLogName, encoding='utf-8')
                self.lastLogName = currentLogName
        elif self.fileHandler:
            self.logger.removeFileHandlers()
            self.fileHandler = None
            self.lastLogName = None
        
    # Mount all Radiobuttons when RadioButtons list changed
    async def watch_portsRB(self):
        try:
            pl = self.query_one("#portList")
            if pl:
                with self.app.batch_update():
                    if len(pl.children)!=0:
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
        if pl and len(pl.children)==0:
            pass
            #await self.watch_ports()    
    
    # Build Radiobuttons when port list changes
    async def watch_ports(self):
        self.createPortsRB()    
    
    async def watch_driveList(self):
        dl = self.query_one("#driveList", OptionList)
        bl = self.query_one("#platformList", OptionList)
        bl.highlighted  = None
        if dl:
            with self.app.batch_update():
                l = len(dl.options)
                if l!=0:
                    for i in range(l-1,-1,-1):
                        dl.remove_option_at_index(i)
                droptions = [Option(d.device) for d in self.driveList]
                dl.add_options(droptions)
            # CHeck if drive has CURRENT.UF2 file
            for d in self.driveList:
                forceUpdateBootloader = False
                dfuDrive, info = self.mt.checkDrive(d.mountpoint)
                if dfuDrive:
                    self.mt_logs.write(f"Drive: {d.device}, dfuDrive: {dfuDrive}:")
                    try:
                        dl.highlighted = self.driveList.index(d)
                        bl.highlighted = self.mt.getBoardsList().index(info.get('board_id',0))
                    except Exception as e:
                        pass
                    ubCB = self.query_one(f"#mmh_{meshtools.mmhSteps.UPDATE_BOOTLOADER.value}",Checkbox)
                    forceUpdateBootloader, bootLoaderAvailable = self.mt.forceBootloaderUpdate(info.get('board_id',''), 
                                                                          self.mt.checkVersion(info.get('bootloader','0'))
                                                                          )

                    self.mt_logs.write( f"\tboard: {info.get('board_id','')}, new bootloader: {not forceUpdateBootloader}, bootloader: {info.get('bootloader', '')}, softdevice: {info.get('softdevice','')}")
                    # Set update bootloder checkbox if dfu has old one
                    ubCB.value = forceUpdateBootloader
                    ubCB.disabled = not bootLoaderAvailable
                    
    # Check if labels changed. If true -sort them. For each label create Static widget and add it to labels container
    async def watch_labelsList(self):
        if self.labelsList:
            with self.app.batch_update():
                self.query_one("#labelsContainer").remove_children("*")
                for label in self.labelsList:
                    if label in self.filledLabels:
                        style = "green"
                    else:
                        style = "white"
                    lt = await self.hltext(f"{label}: {self.labelsList.get(label)}",("([^:]+):",style))
                    lbl = Static(content=lt, classes='labels')
                    await self.query_one("#labelsContainer").mount(lbl)
    
    # Update port list every PORTS_RENEWAL_DELAY sec
    def updatePortsTh(self):
        while self.state == States.Active:
            # Update ports
            avports, currentPort = self.sm.get_available_ports()

            if self.ports != avports or currentPort:
                self.setPorts(avports)
                
            # Update drives
            drives = self.mt.listDrives()
            self.driveList = drives
            
            
            time.sleep(constants.PORTS_RENEWAL_DELAY)
    
    '''
    Create RadioButtons for available ports
    Create  additional buttons (Stop and reconnecting button)
    Reconnecting button is UI element represent  COM port not available in system,
    but triyng to open by serial (in case port was opened but device disconnected from PC)
    '''
    def createPortsRB(self):
        arr = []
        rsbState = False
        try:
            #rsbState = self.query_one("#stopRB").value
            #Check if last pressed button was stopRB
            rsbState = True if self.query_one("#portList").pressed_button.id =="stopRB" else False
        except Exception as e: pass
        if self.ports:
            arr =[RadioButton(t,tooltip=self.ports[i].description, id=self.ports[i].name) for i, t in enumerate(self.ps)]
        if self.sm.port and self.sm.port not in self.ports and self.sm.state == serialModule.States.Reconnecting:
            recB = RadioButton(self.sm.port.name,tooltip=self.sm.port.description, id =self.sm.port.name)
            recB.add_class("fakeRB")
            arr.append(recB)
        stop = RadioButton("Stop",tooltip="Stop logging", id ="stopRB", value=rsbState)
        arr.append(stop)
        for b in arr:
            b.can_focus = False
        self.portsRB = arr
    
    @work(exclusive=True) 
    async def on_radio_button_changed(self, event: RadioButton.Changed) -> None:
        pass
     
    mltask = None   
    @work(exclusive=True)
    async def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self.sm.stopLoop = True
        # Wait while active serial connection is stopped
        # We can check  task state or self.sm.state (currently `task`` to avoid several active tasks running)
        while self.mltask and self.mltask._state != 'FINISHED':
            await asyncio.sleep(0.1)
        
        # Remove fakeRB (`reconnecting` button) if other radiobutton clicked
        for rb in event.control.children:
            if rb.has_class('fakeRB') and rb!= event.pressed:
                await rb.remove()
        # Update logger and start serial for selected port
        if event.pressed.id != 'stopRB':
            try:
                indx= self.ps.index(event.pressed.label.plain)
                port = self.ports[indx]
                self.updateLogger(port = port.device)
                # Preventing multiple tasks with serial 
                if not self.mltask or self.mltask._state == 'FINISHED':
                    self.mltask = asyncio.create_task(asyncio.to_thread(self.runSerial,port))
            except Exception as e:
                pass
        else:
            pass
    
    def runSerial(self, port):
        self.sm.mainLoop(port, int(self.config.get('config').get(constants.CFG_BAUDRATE,115200)), bool(self.config.get('config').get(constants.CFG_AUTO_RECONNECT,False)), waitNewPort=False)


            
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.parent.id == 'settings':
            self.config['config'][event.checkbox.id] = event.checkbox.value
            # Hack for reactive dict https://github.com/Textualize/textual/issues/1098
            self.config = self.config
            #TODO need to use async io library (?) or move to watch_config
            writeConfigFile(self.config, "config")
            self.notify(message="Config saved",timeout=1)
        if event.checkbox.parent.id == 'mmh_steps':
            pass

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
    
    @work(exclusive=True, thread=True)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case 'bootl':
                if self.query_one('#driveList', OptionList).highlighted != None and self.query_one('#platformList', OptionList).highlighted != None:
                    self.mt.copyFile(type = 'bootloader', 
                                platform = self.query_one('#platformList', OptionList).highlighted,
                                targetFolder= self.driveList[self.query_one('#driveList', OptionList).highlighted].mountpoint
                                )

            case 'mmh_btn':
                if self.query_one('#platformList', OptionList).highlighted != None:
                    platform = self.mt.getBoardsList()[self.query_one('#platformList', OptionList).highlighted]
                else: return
                driveN = self.query_one('#driveList', OptionList).highlighted
                if platform != None and driveN != None:
                    targetFolder = self.driveList[driveN].mountpoint
                    steps = [ s.name for s in meshtools.mmhSteps if self.query_one(f"#mmh_{s.value}").value == True ]
                    try:
                        stepsExecuted = await self.mt.execMmhSteps(platform=platform, targetFolder=targetFolder, steps= steps ,sm = self.sm)
                        await self.mmhDisableExecuted(stepsExecuted = stepsExecuted)
                        if meshtools.mmhSteps.OPEN_CONSOLE.name in stepsExecuted:
                            self.logUI.focus()
                        #asyncio.create_task(asyncio.to_thread(self.mt.execMmhSteps,platform=platform, targetFolder=targetFolder, steps= steps, sm = self.sm))
                    except Exception as e:
                        e.__traceback__
                        self.write(str(e))
                        raise e
                        pass
    
    async def mmhDisableExecuted(self, stepsExecuted : list = []):
        if stepsExecuted:
            for s in stepsExecuted:
                try:
                    self.query_one(f"#mmh_{meshtools.mmhSteps[s].value}",Checkbox).value = False
                except Exception as e: pass
        
    
    def setPorts(self, ports: list):
        self.ps = [f"{port.name}" for port in ports]
        self.ports = ports
    
    def getPortByName(self, name):
        for p in self.ports:
            if p.name == name:
                return p
        return None
        

def readConfig():
    
    if not os.path.exists(constants.CONFIG_DIR):
        os.makedirs(constants.CONFIG_DIR)
    #Read all yaml files in config folder and return them as common dictionary

    config_files = [f for f in os.listdir(constants.CONFIG_DIR) if f.endswith('.yaml')]
    config_dict = {}
    for file in config_files:
        with open(os.path.join(constants.CONFIG_DIR, file), 'r') as stream:
            
            config_dict[pathlib.Path(file).stem] = yaml.safe_load(stream)
    if config_dict.get('config',{}) != None:
        default_config.update(config_dict.get('config',{}))
    config_dict['config'] = default_config
    
    return config_dict


def writeConfigFile(config_dict, filename):
    with open(os.path.join(constants.CONFIG_DIR, f"{filename}.yaml"), 'w') as f:
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
    