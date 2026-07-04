const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('smartFactoryElectron', {
  getMemory: () => ipcRenderer.invoke('sfl:get-electron-memory'),
  recordStartupEvent: (name, payload) => ipcRenderer.invoke('sfl:record-startup-event', name, payload),
});
