"""
test_more.py - second real test file. Imports your actual main.py and calls the app's own methods.
Run:  python test_more.py            (tests main.py)
      python test_more.py main_v8_2  (tests another file, name without .py)
Each line is PASS or FAIL. A FAIL is a finding, not a crash. Does NOT cover dialogs, Liquify, Timeline.
"""
import importlib, os, sys, time, tempfile
import tkinter as tk
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
m = importlib.import_module(sys.argv[1] if len(sys.argv) > 1 else "main")
errors = []
m.messagebox.showerror = lambda *a, **k: errors.append(a)       # record popups instead of showing them
m.messagebox.showinfo = lambda *a, **k: None
root = tk.Tk(); root.geometry("1200x800")
app = m.ImageEditor(root); root.update()
results = []

def check(name, ok, info=""):
    results.append(bool(ok)); print(("PASS  " if ok else "FAIL  ") + name, info)

def fresh(layers=None):
    img = Image.new("RGBA", (200, 100), (255, 0, 0, 255)); img.paste((0, 0, 255, 255), (100, 0, 200, 100))
    app.layers = layers or [m.Layer("Background", img)]
    app.active_layer_idx = len(app.layers) - 1
    app.undo_stack.clear(); app.redo_stack.clear(); errors.clear()
    app.zoom = 1.0; app.pan_x = app.pan_y = 0
    app.display_composite(); root.update()

def px(layer_idx=0, xy=(10, 10)): return app.layers[layer_idx].image.getpixel(xy)
def run(name, fn):
    try: fn()
    except Exception as e: check(name, False, f"CRASH {type(e).__name__}: {e}")

def t_rotate():
    fresh(); app.rotate_image(90); check("rotate 90 swaps size", app.layers[0].image.size == (100, 200), app.layers[0].image.size)
run("rotate", t_rotate)

def t_flip():
    fresh(); app.flip_image("h"); check("flip horizontal moves colors", px()[:3] == (0, 0, 255), px())
run("flip", t_flip)

def t_filters():
    for f in ["grayscale", "sepia", "invert", "blur", "sharpen", "edge", "emboss", "detail", "bw_contrast"]:
        fresh(); app.apply_filter(f)
        im = app.layers[0].image
        check(f"filter {f}: runs, size+alpha kept", im.size == (200, 100) and im.mode == "RGBA" and not errors, f"{im.size} {im.mode} errors={len(errors)}")
    fresh(); app.apply_filter("grayscale"); r, g, b = px()[:3]
    check("grayscale gives equal R=G=B", r == g == b, px())
    fresh(); app.apply_filter("invert"); check("invert flips red to cyan", px()[:3] == (0, 255, 255), px())
    fresh(); app.apply_filter("blur"); app.undo(); check("undo after filter restores original", px()[:3] == (255, 0, 0), px())
run("filters", t_filters)

def t_sepia_speed():
    big = Image.new("RGBA", (2000, 1500), (120, 80, 40, 255)); fresh([m.Layer("Background", big)])
    t = time.time(); app.apply_filter("sepia"); dt = time.time() - t
    check("sepia on a 3 MP photo takes under 3 seconds", dt < 3, f"took {dt:.1f}s")
run("sepia speed", t_sepia_speed)

def t_adjust():
    fresh(); app.sliders["brightness"].set(1.5); app.apply_adjustments()
    check("brightness slider 1.5 brightens", px()[0] >= 255 and px(0, (150, 10))[2] > 250, px()); app.reset_sliders()
run("adjust", t_adjust)

def t_resize():
    fresh(); app.display_composite(); app.width_entry.delete(0, tk.END); app.width_entry.insert(0, "100")
    app.lock_aspect.set(True); app.apply_resize()
    check("resize to width 100 keeps aspect (100x50)", app.layers[0].image.size == (100, 50), app.layers[0].image.size)
run("resize", t_resize)

def t_blend_math():
    a = Image.new("RGB", (2, 2), (128, 128, 128)); b = Image.new("RGB", (2, 2), (128, 128, 128))
    mul = app.apply_true_blend(a, b, "multiply").getpixel((0, 0))[0]
    scr = app.apply_true_blend(a, b, "screen").getpixel((0, 0))[0]
    check("multiply 128x128 is about 64", abs(mul - 64) <= 2, mul)
    check("screen 128,128 is about 192", abs(scr - 192) <= 2, scr)
run("blend math", t_blend_math)

def t_opacity():
    base = Image.new("RGBA", (50, 50), (0, 0, 255, 255)); top = Image.new("RGBA", (50, 50), (255, 0, 0, 255))
    layers = [m.Layer("b", base), m.Layer("t", top, opacity=0.5)]
    app.layers = layers; app.active_layer_idx = 1; errors.clear()
    c1 = app.get_composite().getpixel((5, 5)); c2 = app.get_composite().getpixel((5, 5)); c3 = app.get_composite().getpixel((5, 5))
    check("50% red over blue gives about (128,0,128)", abs(c1[0] - 128) <= 6 and abs(c1[2] - 128) <= 6, c1)
    check("redrawing does not change the result (3 redraws identical)", c1 == c2 == c3, (c1, c2, c3))
    check("layer pixels are not altered by drawing (alpha stays 255)", layers[1].image.getpixel((5, 5))[3] == 255, layers[1].image.getpixel((5, 5)))
run("opacity", t_opacity)

def t_mask():
    fresh(); app.add_layer_mask()
    mk = Image.new("L", (200, 100), 255); mk.paste(0, (0, 0, 100, 100)); app.layers[0].mask = mk
    c = app.get_composite(); check("mask hides the left half", c.getpixel((10, 10))[3] == 0 and c.getpixel((150, 10))[3] == 255, (c.getpixel((10, 10)), c.getpixel((150, 10))))
    app.apply_layer_mask(); check("apply mask bakes alpha and removes mask", app.layers[0].mask is None and px()[3] == 0, px())
run("mask", t_mask)

def t_wand():
    fresh(); app.wand_tolerance.set(20); app.wand_contiguous.set(True)
    mk = app.magic_wand_select(10, 10); n = sum(1 for v in mk.getdata() if v == 255)
    check("magic wand selects the red half only (10000 px)", n == 10000, n)
run("wand", t_wand)

def t_adj_layers():
    for typ, data in [("brightness_contrast", {"brightness": 1.5, "contrast": 1.0}), ("hue_sat", {"hue": 0, "saturation": 0.0}),
                      ("black_white", {}), ("levels", {"shadow": 0, "mid": 1.0, "highlight": 128}),
                      ("curves", {"curves": []}), ("color_balance", {"r": 60, "g": 0, "b": -60})]:
        base = Image.new("RGBA", (50, 50), (200, 100, 50, 255)); adj = m.Layer("adj", Image.new("RGBA", (50, 50), (0, 0, 0, 0)))
        adj.is_adjustment_layer = True; adj.adjustment_type = typ; adj.adjustment_data = data
        fresh([m.Layer("b", base), adj]); c = app.get_composited_image().getpixel((5, 5))[:3]
        check(f"adjustment layer '{typ}' changes the picture", c != (200, 100, 50), c)
run("adjustment layers", t_adj_layers)

root.destroy()
print(f"\n{sum(results)}/{len(results)} passed  (module: {m.__name__})")
sys.exit(0 if all(results) else 1)
