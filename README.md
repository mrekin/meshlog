# Another one serial logger :)

## Why
I need a tool to simplify meshtastic nodes log analisys. I didn't found anything usefull, so build my own ugly coded logger.

## Interface

![v0.11 screen](images/screen.png)

## ToDo (near future)
- [x] Autoreconnect to latest COM port
- [x] Port list autoupdates
  - [ ] Fix bugs with UI in port list
- [ ] Custom configurable labels
  - [ ] Static
  - [x] Regexp (groups)
  - [ ] Regexp (match) - is it needed?
  - [x] String/bool result
  - [x] `dropAfter` param
  - [x] `firstEntrance` rule
  - [ ] `searchAfter` param
- [ ] Make working Settings tab
  - [ ] UI
  - [ ] Save/load settings
  - [ ] Use settings in logic
- [ ] Implement logging to file
  - [ ] Single file
  - [ ] Separate file for each COM port
  - [ ] Separate file for each connection
- [ ] `Send to` logic for logs and checks/labels
- [x] Test on Windows system
- [ ] Windows executable
  - [x] Manual build
  - [ ] Autobuilds
- [ ] Test on Linux system
- [ ] Linux executable
  - [ ] Manual build
  - [ ] Autobuilds
- [ ] Github releases
## ToDo (far future)
- [ ] Use Meshtastic library
  - [ ] Use not only serial connection, but IP/Bluetooth
  - [ ] Get/upload node config
  - [ ] Get node status
  - [ ] Trigger DFU mode
  - [ ] (?) Trigger reboot/nodeinfo send/etc
- [ ] NRF52 flashing
  - [ ] Upload fullerase uf2
  - [ ] Upload newest bootloader
  - [ ] Upload firmware
