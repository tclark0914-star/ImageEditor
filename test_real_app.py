import importlib, os, sys, tempfile
import tkinter as tk
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
m = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "main")

root = tk.Tk(); root.geometry("1200x800")
app = m.ImageEditor(root); root.update()
results = []

def check(name, ok, info=""):
    results.append(bool(ok)); print(("PASS  " if ok else "FAIL  ") + name, info)

def fresh():
    img = Image.new("RGBA", (400, 300), (255, 0, 0, 255))
    img.paste((0, 0, 255, 255), (200, 0, 400, 300))
    app.layers = [m.Layer("Background", img)]
    app.active_layer_idx = 0; app.zoom = 1.0; app.pan_x = app.pan_y = 0
    app.undo_stack.clear(); app.redo_stack.clear()
    app.crop_coords = None
    if hasattr(app, "crop_frac"): app.crop_frac = None
    app.current_tool.set("crop"); app.refresh_layers_list()
    app.display_composite(); root.update()

class Ev:
    def __init__(self, x, y): self.x, self.y = x, y

def drag(x0, y0, x1, y1):
    app.on_crop_press(Ev(x0, y0)); app.on_crop_drag(Ev(x1, y1)); app.on_crop_release(Ev(x1, y1))

def pix(): return app.layers[0].image.getpixel((5, 5))[:3]
def size(): return app.layers[0].image.size

fresh(); ox, oy = app.image_offset
check("image displays at 100%", app.display_size == (400, 300), app.display_size)

drag(ox + 200, oy, ox + 400, oy + 300); app.apply_crop(); root.update()
check("crop right half", size() == (200, 300) and pix() == (0, 0, 255), f"{size()} {pix()}")
app.undo(); root.update()
check("undo crop", size() == (400, 300), size())
app.redo(); root.update()
check("redo crop", size() == (200, 300), size())

fresh(); ox, oy = app.image_offset
drag(ox, oy, ox + 200, oy + 300)
app.zoom = 0.5; app.pan_x = 137; app.pan_y = -42
app.display_composite(); root.update(); app.apply_crop()
check("crop still correct after zoom+pan (left/red half)", size() == (200, 300) and pix() == (255, 0, 0), f"{size()} {pix()}")

fresh(); ox, oy = app.image_offset
drag(ox + 200, oy, ox + 400, oy + 300)
app.zoom = 1.5; app.display_composite(); root.update(); app.apply_crop()
check("crop still correct after zoom in (right/blue half)", size() == (200, 300) and pix() == (0, 0, 255), f"{size()} {pix()}")

fresh(); app.add_layer(); root.update()
check("new layer added", len(app.layers) == 2, [l.name for l in app.layers])
app.undo(); root.update()
check("undo removes new layer", len(app.layers) == 1)

fresh()
out = os.path.join(tempfile.gettempdir(), "imageeditor_test.png")
app.get_composite().save(out); back = Image.open(out)
check("save PNG and reopen", back.size == (400, 300), back.size)

root.destroy()
print(f"\n{sum(results)}/{len(results)} passed  (module: {m.__name__})")
sys.exit(0 if all(results) else 1)
