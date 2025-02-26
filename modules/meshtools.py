import psutil
import meshtastic
import os, requests, shutil
import constants

class MeshTools:
    
    
    # method for listing all mouned drives on the system indepedent of os type
    def listDrives(self):
        drives = psutil.disk_partitions()
        return drives
    
    # method for downloading file from given url to folder
    def downloadFile(self, url, folder, filename):
        filepath = os.path.join(folder, filename)
        response = requests.get(url)
        if response.status_code == 200:
            with open(filepath, 'wb') as f:
                f.write(response.content)
        else:
            print(f"Error: {response.status_code}")
            
    # method checks if file exist. If no - download it
    # then copy file to given path
    def copyFile(self, url, filename, targetPath):
        filepath = os.path.join(constants.FILES_DIR, filename)
        if not os.path.exists(filepath):
            self.downloadFile(url, constants.FILES_DIR, filename)
        # copy file to target path
        shutil.copy(filepath, targetPath, follow_symlinks=False)
        return
    
    