const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('smartFactoryElectron', {
  getMemory: () => ipcRenderer.invoke('sfl:get-electron-memory'),
});
