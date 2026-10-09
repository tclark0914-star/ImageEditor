# ImageEditor - Photoshop-Style AI Image Editor

**Version:** v1.0-ai-editor  
**Repo:** https://github.com/tclark0914-star/ImageEditor  
**Author:** Toby Clark  
**Built:** 100% in Python + Tkinter + Pillow + rembg

A lightweight Photoshop-style image editor built from scratch in 4 milestones. No monthly subscription, all local, never overwrites originals.

## Features

### Milestone 1 - Core Viewer
- Open any image (PNG, JPG, BMP, GIF, TIFF, WebP)
- Centered canvas with zoom-to-fit
- Status bar

### Milestone 2 - Photoshop UI
- Left toolbar (Tools panel) - dark theme
- Right panels: Adjustments + Resize & Save
- Crop Mode: Drag rectangle on canvas, Apply Crop
- Rotate: 90° Left/Right + custom angle
- Flip Horizontal / Vertical
- Resize with Lock Aspect Ratio
- Adjustments: Brightness, Contrast, Saturation, Sharpness (live sliders)
- Undo/Redo (Ctrl+Z / Ctrl+Y)
- Save As New File - **never overwrites original**

### Milestone 3 - Layers (like Photoshop)
- Layers panel with active marker `>`
- New Layer (transparent), Duplicate, Delete, Merge Down, Flatten
- Opacity slider 0-100% live
- Visibility toggle (O/X)
- All tools work on Active Layer
- Crop/Resize apply to all layers to keep alignment
- History panel - visual undo stack
- Composite display with transparency checker handled

### Milestone 4 - AI Assisted
- **Remove Background (AI)** - Uses `rembg` U2Net model. If not installed, falls back to white removal. Shortcut Ctrl+B
- **Upscale 2x** - LANCZOS high-quality 2x (all layers)
- **Auto Enhance** - Autocontrast + auto color + brightness normalization
- **Denoise** - Median filter
- **Smart Sharpen** - UnsharpMask

## Install

```powershell
cd $HOME\Documents\ImageEditor
pip install pillow rembg onnxruntime
python main.py
```

First time you click Remove Background, it downloads ~170MB model to `C:\Users\YOU\.u2net` - takes 10-15s then instant.

## How to Run Without PowerShell Every Time

### Option 1 - Desktop Shortcut (30 seconds, recommended)

1. Right-click Desktop > New > Shortcut
2. Paste this as location:
```
C:\Users\tc06h\AppData\Local\Programs\Python\Python312\pythonw.exe C:\Users\tc06h\Documents\ImageEditor\main.py
```
(adjust Python path if yours is different - check `where python` in PowerShell)

3. Name: `ImageEditor`
4. Right-click the new shortcut > Properties > Change Icon > pick something

Double-click to launch!

**Or use the included batch file:**

Double-click `ImageEditor.bat` - we created it for you.

### Option 2 - Make a Real .EXE (5 minutes)

This builds a single `ImageEditor.exe` you can share:

```powershell
cd $HOME\Documents\ImageEditor
pip install pyinstaller
pyinstaller --onefile --windowed --name ImageEditor --clean main.py
```

EXE will be in `dist\ImageEditor.exe`

**Warning:** With rembg included, EXE is ~300-600MB because it bundles numpy, scipy, onnxruntime, scikit-image. Without rembg, ~30MB.

For smaller EXE, build from Milestone 2 version (no AI):
```powershell
pyinstaller --onefile --windowed --name ImageEditorLite main.py
```

### Option 3 - Auto-Start with Windows

1. Press `Win+R` > type `shell:startup` > Enter
2. Copy your desktop shortcut into that Startup folder

## Shortcuts

- Ctrl+O - Open
- Ctrl+S - Save As
- Ctrl+L - New Layer
- Ctrl+B - Remove Background (AI)
- Ctrl+E - Merge Down
- Ctrl+Z - Undo
- Ctrl+Y - Redo
- Del - Delete Layer

## Git Workflow (what you learned)

```powershell
cd $HOME\Documents\ImageEditor
python main.py          # test
git add main.py
git commit -m "Describe change"
git push
git tag v1.0-name
git push origin v1.0-name
```

Always `cd` to `ImageEditor` first - PowerShell starts in `C:\WINDOWS\system32` where git won't work.

## Project Status

All 4 milestones complete and pushed to `main` branch:
- b45cb9a Milestone 1
- 1cae92c Milestone 2
- 65627d5 Milestone 3 (Layers)
- cf1d04a Milestone 4 (AI) - v1.0-ai-editor tag

## Future Ideas

- Text layers
- Brush/draw on transparent layer
- Real-ESRGAN upscaler (replace LANCZOS)
- Drag & drop images onto canvas
- Layer reordering via drag

---
Built with ❤️ in PowerShell + Tkinter
