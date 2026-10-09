# Architecture
- Language: Python 3.12
- UI: PySide6 (Qt, LGPL). Canvas is a QGraphicsView.
- Images: Pillow for loading and saving, NumPy for pixel math later.
- Everything runs on the CPU; no GPU required.
- Core editing code will stay separate from UI code so a future assistant and plugins can call it safely.
