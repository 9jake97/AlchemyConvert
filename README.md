# Batch Zicon Generator — Source Release

## Quick Start

1. Install [Node.js](https://nodejs.org) (v18+)
2. Open a terminal in this folder
3. Run:
   ```
   npm install
   npm start
   ```

## Notes

- **No license required** — authentication has been removed.
- **On first conversion**, the app will automatically download ~600MB of Minecraft default vanilla assets from GitHub. This is a one-time operation.
- The Python backend (`ConvertRP/converter.py`) uses PyArmor and requires the included `python_bin/` to run.

## Folder Structure

```
main.js                  Electron main process (de-obfuscated)
index.html               App UI (auth overlay removed)
src/
  app.js                 Core logic (de-obfuscated, full string resolution)
  auth.js                Auth bypass (no license needed)
  ModelViewer.js         3D Minecraft model viewer
libs/
  three.min.js           Three.js 3D library
  OrbitControls.js       Camera controls
node_modules/            Pre-installed npm packages
ConvertRP/
  converter.py           Java→Bedrock resource pack converter (PyArmor)
  python_bin/            Bundled portable Python runtime
  pyarmor_runtime_*/     PyArmor license runtime
  blank256.png           Default blank texture
```
