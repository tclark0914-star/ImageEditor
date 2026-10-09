
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk, ImageEnhance, ImageOps, ImageFilter, ImageStat, ImageDraw, ImageChops, ImageFont
import os
import math

try:
    from rembg import remove as rembg_remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    rembg_remove = None

class Layer:
    def __init__(self, name, image, visible=True, opacity=1.0, blend_mode="normal"):
        self.name = name
        self.image = image
        self.visible = visible
        self.opacity = opacity
        self.blend_mode = blend_mode
    def copy(self):
        return Layer(self.name, self.image.copy(), self.visible, self.opacity, self.blend_mode)

class ImageEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("ImageEditor - Milestone 6 FIXED")
        self.root.geometry("1450x950")
        self.root.minsize(1250, 800)

        self.original_path = None
        self.layers = []
        self.active_layer_idx = 0
        self.composited_image = None
        self.photo = None
        self.zoom = 1.0
        self.pan_x = 0
        self.pan_y = 0

        self.undo_stack = []
        self.redo_stack = []
        self.max_undo = 20

        # Tools
        self.current_tool = tk.StringVar(value="select")
        self.crop_mode = False
        self.crop_start = None
        self.crop_rect_id = None
        self.crop_coords = None
        self.image_offset = (0, 0)
        self.display_size = (0, 0)
        self.lock_aspect = tk.BooleanVar(value=True)

        # Brush
        self.brush_size = tk.IntVar(value=12)
        self.brush_color = "#ff0000"
        self.brush_last_pos = None
        self.is_drawing = False

        # Magic Wand - DEFINED BEFORE UI
        self.wand_tolerance = tk.IntVar(value=32)
        self.wand_contiguous = tk.BooleanVar(value=True)
        self._last_wand_mask = None

        # Clone Stamp
        self.clone_source = None
        self.clone_offset = None
        self._clone_offset = None

        # Zoom/pan
        self.pan_start = None

        self.setup_ui()
        self.bind_shortcuts()

    def setup_ui(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Image...  Ctrl+O", command=self.open_image)
        file_menu.add_command(label="Save As...    Ctrl+S", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        layer_menu = tk.Menu(menubar, tearoff=0)
        layer_menu.add_command(label="New Layer  Ctrl+L", command=self.add_layer)
        layer_menu.add_command(label="Duplicate Layer", command=self.duplicate_layer)
        layer_menu.add_command(label="Delete Layer  Del", command=self.delete_layer)
        layer_menu.add_command(label="Merge Down  Ctrl+E", command=self.merge_down)
        layer_menu.add_command(label="Flatten Image", command=self.flatten_image)
        menubar.add_cascade(label="Layer", menu=layer_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo  Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="Redo  Ctrl+Y", command=self.redo)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        adjust_menu = tk.Menu(menubar, tearoff=0)
        adjust_menu.add_command(label="Levels...", command=self.levels_dialog)
        adjust_menu.add_command(label="Curves...", command=self.curves_dialog)
        adjust_menu.add_command(label="Hue/Saturation...", command=self.hue_saturation_dialog)
        menubar.add_cascade(label="Adjust", menu=adjust_menu)

        filter_menu = tk.Menu(menubar, tearoff=0)
        filter_menu.add_command(label="Grayscale", command=lambda: self.apply_filter("grayscale"))
        filter_menu.add_command(label="Sepia", command=lambda: self.apply_filter("sepia"))
        filter_menu.add_command(label="Invert", command=lambda: self.apply_filter("invert"))
        filter_menu.add_separator()
        filter_menu.add_command(label="Blur", command=lambda: self.apply_filter("blur"))
        filter_menu.add_command(label="Sharpen", command=lambda: self.apply_filter("sharpen"))
        filter_menu.add_command(label="Edge Enhance", command=lambda: self.apply_filter("edge"))
        filter_menu.add_command(label="Emboss", command=lambda: self.apply_filter("emboss"))
        filter_menu.add_command(label="Detail", command=lambda: self.apply_filter("detail"))
        filter_menu.add_separator()
        filter_menu.add_command(label="Black & White High Contrast", command=lambda: self.apply_filter("bw_contrast"))
        menubar.add_cascade(label="Filters", menu=filter_menu)

        ai_menu = tk.Menu(menubar, tearoff=0)
        ai_menu.add_command(label="Remove Background (AI)  Ctrl+B", command=self.ai_remove_background)
        ai_menu.add_command(label="Upscale 2x (AI)", command=self.ai_upscale)
        ai_menu.add_command(label="Auto Enhance (AI)", command=self.ai_auto_enhance)
        ai_menu.add_command(label="Denoise (AI)", command=self.ai_denoise)
        menubar.add_cascade(label="AI", menu=ai_menu)

        self.root.config(menu=menubar)

        self.main_frame = tk.Frame(self.root, bg="#2b2b2b")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # LEFT - Tools
        self.toolbar = tk.Frame(self.main_frame, bg="#3c3c3c", width=95)
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y)
        self.toolbar.pack_propagate(False)
        tk.Label(self.toolbar, text="TOOLS", bg="#3c3c3c", fg="#aaaaaa", font=("Segoe UI", 8, "bold")).pack(pady=(15,10))

        tools = [("Select", "select"), ("Crop", "crop"), ("Brush", "brush"), ("Eraser", "eraser"), ("Text", "text"), ("Wand", "wand"), ("Clone", "clone")]
        for label, mode in tools:
            b = tk.Radiobutton(self.toolbar, text=label, variable=self.current_tool, value=mode, bg="#3c3c3c", fg="white", selectcolor="#555555", indicatoron=0, width=10, command=self.on_tool_change)
            b.pack(pady=2, padx=5)

        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=8)
        self.make_tool_button("Open", self.open_image)
        self.make_tool_button("Crop Apply", self.apply_crop)
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=8)
        self.make_tool_button("90 Left", lambda: self.rotate_image(-90))
        self.make_tool_button("90 Right", lambda: self.rotate_image(90))
        self.make_tool_button("Flip H", lambda: self.flip_image("h"))
        self.make_tool_button("Flip V", lambda: self.flip_image("v"))
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=8)
        self.make_tool_button("New Layer", self.add_layer)
        self.make_tool_button("Merge Down", self.merge_down)
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=6)
        self.make_tool_button("RM Background", self.ai_remove_background)
        self.make_tool_button("Blur", lambda: self.apply_filter("blur"))
        self.make_tool_button("Gray", lambda: self.apply_filter("grayscale"))
        self.make_tool_button("Wand Sel", lambda: self.current_tool.set("wand"))
        self.make_tool_button("Clone", lambda: self.current_tool.set("clone"))
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=6)
        self.make_tool_button("Zoom In", lambda: self.zoom_step(1.25))
        self.make_tool_button("Zoom Out", lambda: self.zoom_step(0.8))
        self.make_tool_button("Reset Zoom", self.reset_zoom)
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=6)
        self.make_tool_button("Undo", self.undo)
        self.make_tool_button("Redo", self.redo)

        # CENTER
        center_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(center_frame, bg="#1e1e1e", highlightthickness=0, cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_step(1.1))
        self.canvas.bind("<Button-5>", lambda e: self.zoom_step(0.9))
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click)

        self.status_var = tk.StringVar(value="Milestone 6 FIXED: Ready. Wand and Clone fixed.")
        status_bar = tk.Label(center_frame, textvariable=self.status_var, anchor="w", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 9), padx=10, pady=4)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # RIGHT - scrollable
        self.right_panel = tk.Frame(self.main_frame, bg="#2b2b2b", width=380)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_panel.pack_propagate(False)

        canvas_right = tk.Canvas(self.right_panel, bg="#2b2b2b", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.right_panel, orient="vertical", command=canvas_right.yview)
        self.scrollable_frame = tk.Frame(canvas_right, bg="#2b2b2b")
        self.scrollable_frame.bind("<Configure>", lambda e: canvas_right.configure(scrollregion=canvas_right.bbox("all")))
        canvas_right.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas_right.configure(yscrollcommand=scrollbar.set)
        canvas_right.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.setup_right_panels()

    def setup_right_panels(self):
        # Brush panel
        brush_frame = tk.LabelFrame(self.scrollable_frame, text="Brush / Eraser", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        brush_frame.pack(fill="x", padx=8, pady=6)

        tk.Label(brush_frame, text="Size:", bg="#2b2b2b", fg="#cccccc").pack(anchor="w")
        scale = tk.Scale(brush_frame, from_=1, to=100, orient="horizontal", variable=self.brush_size, bg="#2b2b2b", fg="white", highlightthickness=0, troughcolor="#555555")
        scale.pack(fill="x")

        color_row = tk.Frame(brush_frame, bg="#2b2b2b")
        color_row.pack(fill="x", pady=4)
        tk.Label(color_row, text="Color:", bg="#2b2b2b", fg="#cccccc").pack(side="left")
        self.color_preview = tk.Label(color_row, bg=self.brush_color, width=3, relief="sunken")
        self.color_preview.pack(side="left", padx=6)
        tk.Button(color_row, text="Pick", command=self.pick_color, bg="#4a4a4a", fg="white", font=("Segoe UI", 8)).pack(side="left")

        tk.Button(brush_frame, text="Add Text...", command=self.add_text_dialog, bg="#4a7a9a", fg="white").pack(fill="x", pady=6)

        # Wand controls
        wand_frame = tk.LabelFrame(self.scrollable_frame, text="Magic Wand", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        wand_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(wand_frame, text="Tolerance (0-100):", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8)).pack(anchor="w")
        tk.Scale(wand_frame, from_=0, to=100, orient="horizontal", variable=self.wand_tolerance, bg="#2b2b2b", fg="white", troughcolor="#555555", highlightthickness=0).pack(fill="x")
        tk.Checkbutton(wand_frame, text="Contiguous (flood fill)", variable=self.wand_contiguous, bg="#2b2b2b", fg="#cccccc", selectcolor="#3c3c3c").pack(anchor="w")
        tk.Label(wand_frame, text="Click image to select, then Delete", bg="#2b2b2b", fg="#aaaaaa", font=("Segoe UI", 7)).pack(anchor="w")
        btn_wand_row = tk.Frame(wand_frame, bg="#2b2b2b")
        btn_wand_row.pack(fill="x", pady=4)
        tk.Button(btn_wand_row, text="Delete Selected", command=lambda: self.apply_wand_delete(self._last_wand_mask) if self._last_wand_mask else None, bg="#9a4a4a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2)

        # Clone controls
        clone_frame = tk.LabelFrame(self.scrollable_frame, text="Clone Stamp (Alt+Click source)", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        clone_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(clone_frame, text="Alt+click to set source, then paint", bg="#2b2b2b", fg="#aaaaaa", font=("Segoe UI", 8)).pack(anchor="w")
        self.clone_label = tk.Label(clone_frame, text="Source: not set", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8))
        self.clone_label.pack(anchor="w")

        # Layers panel
        self.layers_frame = tk.LabelFrame(self.scrollable_frame, text="Layers", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        self.layers_frame.pack(fill="both", expand=False, padx=8, pady=6)
        self.layers_listbox = tk.Listbox(self.layers_frame, bg="#3c3c3c", fg="white", height=6, selectbackground="#5a5a5a")
        self.layers_listbox.pack(fill="x")
        self.layers_listbox.bind("<<ListboxSelect>>", self.on_layer_select)

        blend_row = tk.Frame(self.layers_frame, bg="#2b2b2b")
        blend_row.pack(fill="x", pady=4)
        tk.Label(blend_row, text="Blend:", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        self.blend_var = tk.StringVar(value="normal")
        blend_combo = ttk.Combobox(blend_row, textvariable=self.blend_var, values=["normal", "multiply", "screen", "overlay", "darken", "lighten"], width=10, state="readonly")
        blend_combo.pack(side="left", padx=4)
        blend_combo.bind("<<ComboboxSelected>>", self.on_blend_change)

        # Adjustments
        adj_frame = tk.LabelFrame(self.scrollable_frame, text="Adjustments", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        adj_frame.pack(fill="x", padx=8, pady=6)
        self.sliders = {}
        for name, label in [("brightness", "Brightness"), ("contrast", "Contrast"), ("saturation", "Saturation"), ("sharpness", "Sharpness")]:
            row = tk.Frame(adj_frame, bg="#2b2b2b")
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg="#2b2b2b", fg="#cccccc", width=10, anchor="w", font=("Segoe UI", 8)).pack(side="left")
            s = tk.Scale(row, from_=0.0, to=2.0, resolution=0.05, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", highlightthickness=0, length=150)
            s.set(1.0)
            s.pack(side="left", fill="x", expand=True)
            self.sliders[name] = s
        btn_row = tk.Frame(adj_frame, bg="#2b2b2b")
        btn_row.pack(fill="x", pady=4)
        tk.Button(btn_row, text="Apply", command=self.apply_adjustments, bg="#4a4a4a", fg="white").pack(side="left", padx=2)
        tk.Button(btn_row, text="Reset", command=self.reset_sliders, bg="#4a4a4a", fg="white").pack(side="left", padx=2)

        # Resize
        resize_frame = tk.LabelFrame(self.scrollable_frame, text="Resize", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        resize_frame.pack(fill="x", padx=8, pady=6)
        dim_row = tk.Frame(resize_frame, bg="#2b2b2b")
        dim_row.pack(fill="x")
        tk.Label(dim_row, text="W:", bg="#2b2b2b", fg="#cccccc").pack(side="left")
        self.width_entry = tk.Entry(dim_row, width=6, bg="#3c3c3c", fg="white")
        self.width_entry.pack(side="left", padx=4)
        tk.Label(dim_row, text="H:", bg="#2b2b2b", fg="#cccccc").pack(side="left")
        self.height_entry = tk.Entry(dim_row, width=6, bg="#3c3c3c", fg="white")
        self.height_entry.pack(side="left", padx=4)
        tk.Checkbutton(resize_frame, text="Lock aspect", variable=self.lock_aspect, bg="#2b2b2b", fg="#cccccc", selectcolor="#3c3c3c").pack(anchor="w", pady=2)
        tk.Button(resize_frame, text="Apply Resize", command=self.apply_resize, bg="#4a4a4a", fg="white").pack(fill="x", pady=4)

        # Zoom info
        zoom_frame = tk.LabelFrame(self.scrollable_frame, text="View", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        zoom_frame.pack(fill="x", padx=8, pady=6)
        self.zoom_label = tk.Label(zoom_frame, text="Zoom: 100% (Wheel=zoom, Middle-drag=pan)", bg="#2b2b2b", fg="#aaaaaa", font=("Segoe UI", 8))
        self.zoom_label.pack(anchor="w")

    def make_tool_button(self, text, command):
        btn = tk.Button(self.toolbar, text=text, command=command, bg="#4a4a4a", fg="white", font=("Segoe UI", 7), relief="flat", padx=4, pady=2)
        btn.pack(pady=1, padx=5, fill="x")

    def on_tool_change(self):
        tool = self.current_tool.get()
        self.status_var.set(f"Tool: {tool} | Zoom {int(self.zoom*100)}%")
        cursors = {"select": "arrow", "crop": "crosshair", "brush": "pencil", "eraser": "dotbox", "text": "xterm", "wand": "tcross", "clone": "crosshair"}
        self.canvas.config(cursor=cursors.get(tool, "crosshair"))

    def bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self.open_image())
        self.root.bind("<Control-s>", lambda e: self.save_as())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-l>", lambda e: self.add_layer())
        self.root.bind("<Control-e>", lambda e: self.merge_down())
        self.root.bind("<Control-b>", lambda e: self.ai_remove_background())
        self.root.bind("<Delete>", lambda e: self.delete_layer())

    def push_undo(self, action=""):
        if len(self.undo_stack) >= self.max_undo:
            self.undo_stack.pop(0)
        self.undo_stack.append(([l.copy() for l in self.layers], self.active_layer_idx, action))
        self.redo_stack.clear()

    def open_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
            self.original_path = path
            self.layers = [Layer("Background", img)]
            self.active_layer_idx = 0
            self.zoom = 1.0
            self.pan_x = self.pan_y = 0
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.refresh_layers_list()
            self.display_composite()
            self.update_resize_entries()
            self.status_var.set(f"Opened {os.path.basename(path)} | {img.size[0]}x{img.size[1]}")
        except Exception as e:
            messagebox.showerror("Open Error", str(e))

    def refresh_layers_list(self):
        self.layers_listbox.delete(0, tk.END)
        for i, l in enumerate(reversed(self.layers)):
            idx = len(self.layers)-1 - i
            sel = " <ACTIVE>" if idx == self.active_layer_idx else ""
            self.layers_listbox.insert(tk.END, f"{l.name}{sel} {'(hidden)' if not l.visible else ''}")
        if self.layers:
            rev_idx = len(self.layers)-1 - self.active_layer_idx
            self.layers_listbox.selection_clear(0, tk.END)
            self.layers_listbox.selection_set(rev_idx)

    def on_layer_select(self, e):
        sel = self.layers_listbox.curselection()
        if not sel:
            return
        rev_idx = sel[0]
        self.active_layer_idx = len(self.layers)-1 - rev_idx
        if self.layers:
            self.blend_var.set(self.layers[self.active_layer_idx].blend_mode)
        self.display_composite()

    def on_blend_change(self, e):
        if not self.layers:
            return
        self.push_undo(f"Blend {self.blend_var.get()}")
        self.layers[self.active_layer_idx].blend_mode = self.blend_var.get()
        self.display_composite()

    def add_layer(self):
        if not self.layers:
            return
        w, h = self.layers[0].image.size
        new_img = Image.new("RGBA", (w, h), (0,0,0,0))
        self.push_undo("New layer")
        self.layers.append(Layer(f"Layer {len(self.layers)}", new_img))
        self.active_layer_idx = len(self.layers)-1
        self.refresh_layers_list()
        self.display_composite()

    def duplicate_layer(self):
        if not self.layers:
            return
        self.push_undo("Duplicate layer")
        dup = self.layers[self.active_layer_idx].copy()
        dup.name += " copy"
        self.layers.insert(self.active_layer_idx+1, dup)
        self.active_layer_idx += 1
        self.refresh_layers_list()
        self.display_composite()

    def delete_layer(self):
        if len(self.layers) <= 1:
            messagebox.showinfo("Layers", "Cannot delete last layer")
            return
        self.push_undo("Delete layer")
        del self.layers[self.active_layer_idx]
        self.active_layer_idx = max(0, self.active_layer_idx-1)
        self.refresh_layers_list()
        self.display_composite()

    def merge_down(self):
        if self.active_layer_idx == 0 or not self.layers:
            return
        self.push_undo("Merge down")
        lower = self.layers[self.active_layer_idx-1]
        upper = self.layers[self.active_layer_idx]
        lower.image = self.composite_two(lower, upper)
        del self.layers[self.active_layer_idx]
        self.active_layer_idx -= 1
        self.refresh_layers_list()
        self.display_composite()

    def flatten_image(self):
        if len(self.layers) <= 1:
            return
        self.push_undo("Flatten")
        base = None
        for l in self.layers:
            if not l.visible:
                continue
            if base is None:
                base = l.image.copy()
            else:
                base = self.composite_two(Layer("tmp", base), l)
        self.layers = [Layer("Background", base.copy())]
        self.active_layer_idx = 0
        self.refresh_layers_list()
        self.display_composite()

    def composite_two(self, lower_layer, upper_layer):
        lower = lower_layer.image
        upper = upper_layer.image
        if upper.size != lower.size:
            upper = upper.resize(lower.size, Image.LANCZOS)
        if upper.mode != "RGBA":
            upper = upper.convert("RGBA")
        if lower.mode != "RGBA":
            lower = lower.convert("RGBA")
        mode = getattr(upper_layer, 'blend_mode', 'normal')
        if mode == "normal":
            blended_rgb = upper
        else:
            lower_rgb = lower.convert("RGB")
            upper_rgb = upper.convert("RGB")
            if mode == "multiply":
                blended = ImageChops.multiply(lower_rgb, upper_rgb)
            elif mode == "screen":
                blended = ImageChops.screen(lower_rgb, upper_rgb)
            elif mode == "darken":
                blended = ImageChops.darker(lower_rgb, upper_rgb)
            elif mode == "lighten":
                blended = ImageChops.lighter(lower_rgb, upper_rgb)
            else:
                blended = Image.blend(lower_rgb, upper_rgb, 0.5)
            blended = blended.convert("RGBA")
            blended.putalpha(upper.split()[3])
            blended_rgb = blended
        if upper_layer.opacity < 1.0:
            alpha = blended_rgb.split()[3]
            alpha = alpha.point(lambda p: int(p * upper_layer.opacity))
            blended_rgb.putalpha(alpha)
        result = Image.alpha_composite(lower, blended_rgb)
        return result

    def get_composite(self):
        if not self.layers:
            return None
        base = None
        for l in self.layers:
            if not l.visible:
                continue
            if base is None:
                base = l.image.copy()
            else:
                base = self.composite_two(Layer("base", base), l)
        return base

    def display_composite(self):
        comp = self.get_composite()
        if comp is None:
            return
        self.composited_image = comp
        w, h = comp.size
        disp_w = int(w * self.zoom)
        disp_h = int(h * self.zoom)
        if disp_w < 1: disp_w = 1
        if disp_h < 1: disp_h = 1
        disp_img = comp.resize((disp_w, disp_h), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(disp_img)
        self.canvas.delete("all")
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10: cw = 800
        if ch < 10: ch = 600
        x = cw//2 + self.pan_x - disp_w//2
        y = ch//2 + self.pan_y - disp_h//2
        self.image_offset = (x, y)
        self.display_size = (disp_w, disp_h)
        self.canvas.create_image(x, y, anchor="nw", image=self.photo)
        self.zoom_label.config(text=f"Zoom: {int(self.zoom*100)}% | {w}x{h} -> {disp_w}x{disp_h} | Tool: {self.current_tool.get()}")
        self.update_resize_entries()

    def update_resize_entries(self):
        if self.composited_image is None:
            return
        w, h = self.composited_image.size
        self.width_entry.delete(0, tk.END)
        self.width_entry.insert(0, str(w))
        self.height_entry.delete(0, tk.END)
        self.height_entry.insert(0, str(h))

    def rotate_image(self, angle):
        if not self.layers:
            return
        self.push_undo(f"Rotate {angle}")
        self.layers[self.active_layer_idx].image = self.layers[self.active_layer_idx].image.rotate(angle, expand=True, resample=Image.BICUBIC)
        self.display_composite()
        self.update_resize_entries()

    def flip_image(self, direction):
        if not self.layers:
            return
        self.push_undo(f"Flip {direction}")
        layer = self.layers[self.active_layer_idx]
        layer.image = ImageOps.mirror(layer.image) if direction=="h" else ImageOps.flip(layer.image)
        self.display_composite()

    def apply_filter(self, name):
        if not self.layers:
            return
        self.push_undo(f"Filter {name}")
        img = self.layers[self.active_layer_idx].image
        has_alpha = img.mode == "RGBA"
        if has_alpha:
            alpha = img.split()[3]
            work = img.convert("RGB")
        else:
            work = img
            alpha = None
        try:
            if name == "grayscale":
                work = ImageOps.grayscale(work).convert("RGB")
            elif name == "sepia":
                work = work.convert("RGB")
                w,h = work.size
                for y in range(h):
                    for x in range(w):
                        r,g,b = work.getpixel((x,y))
                        tr = int(0.393*r + 0.769*g + 0.189*b)
                        tg = int(0.349*r + 0.686*g + 0.168*b)
                        tb = int(0.272*r + 0.534*g + 0.131*b)
                        work.putpixel((x,y), (min(255,tr), min(255,tg), min(255,tb)))
            elif name == "invert":
                work = ImageOps.invert(work)
            elif name == "blur":
                work = work.filter(ImageFilter.GaussianBlur(radius=4))
            elif name == "sharpen":
                work = work.filter(ImageFilter.SHARPEN)
                work = work.filter(ImageFilter.SHARPEN)
            elif name == "edge":
                work = work.filter(ImageFilter.EDGE_ENHANCE_MORE)
            elif name == "emboss":
                work = work.filter(ImageFilter.EMBOSS)
            elif name == "detail":
                work = work.filter(ImageFilter.DETAIL)
            elif name == "bw_contrast":
                work = ImageOps.grayscale(work)
                work = ImageOps.autocontrast(work, cutoff=2)
                work = work.convert("RGB")
            if has_alpha:
                work = work.convert("RGBA")
                work.putalpha(alpha)
            self.layers[self.active_layer_idx].image = work
            self.display_composite()
            self.status_var.set(f"Applied filter: {name}")
        except Exception as e:
            messagebox.showerror("Filter Error", str(e))

    def pick_color(self):
        c = colorchooser.askcolor(initialcolor=self.brush_color)
        if c[1]:
            self.brush_color = c[1]
            self.color_preview.config(bg=self.brush_color)

    def canvas_to_image_coords(self, cx, cy):
        if self.composited_image is None:
            return None
        ox, oy = self.image_offset
        dw, dh = self.display_size
        if not (ox <= cx <= ox+dw and oy <= cy <= oy+dh):
            return None
        rx = (cx - ox) / dw
        ry = (cy - oy) / dh
        iw, ih = self.layers[self.active_layer_idx].image.size if self.layers else self.composited_image.size
        ix = int(rx * iw)
        iy = int(ry * ih)
        return (ix, iy)

    def on_canvas_press(self, event):
        tool = self.current_tool.get()
        if tool == "crop":
            self.on_crop_press(event)
        elif tool in ("brush", "eraser"):
            self.on_brush_press(event)
        elif tool == "text":
            self.on_text_click(event)
        elif tool == "wand":
            self.on_wand_click(event)
        elif tool == "clone":
            coords = self.canvas_to_image_coords(event.x, event.y)
            if coords:
                if self.clone_source is None or (event.state & 0x0008):
                    self.set_clone_source(coords[0], coords[1])
                    if hasattr(self, 'clone_label') and self.clone_label:
                        self.clone_label.config(text=f"Source: {coords[0]},{coords[1]}")
                else:
                    self.on_brush_press(event)

    def on_canvas_drag(self, event):
        tool = self.current_tool.get()
        if tool == "crop":
            self.on_crop_drag(event)
        elif tool in ("brush", "eraser"):
            self.on_brush_drag(event)
        elif tool == "clone":
            self.on_clone_drag(event)

    def on_canvas_release(self, event):
        tool = self.current_tool.get()
        if tool == "crop":
            self.on_crop_release(event)
        elif tool in ("brush", "eraser"):
            self.on_brush_release(event)
        elif tool == "clone":
            self.on_brush_release(event)

    def on_brush_press(self, event):
        if not self.layers:
            return
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            return
        self.push_undo(f"{self.current_tool.get()} stroke")
        self.is_drawing = True
        self.brush_last_pos = coords
        self.draw_brush_line(coords, coords)

    def on_brush_drag(self, event):
        if not self.is_drawing or not self.layers:
            return
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            return
        self.draw_brush_line(self.brush_last_pos, coords)
        self.brush_last_pos = coords

    def on_brush_release(self, event):
        self.is_drawing = False
        self.brush_last_pos = None
        self.display_composite()

    def draw_brush_line(self, p1, p2):
        layer_img = self.layers[self.active_layer_idx].image
        if layer_img.mode != "RGBA":
            layer_img = layer_img.convert("RGBA")
            self.layers[self.active_layer_idx].image = layer_img
        draw = ImageDraw.Draw(layer_img)
        tool = self.current_tool.get()
        size = self.brush_size.get()
        if tool == "eraser":
            color = (0,0,0,0)
            draw.line([p1, p2], fill=color, width=size, joint="curve")
        else:
            hex_color = self.brush_color.lstrip("#")
            r = int(hex_color[0:2], 16); g = int(hex_color[2:4], 16); b = int(hex_color[4:6], 16)
            color = (r,g,b,255)
            draw.line([p1, p2], fill=color, width=size, joint="curve")
            draw.ellipse([p1[0]-size//2, p1[1]-size//2, p1[0]+size//2, p1[1]+size//2], fill=color)
        if tool == "eraser":
            alpha = layer_img.split()[3]
            alpha_draw = ImageDraw.Draw(alpha)
            alpha_draw.line([p1, p2], fill=0, width=size, joint="curve")
            alpha_draw.ellipse([p1[0]-size//2, p1[1]-size//2, p1[0]+size//2, p1[1]+size//2], fill=0)
            layer_img.putalpha(alpha)
        self.layers[self.active_layer_idx].image = layer_img
        self.display_composite()

    def on_text_click(self, event):
        self.add_text_dialog(prefill_pos=self.canvas_to_image_coords(event.x, event.y))

    def on_wand_click(self, event):
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None or not self.layers:
            return
        mask = self.magic_wand_select(coords[0], coords[1])
        if mask:
            self._last_wand_mask = mask
            cnt = self.count_mask_pixels(mask)
            self.status_var.set(f"Wand selected {cnt} pixels at {coords}. Press Delete Selected.")
            self.display_composite_with_mask(mask)

    def display_composite_with_mask(self, mask):
        comp = self.get_composite()
        if comp is None:
            return
        overlay = Image.new("RGBA", comp.size, (255,0,0,80))
        overlay_masked = Image.new("RGBA", comp.size, (0,0,0,0))
        overlay_masked.paste(overlay, mask=mask)
        combined = Image.alpha_composite(comp, overlay_masked)
        w,h = combined.size
        disp_w = int(w * self.zoom); disp_h = int(h * self.zoom)
        disp_img = combined.resize((disp_w, disp_h), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(disp_img)
        self.canvas.delete("all")
        cw = self.canvas.winfo_width(); ch = self.canvas.winfo_height()
        if cw < 10: cw = 800
        if ch < 10: ch = 600
        x = cw//2 + self.pan_x - disp_w//2; y = ch//2 + self.pan_y - disp_h//2
        self.image_offset = (x,y); self.display_size = (disp_w, disp_h)
        self.canvas.create_image(x,y, anchor="nw", image=self.photo)

    def magic_wand_select(self, img_x, img_y):
        if not self.layers:
            return None
        img = self.layers[self.active_layer_idx].image.convert("RGB")
        w,h = img.size
        if not (0 <= img_x < w and 0 <= img_y < h):
            return None
        target = img.getpixel((img_x, img_y))
        tol = self.wand_tolerance.get()
        contiguous = self.wand_contiguous.get()
        mask = Image.new("L", (w,h), 0)
        mask_pixels = mask.load()
        img_pixels = img.load()
        if contiguous:
            stack = [(img_x, img_y)]
            visited = set([(img_x, img_y)])
            while stack:
                x,y = stack.pop()
                r,g,b = img_pixels[x,y]
                dr = r - target[0]; dg = g - target[1]; db = b - target[2]
                dist = (dr*dr + dg*dg + db*db) ** 0.5
                if dist <= tol:
                    mask_pixels[x,y] = 255
                    for nx, ny in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):
                        if 0 <= nx < w and 0 <= ny < h and (nx,ny) not in visited:
                            visited.add((nx,ny))
                            stack.append((nx,ny))
        else:
            for y in range(h):
                for x in range(w):
                    r,g,b = img_pixels[x,y]
                    dr = r - target[0]; dg = g - target[1]; db = b - target[2]
                    dist = (dr*dr + dg*dg + db*db) ** 0.5
                    if dist <= tol:
                        mask_pixels[x,y] = 255
        return mask

    def apply_wand_delete(self, mask):
        if not self.layers or mask is None:
            return
        self.push_undo("Magic Wand Delete")
        layer_img = self.layers[self.active_layer_idx].image.convert("RGBA")
        alpha = layer_img.split()[3]
        new_alpha = ImageChops.multiply(alpha, ImageOps.invert(mask))
        layer_img.putalpha(new_alpha)
        self.layers[self.active_layer_idx].image = layer_img
        self.display_composite()

    def count_mask_pixels(self, mask):
        return sum(1 for p in mask.getdata() if p > 0)

    def set_clone_source(self, img_x, img_y):
        self.clone_source = (img_x, img_y)
        self.status_var.set(f"Clone source set at {img_x},{img_y}. Now paint to clone.")

    def on_clone_drag(self, event):
        if not self.layers or self.clone_source is None:
            return
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            return
        if self.brush_last_pos is None:
            self.brush_last_pos = coords
            self._clone_offset = (coords[0] - self.clone_source[0], coords[1] - self.clone_source[1])
        src_x = coords[0] - self._clone_offset[0]
        src_y = coords[1] - self._clone_offset[1]
        self.draw_clone_line(self.brush_last_pos, coords, (src_x, src_y))
        self.brush_last_pos = coords

    def draw_clone_line(self, dest_p1, dest_p2, src_p):
        layer_img = self.layers[self.active_layer_idx].image.convert("RGBA")
        size = self.brush_size.get()
        x1,y1 = dest_p1; x2,y2 = dest_p2
        sx,sy = src_p
        dist = ((x2-x1)**2 + (y2-y1)**2) ** 0.5
        steps = max(1, int(dist / (size/2)) if size>0 else 1)
        for i in range(steps+1):
            t = i/steps if steps>0 else 0
            dx = int(x1 + (x2-x1)*t)
            dy = int(y1 + (y2-y1)*t)
            sdx = int(sx + (dx - x1))
            sdy = int(sy + (dy - y1))
            w,h = layer_img.size
            if 0 <= sdx < w and 0 <= sdy < h:
                src_box = (max(0,sdx-size//2), max(0,sdy-size//2), min(w,sdx+size//2), min(h,sdy+size//2))
                patch = layer_img.crop(src_box)
                dest_box = (dx-size//2, dy-size//2)
                layer_img.paste(patch, dest_box, patch if patch.mode=='RGBA' else None)
        self.layers[self.active_layer_idx].image = layer_img
        self.display_composite()

    def add_text_dialog(self, prefill_pos=None):
        if not self.layers:
            messagebox.showinfo("Text", "Open an image first")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Add Text")
        dialog.geometry("400x280")
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text="Text:").pack(anchor="w", padx=10, pady=(10,0))
        text_entry = tk.Entry(dialog, font=("Segoe UI", 12))
        text_entry.pack(fill="x", padx=10, pady=4)
        text_entry.insert(0, "Hello Tola!")
        text_entry.focus()
        size_row = tk.Frame(dialog)
        size_row.pack(fill="x", padx=10, pady=4)
        tk.Label(size_row, text="Size:").pack(side="left")
        size_var = tk.IntVar(value=40)
        tk.Scale(size_row, from_=10, to=200, orient="horizontal", variable=size_var).pack(side="left", fill="x", expand=True, padx=6)
        color_row = tk.Frame(dialog)
        color_row.pack(fill="x", padx=10, pady=4)
        tk.Label(color_row, text="Color:").pack(side="left")
        color_var = tk.StringVar(value=self.brush_color)
        preview = tk.Label(color_row, bg=color_var.get(), width=3, relief="sunken")
        preview.pack(side="left", padx=6)
        def pick():
            c = colorchooser.askcolor(initialcolor=color_var.get())
            if c[1]:
                color_var.set(c[1])
                preview.config(bg=c[1])
        tk.Button(color_row, text="Pick", command=pick).pack(side="left")
        pos_row = tk.Frame(dialog)
        pos_row.pack(fill="x", padx=10, pady=4)
        tk.Label(pos_row, text="Position X Y (0,0 = center):").pack(anchor="w")
        xy_row = tk.Frame(pos_row)
        xy_row.pack(fill="x")
        x_var = tk.StringVar(value=str(prefill_pos[0]) if prefill_pos else "0")
        y_var = tk.StringVar(value=str(prefill_pos[1]) if prefill_pos else "0")
        tk.Entry(xy_row, textvariable=x_var, width=8).pack(side="left", padx=2)
        tk.Entry(xy_row, textvariable=y_var, width=8).pack(side="left", padx=2)
        def do_add():
            txt = text_entry.get()
            if not txt:
                return
            try:
                sz = size_var.get()
                col = color_var.get()
                hex_c = col.lstrip("#")
                r = int(hex_c[0:2], 16); g = int(hex_c[2:4], 16); b = int(hex_c[4:6], 16)
                self.push_undo(f"Add text '{txt}'")
                img = self.layers[self.active_layer_idx].image
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("arial.ttf", sz)
                except:
                    font = ImageFont.load_default()
                try:
                    px = int(x_var.get()); py = int(y_var.get())
                except:
                    px = py = 0
                if px == 0 and py == 0:
                    iw, ih = img.size
                    try:
                        bbox = draw.textbbox((0,0), txt, font=font)
                        tw = bbox[2]-bbox[0]; th = bbox[3]-bbox[1]
                    except:
                        tw, th = sz*len(txt)//2, sz
                    px = (iw - tw)//2
                    py = (ih - th)//2
                draw.text((px, py), txt, fill=(r,g,b,255), font=font)
                self.layers[self.active_layer_idx].image = img
                self.display_composite()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Text Error", str(e))
        tk.Button(dialog, text="Add to Image", command=do_add, bg="#4a7a9a", fg="white", font=("Segoe UI", 10, "bold")).pack(pady=12)

    def zoom_step(self, factor):
        self.zoom *= factor
        self.zoom = max(0.05, min(20.0, self.zoom))
        self.display_composite()

    def reset_zoom(self):
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0
        self.display_composite()

    def on_mouse_wheel(self, event):
        if event.delta > 0:
            self.zoom_step(1.1)
        else:
            self.zoom_step(0.9)

    def on_pan_start(self, event):
        self.pan_start = (event.x - self.pan_x, event.y - self.pan_y)

    def on_pan_drag(self, event):
        if self.pan_start is None:
            return
        self.pan_x = event.x - self.pan_start[0]
        self.pan_y = event.y - self.pan_start[1]
        self.display_composite()

    def on_right_click(self, event):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Zoom In", command=lambda: self.zoom_step(1.25))
        menu.add_command(label="Zoom Out", command=lambda: self.zoom_step(0.8))
        menu.add_command(label="Reset Zoom (100%)", command=self.reset_zoom)
        menu.add_separator()
        menu.add_command(label="Add Text Here", command=lambda: self.add_text_dialog(prefill_pos=self.canvas_to_image_coords(event.x, event.y)))
        menu.tk_popup(event.x_root, event.y_root)

    def toggle_crop_mode(self):
        self.current_tool.set("crop" if self.current_tool.get() != "crop" else "select")
        self.on_tool_change()

    def on_crop_press(self, event):
        if self.current_tool.get() != "crop" or not self.layers:
            return
        self.crop_start = (event.x, event.y)
        if self.crop_rect_id:
            self.canvas.delete(self.crop_rect_id)

    def on_crop_drag(self, event):
        if not self.crop_start or self.current_tool.get() != "crop":
            return
        if self.crop_rect_id:
            self.canvas.delete(self.crop_rect_id)
        x0,y0 = self.crop_start
        x1,y1 = event.x, event.y
        self.crop_rect_id = self.canvas.create_rectangle(x0,y0,x1,y1, outline="#00ff00", width=2, dash=(4,4))

    def on_crop_release(self, event):
        if not self.crop_start or self.current_tool.get() != "crop":
            return
        x0,y0 = self.crop_start
        x1,y1 = event.x, event.y
        self.crop_coords = (min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1))
        self.crop_start = None

    def apply_crop(self):
        if not self.crop_coords or not self.layers:
            messagebox.showinfo("Crop", "Draw a crop box first (Crop tool, drag on image)")
            return
        try:
            x0,y0,x1,y1 = self.crop_coords
            ox, oy = self.image_offset
            dw, dh = self.display_size
            x0 = max(ox, min(ox+dw, x0)); x1 = max(ox, min(ox+dw, x1))
            y0 = max(oy, min(oy+dh, y0)); y1 = max(oy, min(oy+dh, y1))
            rx0 = (x0-ox)/dw; ry0 = (y0-oy)/dh
            rx1 = (x1-ox)/dw; ry1 = (y1-oy)/dh
            self.push_undo("Crop")
            for layer in self.layers:
                iw, ih = layer.image.size
                ix0 = int(rx0*iw); iy0 = int(ry0*ih)
                ix1 = int(rx1*iw); iy1 = int(ry1*ih)
                ix0, ix1 = max(0, min(ix0,ix1)), min(iw, max(ix0,ix1))
                iy0, iy1 = max(0, min(iy0,iy1)), min(ih, max(iy0,iy1))
                if ix1-ix0 > 5 and iy1-iy0 > 5:
                    layer.image = layer.image.crop((ix0,iy0,ix1,iy1))
            self.crop_coords = None
            if self.crop_rect_id:
                self.canvas.delete(self.crop_rect_id)
                self.crop_rect_id = None
            self.display_composite()
            self.update_resize_entries()
        except Exception as e:
            messagebox.showerror("Crop Error", str(e))

    def apply_adjustments(self):
        if not self.layers:
            return
        self.push_undo(f"Adjust {self.layers[self.active_layer_idx].name}")
        img = self.layers[self.active_layer_idx].image
        try:
            b = self.sliders["brightness"].get()
            c = self.sliders["contrast"].get()
            s = self.sliders["saturation"].get()
            sh = self.sliders["sharpness"].get()
            if b != 1.0:
                img = ImageEnhance.Brightness(img).enhance(b)
            if c != 1.0:
                img = ImageEnhance.Contrast(img).enhance(c)
            if s != 1.0:
                img = ImageEnhance.Color(img).enhance(s)
            if sh != 1.0:
                img = ImageEnhance.Sharpness(img).enhance(sh)
            self.layers[self.active_layer_idx].image = img
            self.display_composite()
        except Exception as e:
            messagebox.showerror("Adjustment Error", str(e))

    def reset_sliders(self):
        for scale in self.sliders.values():
            scale.set(1.0)

    def apply_resize(self):
        if not self.layers or self.composited_image is None:
            return
        try:
            new_w = int(self.width_entry.get().strip())
            new_h = int(self.height_entry.get().strip())
            if self.lock_aspect.get():
                orig_w, orig_h = self.composited_image.size
                aspect = orig_w / orig_h
                if abs((new_w / new_h) - aspect) > 0.01:
                    new_h = int(new_w / aspect)
                    self.height_entry.delete(0, tk.END)
                    self.height_entry.insert(0, str(new_h))
            self.push_undo(f"Resize to {new_w}x{new_h}")
            for layer in self.layers:
                layer.image = layer.image.resize((new_w, new_h), Image.LANCZOS)
            self.display_composite()
            self.update_resize_entries()
        except Exception as e:
            messagebox.showerror("Resize Error", str(e))

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(([l.copy() for l in self.layers], self.active_layer_idx, "Redo"))
        layers_copy, active_idx, action = self.undo_stack.pop()
        self.layers = layers_copy
        self.active_layer_idx = min(active_idx, len(self.layers)-1)
        self.refresh_layers_list()
        self.display_composite()
        self.update_resize_entries()

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(([l.copy() for l in self.layers], self.active_layer_idx, "Undo"))
        layers_copy, active_idx, action = self.redo_stack.pop()
        self.layers = layers_copy
        self.active_layer_idx = min(active_idx, len(self.layers)-1)
        self.refresh_layers_list()
        self.display_composite()
        self.update_resize_entries()

    def reset_image(self):
        if not self.layers or not self.original_path:
            return
        if not messagebox.askyesno("Reset", "Reset to original? Remove extra layers?"):
            return
        try:
            img = Image.open(self.original_path).convert("RGBA")
            self.push_undo("Reset to original")
            self.layers = [Layer("Background", img, True, 1.0)]
            self.active_layer_idx = 0
            self.refresh_layers_list()
            self.display_composite()
            self.update_resize_entries()
        except Exception as e:
            messagebox.showerror("Reset Error", str(e))

    def save_as(self):
        if self.composited_image is None:
            messagebox.showinfo("Save", "No image")
            return
        initial = "edited_image.png"
        if self.original_path:
            base, ext = os.path.splitext(os.path.basename(self.original_path))
            initial = f"{base}_edited{ext or '.png'}"
        path = filedialog.asksaveasfilename(initialfile=initial, defaultextension=".png", filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("All", "*.*")])
        if not path:
            return
        try:
            save_img = self.composited_image
            if path.lower().endswith((".jpg", ".jpeg")) and save_img.mode == "RGBA":
                bg = Image.new("RGB", save_img.size, (255,255,255))
                bg.paste(save_img, mask=save_img.split()[3])
                save_img = bg
            save_img.save(path)
            self.status_var.set(f"Saved: {os.path.basename(path)} | {len(self.layers)} layers flattened")
            messagebox.showinfo("Saved", f"Saved composite to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def levels_dialog(self):
        if not self.layers:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Levels")
        dialog.geometry("420x350")
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text="Adjust Levels", font=("Segoe UI", 10, "bold")).pack(pady=8)
        shadows = tk.IntVar(value=0)
        mid = tk.DoubleVar(value=1.0)
        highlights = tk.IntVar(value=255)
        def make_row(label, var, from_, to_, res=None):
            row = tk.Frame(dialog)
            row.pack(fill="x", padx=10, pady=4)
            tk.Label(row, text=label, width=12, anchor="w").pack(side="left")
            s = tk.Scale(row, from_=from_, to=to_, orient="horizontal", variable=var, length=250)
            if res: s.config(resolution=res)
            s.pack(side="left", fill="x", expand=True)
            return s
        make_row("Shadows", shadows, 0, 100)
        make_row("Mid (Gamma)", mid, 0.1, 3.0, 0.05)
        make_row("Highlights", highlights, 155, 255)
        preview = tk.BooleanVar(value=True)
        tk.Checkbutton(dialog, text="Live Preview", variable=preview).pack()
        original = self.layers[self.active_layer_idx].image.copy()
        def apply_preview(*args):
            if not preview.get():
                return
            img = original.copy()
            s = shadows.get(); m = mid.get(); h = highlights.get()
            def levels_map(p):
                if h <= s:
                    return p
                p2 = (p - s) * 255.0 / max(1, h - s)
                p2 = max(0, min(255, p2))
                p2 = 255 * ((p2/255.0) ** (1.0/m)) if m !=0 else p2
                return int(p2)
            if img.mode == "RGBA":
                r,g,b,a = img.split()
                r = r.point(levels_map); g = g.point(levels_map); b = b.point(levels_map)
                img = Image.merge("RGBA", (r,g,b,a))
            else:
                img = img.point(levels_map)
            self.layers[self.active_layer_idx].image = img
            self.display_composite()
        shadows.trace_add("write", lambda *a: apply_preview())
        mid.trace_add("write", lambda *a: apply_preview())
        highlights.trace_add("write", lambda *a: apply_preview())
        def on_ok():
            dialog.destroy()
        def on_cancel():
            self.layers[self.active_layer_idx].image = original
            self.display_composite()
            dialog.destroy()
        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=12)
        tk.Button(btn_row, text="Cancel", command=on_cancel, width=10).pack(side="left", padx=6)
        tk.Button(btn_row, text="OK", command=on_ok, bg="#4a7a9a", fg="white", width=10).pack(side="left", padx=6)

    def curves_dialog(self):
        if not self.layers:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Curves")
        dialog.geometry("380x280")
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text="Curves - S-Curve contrast", font=("Segoe UI", 10, "bold")).pack(pady=6)
        curve_strength = tk.DoubleVar(value=0.0)
        tk.Label(dialog, text=" -1 = Flat, 0 = Normal, +1 = Strong").pack()
        tk.Scale(dialog, from_=-1.0, to=1.0, resolution=0.05, orient="horizontal", variable=curve_strength, length=300).pack(pady=8)
        original = self.layers[self.active_layer_idx].image.copy()
        def apply_curve(*args):
            img = original.copy()
            s = curve_strength.get()
            def curve_map(p):
                x = p/255.0
                x2 = x + s * 0.5 * math.sin(math.pi * (x-0.5))
                x2 = max(0, min(1, x2))
                return int(x2*255)
            if img.mode == "RGBA":
                r,g,b,a = img.split()
                r = r.point(curve_map); g = g.point(curve_map); b = b.point(curve_map)
                img = Image.merge("RGBA", (r,g,b,a))
            else:
                img = img.point(curve_map)
            self.layers[self.active_layer_idx].image = img
            self.display_composite()
        curve_strength.trace_add("write", lambda *a: apply_curve())
        def on_ok(): dialog.destroy()
        def on_cancel():
            self.layers[self.active_layer_idx].image = original
            self.display_composite()
            dialog.destroy()
        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=12)
        tk.Button(btn_row, text="Cancel", command=on_cancel).pack(side="left", padx=6)
        tk.Button(btn_row, text="OK", command=on_ok, bg="#4a7a9a", fg="white").pack(side="left", padx=6)

    def hue_saturation_dialog(self):
        if not self.layers:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Hue / Saturation")
        dialog.geometry("380x300")
        dialog.transient(self.root)
        dialog.grab_set()
        hue = tk.IntVar(value=0)
        sat = tk.DoubleVar(value=1.0)
        tk.Label(dialog, text="Hue Shift").pack(anchor="w", padx=10)
        tk.Scale(dialog, from_=-180, to=180, orient="horizontal", variable=hue, length=300).pack()
        tk.Label(dialog, text="Saturation").pack(anchor="w", padx=10)
        tk.Scale(dialog, from_=0.0, to=3.0, resolution=0.05, orient="horizontal", variable=sat, length=300).pack()
        original = self.layers[self.active_layer_idx].image.copy()
        def apply_hs(*args):
            img = original.copy().convert("RGBA")
            h_shift = hue.get()
            s_factor = sat.get()
            if s_factor != 1.0:
                img = ImageEnhance.Color(img).enhance(s_factor)
            if h_shift != 0:
                import colorsys
                rgb = img.convert("RGB")
                pixels = list(rgb.getdata())
                new_pixels = []
                shift = h_shift / 360.0
                for r,g,b in pixels:
                    hr, hg, hb = r/255.0, g/255.0, b/255.0
                    h_val, s_val, v_val = colorsys.rgb_to_hsv(hr,hg,hb)
                    h_val = (h_val + shift) % 1.0
                    nr, ng, nb = colorsys.hsv_to_rgb(h_val, s_val, v_val)
                    new_pixels.append((int(nr*255), int(ng*255), int(nb*255)))
                rgb.putdata(new_pixels)
                r_a = img.split()[3]
                img = rgb.convert("RGBA")
                img.putalpha(r_a)
            self.layers[self.active_layer_idx].image = img
            self.display_composite()
        hue.trace_add("write", lambda *a: apply_hs())
        sat.trace_add("write", lambda *a: apply_hs())
        def on_ok(): dialog.destroy()
        def on_cancel():
            self.layers[self.active_layer_idx].image = original
            self.display_composite()
            dialog.destroy()
        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=10)
        tk.Button(btn_row, text="Cancel", command=on_cancel).pack(side="left", padx=4)
        tk.Button(btn_row, text="OK", command=on_ok, bg="#4a7a9a", fg="white").pack(side="left", padx=4)

    def ai_remove_background(self):
        if not self.layers:
            return
        if not REMBG_AVAILABLE:
            messagebox.showinfo("AI", "rembg not installed. pip install rembg")
            return
        try:
            self.push_undo("AI Remove BG")
            img = self.layers[self.active_layer_idx].image
            self.status_var.set("AI removing background...")
            self.root.update()
            result = rembg_remove(img)
            self.layers[self.active_layer_idx].image = result.convert("RGBA")
            self.display_composite()
            self.status_var.set("Background removed!")
        except Exception as e:
            messagebox.showerror("AI Error", str(e))

    def ai_upscale(self):
        if not self.layers:
            return
        self.push_undo("Upscale 2x")
        img = self.layers[self.active_layer_idx].image
        w,h = img.size
        self.layers[self.active_layer_idx].image = img.resize((w*2, h*2), Image.LANCZOS)
        self.display_composite()
        self.update_resize_entries()

    def ai_auto_enhance(self):
        if not self.layers:
            return
        self.push_undo("Auto Enhance")
        img = self.layers[self.active_layer_idx].image
        img = ImageOps.autocontrast(img, cutoff=1)
        img = ImageEnhance.Color(img).enhance(1.15)
        img = ImageEnhance.Sharpness(img).enhance(1.1)
        self.layers[self.active_layer_idx].image = img
        self.display_composite()

    def ai_denoise(self):
        if not self.layers:
            return
        self.push_undo("Denoise")
        img = self.layers[self.active_layer_idx].image
        img = img.filter(ImageFilter.MedianFilter(size=3))
        self.layers[self.active_layer_idx].image = img
        self.display_composite()

if __name__ == "__main__":
    root = tk.Tk()
    try:
        style = ttk.Style()
        style.theme_use("clam")
    except:
        pass
    app = ImageEditor(root)
    root.mainloop()
