import asyncio
import os
import pathlib
import re
import time
from enum import Enum
from queue import Queue
from signal import SIGINT, signal

import requests
import yaml
from rich.highlighter import ReprHighlighter
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import (
    Container,
    Horizontal,
    ScrollableContainer,
    Vertical,
    VerticalScroll,
)
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    RadioButton,
    RadioSet,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.widgets.option_list import Option

import modules.constants as constants
import modules.labelFilter as lfilter
import modules.logger as logger
import modules.meshtools as meshtools

# from textual.events import Blur
import modules.serialModule as serialModule

default_config = {
    constants.CFG_LOG2FILE: True,
    constants.CFG_LOGS_BY_PORT: False,
    constants.CFG_LOGS_BY_SESSION: False,
    constants.CFG_AUTO_RECONNECT: True,
    constants.CFG_BAUDRATE: 115200,
    constants.CFG_AUTO_SAVE_NODE_CFG: True,
    constants.CFG_LOG_BOARD_CFG: False,
}


def idf(text):
    text = text.replace(" ", "_")
    return text


class States(Enum):
    Starting = 0
    Active = 1
    Suspend = 2
    Closing = 3


class Lbl(Widget):
    text = reactive("empty label", layout=True)

    def __init__(
        self, *children, name=None, id=None, classes=None, disabled=False, text=None
    ):
        super().__init__(
            *children, name=name, id=id, classes=classes, disabled=disabled
        )
        if text:
            self.text = text

    def render(self) -> str:
        return f"{self.text}"


class RichLogEx(RichLog):

    smartAutoScroll = False

    @on(events.MouseScrollDown)
    @on(events.MouseScrollUp)
    @on(events.Key)
    def checkSmartAutoScroll(self, event: events.InputEvent) -> None:
        if self.smartAutoScroll:
            if isinstance(event, events.MouseScrollDown) or (
                isinstance(event, events.Key)
                and event.key in ("down", "pagedown", "end")
            ):
                if self.max_scroll_y == self.scroll_target_y and not self.auto_scroll:
                    self.auto_scroll = True
            if isinstance(event, events.MouseScrollUp) or (
                isinstance(event, events.Key) and event.key in ("up", "pageup", "home")
            ):
                if self.max_scroll_y != self.scroll_target_y and self.auto_scroll:
                    self.auto_scroll = False

    def setSmartAutoScroll(self, smartAutoScroll=False):
        self.smartAutoScroll = smartAutoScroll


class PortSelector(App[None]):
    version = constants.VERSION
    TITLE = constants.TITLE
    SUB_TITLE = constants.SUB_TITLE
    CSS_PATH = constants.CSS_PATH
    ports = reactive([])
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
    text = reactive("")
    mt_logs = None

    # Vars for labels filterings
    ruller = None
    labelsList = reactive({})
    filledLabels = []
    highlighter = ReprHighlighter()

    state = States.Starting

    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
        Binding(
            key="ctrl+a", action="expand_log('#vlogs')", description="Fullscreen logs"
        ),
        Binding(key="ctrl+r", action="clear_log('#rclogs')", description="Clear logs"),
        Binding(key="ctrl+l", action="save_labels()", description="Save labels"),
    ]

    def __init__(
        self,
        driver_class=None,
        css_path=None,
        watch_css=False,
        ansi_color=False,
        config=default_config,
    ):
        super().__init__(driver_class, css_path, watch_css, ansi_color)
        self.logger = logger.SLogger()
        self.sm = serialModule.SerialModule(
            logger=self.logger.getLogger(), queue=Queue()
        )
        self.mt = meshtools.MeshTools(config)
        self.config = config

    """
    Actions
    """

    def action_quit(self):
        self.sm.stopLoop = True
        self.logger = None
        self.state = States.Closing
        return super().action_quit()

    def action_expand_log(self, id=None) -> None:
        if not self.isFullscreen:
            for w in self.query(".fullScreenOn"):
                w.styles.widthOld = w.styles.width
                w.styles.width = "99%"
            for w in self.query(".fullScreenOff"):
                w.styles.visibility = "hidden"

            self.isFullscreen = True
        else:
            for w in self.query(".fullScreenOn"):
                w.styles.width = w.styles.widthOld
            self.isFullscreen = False
            for w in self.query(".fullScreenOff"):
                w.styles.visibility = "visible"
            for w in self.query(".mui"):
                w.styles.visibility = "visible"

    def action_clear_log(self, id=None) -> None:
        self.logUI.clear()

    # Save labelsList to file
    def action_save_labels(self) -> None:
        with open(constants.LABELS_FILE, "w") as f:
            yaml.dump(self.labelsList, f)
            self.notify(f"Labes saved to {constants.LABELS_FILE}", timeout=2)

    def action_sendto(self):
        pass

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("Tools", id="main-tab"):
                with Horizontal():
                    with Vertical(
                        id="sm_leftColumn", classes="mui fullScreenOff leftColumn"
                    ):
                        with RadioSet(
                            *self.portsRB,
                            id="portList",
                            name="Ports list",
                            classes="comports",
                        ) as pl:
                            pl.border_title = "COM ports"
                        with OptionList("111", id="driveList", name="Drives") as ol:
                            ol.border_title = "Drives"
                        with OptionList(
                            *self.mt.getBoardsList(),
                            id="platformList",
                            name="Platforms",
                        ) as ol:
                            ol.border_title = "Boards types"

                    with Vertical(
                        id="sm_toolsColumn", classes="fullScreenOn leftColumn"
                    ):
                        with TabbedContent():
                            with TabPane("Serial", id="serial-tab", classes="toolTab"):
                                with Horizontal() as h:
                                    h.border_title = "hv"
                                    with Vertical(
                                        id="sm_labelsColumn", classes="mui1 leftColumn1"
                                    ) as v:
                                        v.border_title = "vv"
                                        yield ScrollableContainer(
                                            *[],
                                            id="labelsContainer",
                                            classes="fullScreenOff",
                                        )
                                    with Vertical(id="vlogs", classes="fullScreenOn"):
                                        with RichLogEx(
                                            id="rclogs", highlight=True
                                        ) as rl:
                                            rl.setSmartAutoScroll(True)
                                            self.logUI = rl

                            with TabPane(
                                "MeshTools", id="meshtools-tab", classes="toolTab"
                            ):
                                # with Horizontal(id='mt_btnh', classes="mui"):
                                with Horizontal(
                                    id="mmh_uf2", classes="mui"
                                ) as uf2_container:
                                    uf2_container.border_title = "UF2 boards tools"
                                    with VerticalScroll(
                                        id="dfuButtons", classes="buttonsList mui w1"
                                    ) as dfuO:
                                        dfuO.border_title = "DFU operations"
                                        with ScrollableContainer(
                                            id="mmh_steps", classes="mui"
                                        ):
                                            for s in meshtools.mmhSteps:
                                                with Horizontal(
                                                    id=f"mmhor_{s.value}",
                                                    classes="mmhorisontal",
                                                ):
                                                    yield Checkbox(
                                                        id=f"mmh_{s.value}",
                                                        label=f"{s.name}",
                                                        classes="mmh_checkbox settings_element",
                                                    )
                                        yield Button(
                                            "Make me happy!",
                                            id="mmh_btn",
                                            classes="dfuButtons1 mesh_button",
                                            variant="primary",
                                        )
                                    with Vertical(
                                        id="meshInputs", classes="buttonsList w1"
                                    ) as meshI:
                                        meshI.border_title = "Node connection settings"
                                    with Vertical(
                                        id="meshButtons", classes="buttonsList w05"
                                    ) as meshO:
                                        meshO.border_title = "Mesh operations"
                                        with ScrollableContainer(id="mesh_buttons"):
                                            for s in meshtools.meshOptions:
                                                yield Button(
                                                    id=f"meshOption_{s.value}",
                                                    label=f"{s.name}".replace("_", " "),
                                                    classes="mesh_button",
                                                )
                                with Horizontal(id="mt_logsh"):
                                    with RichLogEx(id="mt_logs", highlight=True) as rl:
                                        rl.setSmartAutoScroll(True)

            with TabPane("Settings", id="settings-tab"):
                with Container(classes="settings_tab", id="settings"):
                    for key in self.config.get("config", {}).keys():
                        value = self.config.get("config", {}).get(key)
                        if isinstance(value, bool):
                            yield Checkbox(
                                id=key,
                                label=constants.getVarName(key),
                                value=value,
                                classes="settings_checkbox settings_element",
                            )
                        elif isinstance(value, (int, str)):
                            with Horizontal(classes="settings_label_input"):
                                yield Label(
                                    f"{constants.getVarName(key)}:",
                                    classes="settings_label settings_element",
                                )
                                inp = Input(
                                    value=str(value),
                                    id=key,
                                    tooltip=key,
                                    type="integer",
                                    classes="settings_input settings_element",
                                )
                                inp.oldValue = str(value)
                                yield inp

            with TabPane("Info", id="info-tab"):
                with Vertical(classes="info_tab"):
                    yield TextArea(
                        text=self.config.get("info", {}).get("text", ""),
                        id="taAbout",
                        disabled=True,
                    )
                    v = f"App version: {self.config.get('info',{}).get('version',self.version)}"
                    yield Static(content=v, id="version")

        yield Footer()

    async def on_mount(self):
        pass

    async def on_ready(self) -> None:
        self.logger.addCustomLogger(self.write)
        self.state = States.Active
        asyncio.create_task(asyncio.to_thread(self.updatePortsTh))
        self.ruller = lfilter.LabelFiller(self.config.get("labels", []))

        htext = self.highlighter(constants.LOG_INITIAL_TEXT)
        htext.style = "gray 40%"
        htext.highlight_words(
            await self.ruller.getKeywords(htext.plain, "`([^`]+)`"),
            style="green italic",
        )
        self.logUI.write(htext)

        self.sm.stateInfoSubscribe(self.serialPortStateUpdate)
        # Process static labels
        self.run_worker(self.labelFilterWrapper(""))
        # self.config.get("config", {})
        self.mt_logs = self.query_one("#mt_logs", RichLogEx)

        self.mt.setLogCallback(self.mt_logs.write)

        htext = self.highlighter(constants.MT_INITIAL_TEXT)
        htext.style = "gray 40%"
        htext.highlight_words(
            await self.ruller.getKeywords(htext.plain, "`([^`]+)`"),
            style="green italic",
        )
        self.mt.log.write(htext)

        """
        if constants.CFG_SENDTO in cfg and cfg[constants.CFG_SENDTO]:
            self.bind(keys='ctrl+m' , action="sendto" , description='123')
        """

    @on(TabbedContent.TabActivated)
    async def on_tab_activated(self, msg: TabbedContent.TabActivated) -> None:
        """Tab activated event"""
        msg.stop()
        if "toolTab" in msg.pane.classes:
            p = self.sm.port
            if p:
                await self.sm.stopLoopM()
                self.notify(f"Closing serial at: {p.device}")

    # Rules is a set of tuples (regexp, style) for highlighting
    async def hltext(self, text: str | ReprHighlighter, *rules):
        t = self.highlighter(text)
        for r in rules:
            if isinstance(r, tuple):
                try:
                    t.highlight_words(
                        await self.ruller.getKeywords(t.plain, r[0]), style=r[1]
                    )
                except Exception:
                    pass
        return t

    """
    smState update callback. 
    TODO time.time added to always update smState, but need to ne changed to always_update property of reactive
    """
    smState = reactive(())

    def serialPortStateUpdate(
        self, state: serialModule.States, prevState: serialModule.States, port, baud
    ):
        self.smState = (state, prevState, port, baud, time.time())

    """
    Check serial monitor state changes
    Do NOT use this method to add/remove UI elements or something similar
    Some states catches not in 100% cases (like Closing or stopped), so you can miss something
    """

    async def watch_smState(self):
        if not self.smState:
            return
        state = self.smState[0]
        # prevState = self.smState[1]
        port = self.smState[2]
        # baud = self.smState[3]
        rb = None
        rsb = None
        try:
            try:
                rsb = self.query_one("#stopRB", RadioButton)
                if port:
                    rb = self.query_one(f"#{port.name}", RadioButton)
            except Exception:
                pass
            if state == serialModule.States.Reconnecting:
                if not rb:
                    rb = rsb
                with rb.prevent(rb.Changed):
                    rb.toggle()
            elif state == serialModule.States.Active and not rb.value and not rsb.value:
                with rb.prevent(rb.Changed):
                    rb.toggle()
            elif not rb:
                rsb.toggle()
            elif (
                state
                not in (serialModule.States.Active, serialModule.States.Reconnecting)
                and rb.value
            ):
                with rb.prevent(rb.Changed):
                    rb.toggle()

        except Exception:
            pass
        finally:
            pass

    # Write callback for logging to UI RichLog and fill labels
    @work(exclusive=True)
    async def write(self, msg):
        # clean_text = await PortSelector.cleanText(msg)
        self.logUI.write(msg)
        self.run_worker(self.labelFilterWrapper(msg))

    # Remove non ANSII chars from text
    # Not used, moved to serialModule TODO need to remove or do something
    async def cleanText(msg):
        clean_text = re.sub(
            r"\x1b\[([0-9,A-Z]{1,2}(;[0-9]{1,2})?(;[0-9]{3})?)?[m|K]?", "", msg
        )
        clean_text = clean_text.replace("\x00", "")
        return clean_text

    async def labelFilterWrapper(self, string):
        self.filledLabels, self.labelsList = await self.ruller.labelFilter(
            string, self.labelsList.copy()
        )

    # Do jobs when config changed
    def watch_config(self):
        # set actual file handlers (logToFile, separatePortLogs)
        self.updateLogger()
        # Set autoReconnect
        self.sm.retry = self.config.get("config", default_config).get(
            constants.CFG_AUTO_RECONNECT, False
        )
        pass

    # Add/remove logger handlers when settings changed or other port selected
    def updateLogger(self, port=None):
        if not os.path.exists(constants.LOG_DIR):
            os.makedirs(constants.LOG_DIR)
        if not port:
            port = (
                self.sm.port.name
                if self.sm.state == serialModule.States.Active
                else None
            )
        cfg = self.config.get("config", default_config)
        fname = constants.LOG_FILENAME
        fprefix = (
            port
            if port
            and (
                constants.CFG_LOGS_BY_PORT in cfg
                and cfg.get(constants.CFG_LOGS_BY_PORT, False)
            )
            else None
        )
        if constants.CFG_LOGS_BY_SESSION in cfg and cfg.get(
            constants.CFG_LOGS_BY_SESSION, False
        ):
            formatted_time = time.strftime(
                "%Y-%m-%d_%H-%M-%S", time.localtime(time.time())
            )
            fprefix = f"{fprefix}.{formatted_time}" if fprefix else formatted_time
        path = pathlib.Path(
            constants.LOG_DIR, f"{fprefix}.{fname}" if fprefix else fname
        )
        # currentLogName = f"{fprefix}.{fname}" if fprefix else fname
        currentLogName = path.as_posix()
        if self.lastLogName == currentLogName:
            return
        self.logger.removeFileHandlers()
        self.fileHandler = None
        self.lastLogName = None
        if constants.CFG_LOG2FILE in cfg and cfg.get(constants.CFG_LOG2FILE, False):
            self.fileHandler = self.logger.addFileHandler(
                currentLogName, encoding="utf-8"
            )
            self.lastLogName = currentLogName

    # Mount all Radiobuttons when RadioButtons list changed
    async def watch_portsRB(self):
        try:
            pls = self.query(".comports").nodes
            for pl in pls:
                with self.app.batch_update():
                    if len(pl.children) != 0:
                        await pl.remove_children("*")
                    # Make active port selected
                    if self.sm.state == serialModule.States.Active and self.sm.port:
                        for b in self.portsRB:
                            if b.id == self.sm.port.name and not b.value:
                                with b.prevent(b.Changed):
                                    b.toggle()
                    await pl.mount_all(self.portsRB)
        except:
            pass

    # Build Radiobuttons when port list changes
    async def watch_ports(self):
        self.createPortsRB()
        self.checkPortAndSave()

    async def watch_driveList(self):
        dl = self.query_one("#driveList", OptionList)
        bl = self.query_one("#platformList", OptionList)
        bl.highlighted = None
        if dl:
            with self.app.batch_update():
                ol = len(dl.options)
                if ol != 0:
                    for i in range(ol - 1, -1, -1):
                        dl.remove_option_at_index(i)
                droptions = [Option(d.device) for d in self.driveList]
                dl.add_options(droptions)
                # Hot fix while Textual bug not fixed in release https://github.com/Textualize/textual/pull/5795
                # TODO test and remove this on next Textual version bump.
                dl.refresh(layout=True)

                pass
            # CHeck if drive has CURRENT.UF2 file
            for d in self.driveList:
                forceUpdateBootloader = False
                dfuDrive, info = self.mt.checkDrive(d.mountpoint)
                if dfuDrive:
                    self.mt_logs.write(f"Drive: {d.device}, dfuDrive: {dfuDrive}:")
                    try:
                        dl.highlighted = self.driveList.index(d)
                        bl.highlighted = self.mt.getBoardsList().index(
                            info.get("board_id", 0)
                        )
                    except Exception:
                        pass
                    ubCB = self.query_one(
                        f"#mmh_{meshtools.mmhSteps.UPDATE_BOOTLOADER.value}", Checkbox
                    )
                    forceUpdateBootloader, bootLoaderAvailable = (
                        self.mt.forceBootloaderUpdate(
                            info.get("board_id", ""),
                            self.mt.checkVersion(info.get("bootloader", "0")),
                        )
                    )

                    self.mt_logs.write(
                        f"\tboard: {info.get('board_id','')}, new bootloader: {not forceUpdateBootloader}, bootloader: {info.get('bootloader', '')}, softdevice: {info.get('softdevice','')}"
                    )
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
                    lt = await self.hltext(
                        f"{label}: {self.labelsList.get(label)}", ("([^:]+):", style)
                    )
                    lbl = Static(content=lt, classes="labels")
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

    """
    Create RadioButtons for available ports
    Create  additional buttons (Stop and reconnecting button)
    Reconnecting button is UI element represent  COM port not available in system,
    but triyng to open by serial (in case port was opened but device disconnected from PC)
    """

    def createPortsRB(self):
        arr = []
        rsbState = False
        try:
            # rsbState = self.query_one("#stopRB").value
            # Check if last pressed button was stopRB
            pls = self.query(".comports").nodes
            for pl in pls:
                rsbState = True if pl.pressed_button.id == "stopRB" else False
            # rsbState = True if self.query_one("#portList").pressed_button.id =="stopRB" else False
        except Exception:
            pass
        if self.ports:
            arr = [
                RadioButton(t, tooltip=self.ports[i].description, id=self.ports[i].name)
                for i, t in enumerate(self.ps)
            ]
        if (
            self.sm.port
            and self.sm.port not in self.ports
            and self.sm.state == serialModule.States.Reconnecting
        ):
            recB = RadioButton(
                self.sm.port.name,
                tooltip=self.sm.port.description,
                id=self.sm.port.name,
            )
            recB.add_class("fakeRB")
            arr.append(recB)
        stop = RadioButton("Stop", tooltip="Stop logging", id="stopRB", value=rsbState)
        arr.append(stop)
        for b in arr:
            b.can_focus = False
        self.portsRB = arr

    @work(exclusive=True)
    async def on_radio_button_changed(self, event: RadioButton.Changed) -> None:
        pass

    @work(exclusive=True)
    async def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        # Get selected platform(board type) and disable all steps which not available for this platform, using getAvailableMmhSteps method
        if (
            self.getCurrentToolPane().id == "meshtools-tab"
            and event.option_list.id in ("platformList", "driveList")
            and self.query_one("#platformList", OptionList).highlighted is not None
        ):

            platform = self.mt.getBoardsList()[
                self.query_one("#platformList", OptionList).highlighted
            ]
            avSteps, fwSelect = await self.mt.getAvailableMmhSteps(platform)
            avSteps = [f"mmh_{x.value}" for x in avSteps]
            checkBoxes = self.query(".mmh_checkbox").nodes
            for chb in checkBoxes:
                if chb.id not in avSteps:
                    chb.disabled = True
                    chb.value = False
                else:
                    chb.disabled = False
            if fwSelect:
                h = None
                s = None
                try:
                    h = self.query_one(
                        f"#mmhor_{meshtools.mmhSteps.UPDATE_FIRMWARE.value}", Horizontal
                    )
                    s = self.query_one("#fwSelect")
                except Exception:
                    pass
                v = await self.mt.getFirmwares(platform)
                if len(v) > 0:
                    if not s:
                        s = Select(
                            [(x, x) for x in v],
                            id="fwSelect",
                            prompt="Select..",
                            allow_blank=True,
                            value=v[0],
                        )
                        h.mount(s)
                    else:
                        curv = await self.getSelectedVersion()
                        s.set_options([(x, x) for x in v])
                        if curv not in v:
                            s.value = v[0]
                        else:
                            s.value = curv
            else:
                s = None
                try:
                    s = self.query_one("#fwSelect")
                    s.remove()
                except Exception:
                    pass

    async def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        if (
            self.config.get("config", {}).get(constants.CFG_LOG_BOARD_CFG, False)
            and self.getCurrentToolPane().id == "meshtools-tab"
            and event.option_list.id in ("platformList")
        ):
            platform = self.mt.getBoardsList()[
                self.query_one("#platformList", OptionList).highlighted
            ]
            await self.mt.logPlatformConfig(platform=platform)

    mltask = None

    @work(exclusive=True)
    async def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self.sm.stopLoop = True
        await self.mt.closeSerial()
        # Wait while active serial connection is stopped
        # We can check  task state or self.sm.state (currently `task`` to avoid several active tasks running)
        while self.mltask and self.mltask._state != "FINISHED":
            await asyncio.sleep(0.1)

        # Remove fakeRB (`reconnecting` button) if other radiobutton clicked
        for rb in event.control.children:
            if rb.has_class("fakeRB") and rb != event.pressed:
                await rb.remove()
        # Update logger and start serial for selected port
        if event.pressed.id != "stopRB":
            try:
                indx = self.ps.index(event.pressed.label.plain)
                port = self.ports[indx]
                self.updateLogger(port=port.device)
                # Get active toolTab
                pane = self.getCurrentToolPane()

                # Preventing multiple tasks with serial
                if not self.mltask or self.mltask._state == "FINISHED":
                    if pane.id == "serial-tab":
                        self.mltask = asyncio.create_task(
                            asyncio.to_thread(self.runSerial, port)
                        )
                    if pane.id == "meshtools-tab":
                        # Connect to serial as meshtastic client
                        await self.mt.openSerial(port)
            except Exception:
                pass
        else:
            pass

    def getCurrentToolPane(self):
        pane = [p for p in self.query(".toolTab") if p.display]
        pane = pane[0] if pane else None
        return pane

    def runSerial(self, port):
        self.sm.mainLoop(
            port,
            int(self.config.get("config").get(constants.CFG_BAUDRATE, 115200)),
            bool(self.config.get("config").get(constants.CFG_AUTO_RECONNECT, False)),
            waitNewPort=False,
        )

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.parent.id == "settings":
            self.config["config"][event.checkbox.id] = event.checkbox.value
            # Hack for reactive dict https://github.com/Textualize/textual/issues/1098
            self.config = self.config
            # TODO need to use async io library (?) or move to watch_config
            writeConfigFile(self.config, "config")
            self.notify(message="Config saved", timeout=1)
        if event.checkbox.parent.id == "mmh_steps":
            pass

    @on(Input.Submitted, selector=".settings_element")
    @on(Input.Blurred, selector=".settings_element")
    async def on_submit(self, event: Input.Submitted) -> None:
        if event.input._initial_value:
            return
        if event.input.oldValue != event.input.value:
            event.input.oldValue = event.input.value
            self.config["config"][event.input.id] = event.input.value
            # TODO need to use async io library
            writeConfigFile(self.config, "config")
            self.notify(message=f"Config saved: {event.input.id}", timeout=2)

    @work(exclusive=True, thread=True)
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "bootl":
                if (
                    self.query_one("#driveList", OptionList).highlighted is not None
                    and self.query_one("#platformList", OptionList).highlighted
                    is not None
                ):
                    self.mt.copyFile(
                        type="bootloader",
                        platform=self.query_one(
                            "#platformList", OptionList
                        ).highlighted,
                        targetFolder=self.driveList[
                            self.query_one("#driveList", OptionList).highlighted
                        ].mountpoint,
                    )

            case "mmh_btn":
                vars = {
                    "version": None,
                }
                if self.query_one("#platformList", OptionList).highlighted is not None:
                    platform = self.mt.getBoardsList()[
                        self.query_one("#platformList", OptionList).highlighted
                    ]
                else:
                    return
                driveN = self.query_one("#driveList", OptionList).highlighted
                if platform is not None and driveN is not None:
                    targetFolder = self.driveList[driveN].mountpoint
                    steps = [
                        s.name
                        for s in meshtools.mmhSteps
                        if self.query_one(f"#mmh_{s.value}").value
                    ]
                    vars["version"] = await self.getSelectedVersion()
                    try:
                        stepsExecuted = await self.mt.execMmhSteps(
                            platform=platform,
                            targetFolder=targetFolder,
                            steps=steps,
                            sm=self.sm,
                            vars=vars,
                        )
                        await self.mmhDisableExecuted(stepsExecuted=stepsExecuted)
                        if meshtools.mmhSteps.OPEN_CONSOLE.name in stepsExecuted:
                            self.logUI.focus()
                        # asyncio.create_task(asyncio.to_thread(self.mt.execMmhSteps,platform=platform, targetFolder=targetFolder, steps= steps, sm = self.sm))
                    except Exception as e:
                        self.write(str(e))
                        raise e
                        pass
            case x if "meshOption_" in x:
                # All logic in meshtools module
                await self.mt.meshOptionsFunc(x)

    # Method returns value of Select widget if exists, None otherwise
    async def getSelectedVersion(self):
        try:
            s = self.query_one("#fwSelect")
            return s.value
        except Exception:
            return None

    async def mmhDisableExecuted(self, stepsExecuted: list = None):
        if stepsExecuted:
            for s in stepsExecuted:
                try:
                    self.query_one(
                        f"#mmh_{meshtools.mmhSteps[s].value}", Checkbox
                    ).value = False
                except Exception:
                    pass

    def setPorts(self, ports: list):
        self.ps = [f"{port.name}" for port in ports]
        self.ports = ports

    def getPortByName(self, name):
        for p in self.ports:
            if p.name == name:
                return p
        return None

    """
    Check port pid in config
    if found - try to connect by meshtools and get key and cfg (if config params is true)
    """

    @work(exclusive=True, thread=True)
    async def checkPortAndSave(self):
        # Autosave only if MeshTab active
        tab = None
        try:
            tab = self.query_one("#meshtools-tab", TabPane)
        except Exception:
            return
        if tab.is_on_screen:
            # Autosave only if cfg parameter is true
            if self.config.get("config").get(constants.CFG_AUTO_SAVE_NODE_CFG, False):
                # Exclude already opened/reconnecting port
                if self.sm.state in (
                    serialModule.States.Active,
                    serialModule.States.Reconnecting,
                ):
                    ports = [p for p in self.ports if p != self.sm.port]
                else:
                    ports = self.ports
                await self.mt.autoSaveCFG(ports)


def readConfig():

    if not os.path.exists(constants.CONFIG_DIR):
        # Download default configs from github to get basic settings
        repo_url = constants.DEF_CONFIG_URL

        ## Send a GET request to the GitHub API
        response = requests.get(repo_url, timeout=3)
        os.makedirs(constants.CONFIG_DIR)
        ## Iterate through the folder contents and download each file
        for item in response.json():
            if item["type"] == "file":
                file_url = item["download_url"]
                file_name = item["name"]
                file_path = f"{constants.CONFIG_DIR}/{file_name}"

                ## Download the file
                file_response = requests.get(file_url, timeout=3)
                with open(file_path, "wb") as file:
                    file.write(file_response.content)

    # Read all yaml files in config folder and return them as common dictionary

    config_files = [f for f in os.listdir(constants.CONFIG_DIR) if f.endswith(".yaml")]
    config_dict = {}
    for file in config_files:
        with open(os.path.join(constants.CONFIG_DIR, file), "r") as stream:

            config_dict[pathlib.Path(file).stem] = yaml.safe_load(stream)
    if config_dict.get("config", {}) is not None:
        default_config.update(config_dict.get("config", {}))
    config_dict["config"] = default_config

    return config_dict


def writeConfigFile(config_dict, filename):
    with open(os.path.join(constants.CONFIG_DIR, f"{filename}.yaml"), "w") as f:
        yaml.dump(config_dict.get(filename), f)


def init():
    return


def handler(signal_received, frame):
    # Handle any cleanup here
    print("SIGINT or CTRL-C detected. Exiting logging gracefully")
    # q.put(True)


if __name__ == "__main__":
    signal(SIGINT, handler)
    print("Running. Press CTRL-C to exit.")
    loop = True
    app = PortSelector(config=readConfig())
    # app.config = readConfig()
    app.setPorts(serialModule.get_available_ports())
    app.run()
