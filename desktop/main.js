const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");

// Parse --url=<backend> from argv
let backendUrl = "http://127.0.0.1:8765";
for (const arg of process.argv) {
  if (arg.startsWith("--url=")) {
    backendUrl = arg.slice(6);
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 940,
    minWidth: 420,
    minHeight: 360,
    frame: false,
    resizable: true,
    show: false,
    backgroundColor: "#000000",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // IPC handlers for titlebar controls
  ipcMain.handle("win:minimize", () => win.minimize());
  ipcMain.handle("win:toggleMaximize", () => {
    if (win.isMaximized()) {
      win.unmaximize();
    } else {
      win.maximize();
    }
  });
  ipcMain.handle("win:close", () => win.close());

  // Show window once content is ready to avoid white flash
  win.once("ready-to-show", () => win.show());

  win.loadURL(backendUrl);
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  app.quit();
});
