import psutil, asyncio, re
#import meshtastic
import os, requests, shutil
from . import constants, serialModule
from urllib.parse import urlparse
from enum import Enum
import pyrfc6266

class Log(object):
    def write(self, text):
        pass

class mmhSteps(Enum):
    UPDATE_BOOTLOADER = 0
    FULL_ERASE = 1
    UPDATE_FIRMWARE = 2
    OPEN_CONSOLE = 3
    
class MeshTools:
    boards = {}
    log = Log()
    
    def __init__(self,cfg, log_callback = None):
        self.boards = cfg.get('boards','')
        if log_callback:
            self.log.write = log_callback
    
    def getBoardsList(self):
        return [b.get('name', None) for b in self.boards]
    
    def setLogCallback(self, log_callback):
        self.log.write = log_callback
    # method for listing all mouned drives on the system indepedent of os type
    def listDrives(self):
        drives = psutil.disk_partitions()
        return drives
    
    # method for downloading file from given url to folder
    def downloadFile(self, url= None, folder = constants.FILES_DIR, filename = None, type = None, platform: int = None):
        
        response = requests.get(url)

        if response.status_code == 200:
            try:
                filename = pyrfc6266.requests_response_to_filename(response)
            except Exception as e:
                pass
            filepath = os.path.join(folder, filename)
            if os.path.exists(filepath):
                self.log.write(f"File {filename} already exists")
                return filename
            
            if not os.path.exists(constants.FILES_DIR):
                os.makedirs(constants.FILES_DIR)
            with open(filepath, 'wb') as f:
                f.write(response.content)
        else:
            print(f"Error: {response.status_code}")
        return filename
            
    # method checks if file exist. If no - download it
    # then copy file to given path
    def copyFile(self, url= None, targetFolder = None, filename = None, type = None, platform: int = None):
        if not url:
            match type:
                case 'bootloader':
                    url = self.boards[self.getBoardsList().index(platform)].get(constants.CFG_BOOTLOADER_URL,None)
                    if not url:
                        self.log.write(f"Bootloader url is not set in config ({platform})")
                        return
                    if not filename:
                        parsed_url = urlparse(url)
                        filename = os.path.basename(parsed_url.path)
                case 'fullerase':
                    url = self.boards[self.getBoardsList().index(platform)].get(constants.CFG_FULLERASE_URL,None)
                    if not url:
                        self.log.write(f"Full erase url is not set in config ({platform})")
                        return
                    if not filename:
                        parsed_url = urlparse(url)
                        filename = os.path.basename(parsed_url.path)
                        
                case 'firmware':
                    url = self.boards[self.getBoardsList().index(platform)].get(constants.CFG_FIRMWARE_URL,None)
                    if not url:
                        self.log.write(f"Firmware url is not set in config ({platform})")
                        return
                    if not filename:
                        parsed_url = urlparse(url)
                        filename = os.path.basename(parsed_url.path)                        
                
        filename = filename if '.uf2' in filename else f"{platform}_{type}.uf2"
        self.log.write(f"Downloading file: {url}")
        filename = self.downloadFile(url, folder = constants.FILES_DIR, filename = filename, type= type, platform= platform)
        filepath = os.path.join(constants.FILES_DIR, filename)
        # copy file to target path
        try:
            self.log.write(f"Copying file: {filepath} to {targetFolder}")
            shutil.copy(filepath, targetFolder, follow_symlinks=False)
        except Exception as e: 
            pass
        
        return
    
    # Check if drive has bootloader info file and get usefull info from this file
    def checkDrive(self, driveMountPoint:str):
        dfuDrive = False
        uf2Info = {}
        txtFile = os.path.join(driveMountPoint, "INFO_UF2.TXT")
        if os.path.exists(txtFile):
            dfuDrive = True
            with open(txtFile, 'r') as file:
                #read file line by line
                for line in file:
                    #iterate UF2_TXT_TOKENS and get first group matching value
                    for token in constants.UF2_TXT_TOKENS:
                        match = re.search(constants.UF2_TXT_TOKENS[token], line.strip())
                        if match:
                            uf2Info[token] = match.group(1)

        return dfuDrive, uf2Info
    
    async def execMmhSteps(self, platform = None, targetFolder = None, steps= [], sm: serialModule.SerialModule  = None):
        stepsExecuted = []
        ports = sm.get_available_ports()[0]
        if mmhSteps.UPDATE_BOOTLOADER.name in steps:
            self.log.write(f"--> Bootloader step.")            
            self.copyFile(type = 'bootloader', 
                                platform = platform,
                                targetFolder= targetFolder
                                )
            self.log.write("Done")
            ports = sm.get_available_ports()[0]
            stepsExecuted.append(mmhSteps.UPDATE_BOOTLOADER.name)
        if mmhSteps.FULL_ERASE.name in steps:
            self.log.write(f"--> Full erase step.")
            # Wait for drive to be mounted
            self.log.write(f"Waiting for drive {targetFolder} to be mounted..")
            try:
                bingo = await self.waitDriveOrSerial(ports = ports, sm = sm, targetFolder = targetFolder, delay = 10, platform = platform)
            except Exception as e:
                self.log.write(f"Error: {e}")
            
            if not self.checkDrive(targetFolder):
                self.log.write(f"Drive {targetFolder} is not a DFU drive")
                bingo = False
            
            if not bingo:
                self.log.write(f"Please enable DFU mode manually (double reset) and do Full Erase again")
                return stepsExecuted
            
            self.log.write("Downloading full erase file...")
            
            self.copyFile(type = 'fullerase', 
                                platform = platform,
                                targetFolder= targetFolder
                                )
            ports = sm.get_available_ports()[0]
            try:
                await asyncio.sleep(2)
                bingo = await self.waitDriveOrSerial(ports = ports, sm = sm, targetFolder = targetFolder, delay = 10, platform = platform)
            except Exception as e:
                self.log.write(f"Error: {e}")
            self.log.write("Done")
            stepsExecuted.append(mmhSteps.FULL_ERASE.name)
        if mmhSteps.UPDATE_FIRMWARE.name in steps:
            # Wait for drive to be mounted
            self.log.write(f"Waiting for drive {targetFolder} to be mounted..")
            bingo = await self.waitDriveOrSerial(ports = ports, sm = sm, targetFolder = targetFolder, delay = 10, platform = platform)
            
            if not self.checkDrive(targetFolder):
                self.log.write(f"Drive {targetFolder} is not a DFU drive")
                bingo = False
            
            if not bingo:
                self.log.write(f"Please enable DFU mode manually (double reset) and do UPDATE_FIRMWARE again")
                return stepsExecuted
            self.log.write("Downloading firmware file...")
            self.copyFile(type = 'firmware', 
                                platform = platform,
                                targetFolder= targetFolder
                                )   
            self.log.write("Done")
            stepsExecuted.append(mmhSteps.UPDATE_FIRMWARE.name) 

        if mmhSteps.OPEN_CONSOLE.name in steps:
            self.log.write(f"Opening serial console...")
            asyncio.create_task(sm.readNewSerial(ports))
            self.log.write("Done. Switching to serial pane...")
            stepsExecuted.append(mmhSteps.OPEN_CONSOLE.name)
        return stepsExecuted
    
    async def waitDriveOrSerial(self, targetFolder:str = None, sm = None, ports = None, delay:int =10, platform : str = None):
            res = False
            while not os.path.exists(targetFolder) and not res:
                delay-=1
                newPorts = sm.check_new_port(ports)
                if newPorts:
                    if platform == 'nRF52840-nicenano':
                        self.log.write("Catching new serial")
                        res = await sm.readNewSerial(ports, sendOnConnect = '\\n')
                        self.log.write("Done. Check Serial tab. Re-connect USB if Factory restore not catched")
                        #await asyncio.sleep(1)
                if not delay:
                    return False
            return True
    
    # TODO re-use version comparition from webTools
    def checkVersion(self, versionCurrent:str, versionNew: str = '0.8.0'):
        #compare versions line 0.8.0 and 0.9.1
        current = versionCurrent.split('.')
        new = versionNew.split('.')
        for i in range(0,len(current)):
            if int(current[i]) < int(new[i]):
                return True
        return False
    
    def bootLoaderAvailable(self, platform: str):
        try:
            res=  bool(self.boards[self.getBoardsList().index(platform)].get(constants.CFG_BOOTLOADER_URL,None))
        except Exception as e:
            res = False
        return res
    
    def forceBootloaderUpdate(self, platform: str, isOldBootloader: bool):
        available = self.bootLoaderAvailable(platform)
        force = available if isOldBootloader else False
        return force, available