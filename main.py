import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance, ImageOps, ImageFilter, ImageStat
import os

# --- Optional AI dependencies ---
try:
    from rembg import remove as rembg_remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    rembg_remove = None

class Layer:
    def __init__(self, name, image, visible=True, opacity=1.0):
        self.name = name
        self.image = image  # RGBA
        self.visible = visible
        self.opacity = opacity

    def copy(self):
        return Layer(self.name, self.image.copy(), self.visible, self.opacity)

class ImageEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("ImageEditor - Milestone 4 (AI Assisted)")
        self.root.geometry("1450x950")
        self.root.minsize(1250, 800)

        self.original_path = None
        self.layers = []
        self.active_layer_idx = 0
        self.composited_image = None
        self.photo = None
        self.zoom = 1.0

        self.undo_stack = []
        self.redo_stack = []
        self.max_undo = 20

        self.crop_mode = False
        self.crop_start = None
        self.crop_rect_id = None
        self.crop_coords = None
        self.image_offset = (0, 0)
        self.display_size = (0, 0)
        self.lock_aspect = tk.BooleanVar(value=True)

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

        ai_menu = tk.Menu(menubar, tearoff=0)
        ai_menu.add_command(label="Remove Background (AI)  Ctrl+B", command=self.ai_remove_background)
        ai_menu.add_command(label="Upscale 2x (AI)", command=self.ai_upscale)
        ai_menu.add_command(label="Auto Enhance (AI)", command=self.ai_auto_enhance)
        ai_menu.add_command(label="Denoise (AI)", command=self.ai_denoise)
        menubar.add_cascade(label="AI", menu=ai_menu)

        self.root.config(menu=menubar)

        self.main_frame = tk.Frame(self.root, bg="#2b2b2b")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # LEFT
        self.toolbar = tk.Frame(self.main_frame, bg="#3c3c3c", width=85)
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y)
        self.toolbar.pack_propagate(False)
        tk.Label(self.toolbar, text="TOOLS", bg="#3c3c3c", fg="#aaaaaa", font=("Segoe UI", 8, "bold")).pack(pady=(15,10))
        self.make_tool_button("Open", self.open_image)
        self.make_tool_button("Crop Mode", self.toggle_crop_mode)
        self.make_tool_button("Apply Crop", self.apply_crop)
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=8)
        self.make_tool_button("90 Left", lambda: self.rotate_image(-90))
        self.make_tool_button("90 Right", lambda: self.rotate_image(90))
        self.make_tool_button("Rotate...", self.rotate_custom_dialog)
        self.make_tool_button("Flip H", lambda: self.flip_image("h"))
        self.make_tool_button("Flip V", lambda: self.flip_image("v"))
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=8)
        self.make_tool_button("New Layer", self.add_layer)
        self.make_tool_button("Merge Down", self.merge_down)
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=6)
        self.make_tool_button("RM Background", self.ai_remove_background)
        self.make_tool_button("Upscale 2x", self.ai_upscale)
        self.make_tool_button("Auto Enhance", self.ai_auto_enhance)
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=6)
        self.make_tool_button("Undo", self.undo)
        self.make_tool_button("Redo", self.redo)

        # CENTER
        center_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(center_frame, bg="#1e1e1e", highlightthickness=0, cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.bind("<ButtonPress-1>", self.on_crop_press)
        self.canvas.bind("<B1-Motion>", self.on_crop_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_crop_release)
        self.status_var = tk.StringVar(value="Milestone 4: AI ready. Open image. Ctrl+B for Remove Background.")
        status_bar = tk.Label(center_frame, textvariable=self.status_var, anchor="w", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 9), padx=10, pady=4)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # RIGHT - scrollable area for panels
        self.right_panel = tk.Frame(self.main_frame, bg="#2b2b2b", width=360)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_panel.pack_propagate(False)

        # Canvas for scrolling right panels if screen small
        canvas_right = tk.Canvas(self.right_panel, bg="#2b2b2b", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.right_panel, orient="vertical", command=canvas_right.yview)
        self.scrollable_frame = tk.Frame(canvas_right, bg="#2b2b2b")
        self.scrollable_frame.bind("<Configure>", lambda e: canvas_right.configure(scrollregion=canvas_right.bbox("all")))
        canvas_right.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas_right.configure(yscrollcommand=scrollbar.set)
        canvas_right.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- LAYERS ---
        layers_frame = tk.LabelFrame(self.scrollable_frame, text="Layers", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=8)
        layers_frame.pack(fill=tk.X, padx=8, pady=8)
        list_row = tk.Frame(layers_frame, bg="#2b2b2b")
        list_row.pack(fill=tk.BOTH, expand=True)
        self.layers_listbox = tk.Listbox(list_row, bg="#3c3c3c", fg="white", selectbackground="#0e639c", height=6, font=("Segoe UI", 9), activestyle="none")
        self.layers_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.layers_listbox.bind("<<ListboxSelect>>", self.on_layer_select)
        sb = tk.Scrollbar(list_row, command=self.layers_listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.layers_listbox.config(yscrollcommand=sb.set)

        ctrl_row = tk.Frame(layers_frame, bg="#2b2b2b")
        ctrl_row.pack(fill=tk.X, pady=(8,4))
        tk.Button(ctrl_row, text="Toggle Visible", command=self.toggle_visibility, bg="#4a4a4a", fg="white", relief=tk.FLAT, font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=2)

        op_row = tk.Frame(layers_frame, bg="#2b2b2b")
        op_row.pack(fill=tk.X, pady=4)
        tk.Label(op_row, text="Opacity:", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.opacity_var = tk.DoubleVar(value=100)
        self.opacity_scale = tk.Scale(op_row, from_=0, to=100, orient=tk.HORIZONTAL, variable=self.opacity_var, bg="#2b2b2b", fg="#cccccc", highlightthickness=0, troughcolor="#444444", length=150, command=self.on_opacity_change)
        self.opacity_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        btn_row = tk.Frame(layers_frame, bg="#2b2b2b")
        btn_row.pack(fill=tk.X, pady=4)
        tk.Button(btn_row, text="New", command=self.add_layer, bg="#3c3c3c", fg="white", relief=tk.FLAT, width=5).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text="Dup", command=self.duplicate_layer, bg="#3c3c3c", fg="white", relief=tk.FLAT, width=5).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text="Del", command=self.delete_layer, bg="#5a2a2a", fg="white", relief=tk.FLAT, width=5).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_row, text="Merge", command=self.merge_down, bg="#3c3c3c", fg="white", relief=tk.FLAT, width=6).pack(side=tk.LEFT, padx=2)

        # --- AI TOOLS (NEW - Milestone 4) ---
        ai_frame = tk.LabelFrame(self.scrollable_frame, text="AI Tools (Milestone 4)", bg="#2b2b2b", fg="#00d4ff", font=("Segoe UI", 9, "bold"), padx=10, pady=8)
        ai_frame.pack(fill=tk.X, padx=8, pady=8)

        ai_status_text = "AI Ready" if REMBG_AVAILABLE else "Install rembg for BG Remove"
        tk.Label(ai_frame, text=f"Status: {ai_status_text}", bg="#2b2b2b", fg="#888888", font=("Segoe UI", 8, "italic")).pack(anchor="w")

        tk.Button(ai_frame, text="✂ Remove Background (AI) - Active Layer", command=self.ai_remove_background, bg="#6a1b9a", fg="white", relief=tk.FLAT, font=("Segoe UI", 9, "bold"), pady=6).pack(fill=tk.X, pady=4)
        tk.Label(ai_frame, text="Uses rembg if installed, else smart edge fallback. Result = transparent layer.", bg="#2b2b2b", fg="#777777", font=("Segoe UI", 7)).pack(anchor="w")

        row_ai = tk.Frame(ai_frame, bg="#2b2b2b")
        row_ai.pack(fill=tk.X, pady=4)
        tk.Button(row_ai, text="⬆ Upscale 2x", command=self.ai_upscale, bg="#0e639c", fg="white", relief=tk.FLAT, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(row_ai, text="✨ Auto Enhance", command=self.ai_auto_enhance, bg="#0e639c", fg="white", relief=tk.FLAT, width=14).pack(side=tk.LEFT, padx=2)

        row_ai2 = tk.Frame(ai_frame, bg="#2b2b2b")
        row_ai2.pack(fill=tk.X, pady=2)
        tk.Button(row_ai2, text="Denoise", command=self.ai_denoise, bg="#3c3c3c", fg="white", relief=tk.FLAT, width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(row_ai2, text="Smart Sharpen", command=self.ai_smart_sharpen, bg="#3c3c3c", fg="white", relief=tk.FLAT, width=14).pack(side=tk.LEFT, padx=2)

        # --- Adjustments ---
        adj_frame = tk.LabelFrame(self.scrollable_frame, text="Adjustments (Active Layer)", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=6)
        adj_frame.pack(fill=tk.X, padx=8, pady=4)
        self.sliders = {}
        for name, label in [("brightness", "Brightness"), ("contrast", "Contrast"), ("saturation", "Saturation"), ("sharpness", "Sharpness")]:
            row = tk.Frame(adj_frame, bg="#2b2b2b")
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label, bg="#2b2b2b", fg="#cccccc", width=12, anchor="w", font=("Segoe UI", 8)).pack(side=tk.LEFT)
            scale = tk.Scale(row, from_=0.0, to=2.0, resolution=0.05, orient=tk.HORIZONTAL, bg="#2b2b2b", fg="#cccccc", highlightthickness=0, troughcolor="#444444", length=140)
            scale.set(1.0)
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.sliders[name] = scale
        btn_row2 = tk.Frame(adj_frame, bg="#2b2b2b")
        btn_row2.pack(fill=tk.X, pady=(6,0))
        tk.Button(btn_row2, text="Apply to Layer", command=self.apply_adjustments, bg="#0e639c", fg="white", relief=tk.FLAT, padx=8, font=("Segoe UI", 8)).pack(side=tk.LEFT)
        tk.Button(btn_row2, text="Reset Sliders", command=self.reset_sliders, bg="#3c3c3c", fg="white", relief=tk.FLAT, padx=8, font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=4)

        # --- Resize ---
        resize_frame = tk.LabelFrame(self.scrollable_frame, text="Resize & Save", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=6)
        resize_frame.pack(fill=tk.X, padx=8, pady=4)
        self.size_info_var = tk.StringVar(value="No image")
        tk.Label(resize_frame, textvariable=self.size_info_var, bg="#2b2b2b", fg="#888888", font=("Segoe UI", 8)).pack(anchor="w")
        row_w = tk.Frame(resize_frame, bg="#2b2b2b")
        row_w.pack(fill=tk.X, pady=2)
        tk.Label(row_w, text="Width:", bg="#2b2b2b", fg="#cccccc", width=8, anchor="w", font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.width_entry = tk.Entry(row_w, width=10, bg="#3c3c3c", fg="white", insertbackground="white", font=("Segoe UI", 8))
        self.width_entry.pack(side=tk.LEFT)
        row_h = tk.Frame(resize_frame, bg="#2b2b2b")
        row_h.pack(fill=tk.X, pady=2)
        tk.Label(row_h, text="Height:", bg="#2b2b2b", fg="#cccccc", width=8, anchor="w", font=("Segoe UI", 8)).pack(side=tk.LEFT)
        self.height_entry = tk.Entry(row_h, width=10, bg="#3c3c3c", fg="white", insertbackground="white", font=("Segoe UI", 8))
        self.height_entry.pack(side=tk.LEFT)
        tk.Checkbutton(resize_frame, text="Lock aspect ratio", variable=self.lock_aspect, bg="#2b2b2b", fg="#cccccc", selectcolor="#3c3c3c", activebackground="#2b2b2b", font=("Segoe UI", 8)).pack(anchor="w", pady=2)
        tk.Button(resize_frame, text="Apply Resize to All Layers", command=self.apply_resize, bg="#0e639c", fg="white", relief=tk.FLAT, padx=10, pady=2, font=("Segoe UI", 8)).pack(fill=tk.X, pady=(6,2))
        tk.Button(resize_frame, text="Save As New File (Never Overwrites)", command=self.save_as, bg="#16825d", fg="white", relief=tk.FLAT, padx=10, pady=5, font=("Segoe UI", 8, "bold")).pack(fill=tk.X, pady=2)

        # --- History ---
        hist_frame = tk.LabelFrame(self.scrollable_frame, text="History", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        hist_frame.pack(fill=tk.BOTH, padx=8, pady=8, expand=False)
        self.history_listbox = tk.Listbox(hist_frame, bg="#252525", fg="#aaaaaa", height=8, font=("Segoe UI", 8))
        self.history_listbox.pack(fill=tk.BOTH, expand=True)
        self.history_listbox.insert(tk.END, "History: Open image to start")

    def make_tool_button(self, text, cmd):
        b = tk.Button(self.toolbar, text=text, command=cmd, bg="#4a4a4a", fg="white", relief=tk.FLAT, font=("Segoe UI", 9), padx=5, pady=5, width=14, wraplength=75)
        b.pack(pady=2, padx=5)

    def bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self.open_image())
        self.root.bind("<Control-s>", lambda e: self.save_as())
        self.root.bind("<Control-l>", lambda e: self.add_layer())
        self.root.bind("<Control-b>", lambda e: self.ai_remove_background())
        self.root.bind("<Control-e>", lambda e: self.merge_down())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Delete>", lambda e: self.delete_layer())

    def composite_layers(self):
        if not self.layers:
            return None
        base_w = max(l.image.width for l in self.layers)
        base_h = max(l.image.height for l in self.layers)
        composite = Image.new("RGBA", (base_w, base_h), (0,0,0,0))
        for layer in self.layers:
            if not layer.visible:
                continue
            l_img = layer.image if layer.image.mode=="RGBA" else layer.image.convert("RGBA")
            if layer.opacity < 1.0:
                alpha = l_img.split()[3]
                alpha = ImageEnhance.Brightness(alpha).enhance(layer.opacity)
                l_img = l_img.copy()
                l_img.putalpha(alpha)
            if l_img.size != composite.size:
                tmp = Image.new("RGBA", composite.size, (0,0,0,0))
                x = (composite.width - l_img.width)//2
                y = (composite.height - l_img.height)//2
                tmp.paste(l_img, (x,y), l_img)
                l_img = tmp
            composite = Image.alpha_composite(composite, l_img)
        return composite

    def push_undo(self, action="Action"):
        if not self.layers:
            return
        if len(self.undo_stack) >= self.max_undo:
            self.undo_stack.pop(0)
        self.undo_stack.append(([l.copy() for l in self.layers], self.active_layer_idx, action))
        self.redo_stack.clear()
        self.history_listbox.insert(tk.END, action)
        self.history_listbox.see(tk.END)
        self.status_var.set(f"{action} | Undo:{len(self.undo_stack)} Redo:{len(self.redo_stack)}")

    def refresh_layers_list(self):
        self.layers_listbox.delete(0, tk.END)
        for i in reversed(range(len(self.layers))):
            l = self.layers[i]
            vis = "O" if l.visible else "X"
            active = ">" if i == self.active_layer_idx else " "
            self.layers_listbox.insert(tk.END, f"{active} [{vis}] {l.name} {int(l.opacity*100)}%")
        if self.layers:
            rev_idx = len(self.layers)-1 - self.active_layer_idx
            self.layers_listbox.selection_clear(0, tk.END)
            self.layers_listbox.selection_set(rev_idx)
            self.opacity_var.set(self.layers[self.active_layer_idx].opacity*100)

    def on_layer_select(self, event):
        if not self.layers:
            return
        sel = self.layers_listbox.curselection()
        if not sel:
            return
        rev_idx = sel[0]
        real_idx = len(self.layers)-1 - rev_idx
        self.active_layer_idx = real_idx
        self.refresh_layers_list()
        self.display_composite()

    def open_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"), ("All", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path).convert("RGBA")
            self.original_path = path
            self.layers = [Layer("Background", img.copy(), True, 1.0)]
            self.active_layer_idx = 0
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.history_listbox.delete(0, tk.END)
            self.history_listbox.insert(tk.END, f"Opened {os.path.basename(path)}")
            self.reset_sliders()
            self.refresh_layers_list()
            self.display_composite()
            self.update_resize_entries()
        except Exception as e:
            messagebox.showerror("Open Error", str(e))

    def display_composite(self):
        self.composited_image = self.composite_layers()
        if self.composited_image is None:
            return
        self.canvas.delete("all")
        self.crop_rect_id = None
        self.crop_coords = None
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 50:
            cw = 900
            ch = 600
        img_w, img_h = self.composited_image.size
        scale = min(cw / img_w, ch / img_h, 1.0) * 0.92
        self.zoom = scale
        dw = int(img_w * scale)
        dh = int(img_h * scale)
        self.display_size = (dw, dh)
        display_img = self.composited_image.resize((dw, dh), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(display_img)
        x0 = (cw - dw) // 2
        y0 = (ch - dh) // 2
        self.image_offset = (x0, y0)
        self.canvas.create_image(x0, y0, anchor="nw", image=self.photo)
        self.size_info_var.set(f"{self.composited_image.width}x{self.composited_image.height}px | {len(self.layers)} layers | Active: {self.layers[self.active_layer_idx].name if self.layers else 'None'}")

    def update_resize_entries(self):
        if self.composited_image:
            self.width_entry.delete(0, tk.END)
            self.width_entry.insert(0, str(self.composited_image.width))
            self.height_entry.delete(0, tk.END)
            self.height_entry.insert(0, str(self.composited_image.height))

    def canvas_to_image_coords(self, cx, cy):
        ox, oy = self.image_offset
        dw, dh = self.display_size
        if dw == 0 or dh == 0 or self.composited_image is None:
            return None
        ix = (cx - ox) / self.zoom
        iy = (cy - oy) / self.zoom
        return (ix, iy)

    def add_layer(self):
        if not self.layers:
            messagebox.showinfo("Layers", "Open an image first.")
            return
        self.push_undo("Add Layer")
        w, h = self.composited_image.size
        transparent = Image.new("RGBA", (w, h), (0,0,0,0))
        name = f"Layer {len(self.layers)}"
        self.layers.append(Layer(name, transparent, True, 1.0))
        self.active_layer_idx = len(self.layers)-1
        self.refresh_layers_list()
        self.display_composite()

    def duplicate_layer(self):
        if not self.layers:
            return
        self.push_undo(f"Duplicate {self.layers[self.active_layer_idx].name}")
        src = self.layers[self.active_layer_idx]
        dup = Layer(f"{src.name} copy", src.image.copy(), src.visible, src.opacity)
        self.layers.insert(self.active_layer_idx+1, dup)
        self.active_layer_idx += 1
        self.refresh_layers_list()
        self.display_composite()

    def delete_layer(self):
        if not self.layers:
            return
        if len(self.layers) == 1:
            messagebox.showinfo("Layers", "Cannot delete last layer.")
            return
        if not messagebox.askyesno("Delete Layer", f"Delete {self.layers[self.active_layer_idx].name}?"):
            return
        self.push_undo(f"Delete {self.layers[self.active_layer_idx].name}")
        del self.layers[self.active_layer_idx]
        self.active_layer_idx = max(0, min(self.active_layer_idx, len(self.layers)-1))
        self.refresh_layers_list()
        self.display_composite()

    def toggle_visibility(self):
        if not self.layers:
            return
        self.layers[self.active_layer_idx].visible = not self.layers[self.active_layer_idx].visible
        self.refresh_layers_list()
        self.display_composite()

    def on_opacity_change(self, val):
        if not self.layers:
            return
        try:
            op = float(val)/100.0
            self.layers[self.active_layer_idx].opacity = op
            self.display_composite()
            self.refresh_layers_list()
        except:
            pass

    def merge_down(self):
        if not self.layers or len(self.layers) < 2 or self.active_layer_idx == 0:
            messagebox.showinfo("Merge Down", "Select a layer above Background.")
            return
        self.push_undo(f"Merge {self.layers[self.active_layer_idx].name} down")
        top_idx = self.active_layer_idx
        bottom_idx = top_idx - 1
        bottom = self.layers[bottom_idx]
        top = self.layers[top_idx]
        base = bottom.image.copy().convert("RGBA")
        top_img = top.image.convert("RGBA") if top.image.mode!="RGBA" else top.image
        if top.opacity < 1.0:
            tmp = top_img.copy()
            alpha = tmp.split()[3]
            alpha = ImageEnhance.Brightness(alpha).enhance(top.opacity)
            tmp.putalpha(alpha)
            top_img = tmp
        if top_img.size != base.size:
            tmp = Image.new("RGBA", base.size, (0,0,0,0))
            tmp.paste(top_img, (base.width-top_img.width)//2, (base.height-top_img.height)//2, top_img)
            top_img = tmp
        merged = Image.alpha_composite(base, top_img)
        bottom.image = merged
        del self.layers[top_idx]
        self.active_layer_idx = bottom_idx
        self.refresh_layers_list()
        self.display_composite()

    def flatten_image(self):
        if not self.layers:
            return
        if not messagebox.askyesno("Flatten", "Flatten all layers?"):
            return
        self.push_undo("Flatten Image")
        comp = self.composite_layers()
        self.layers = [Layer("Background", comp, True, 1.0)]
        self.active_layer_idx = 0
        self.refresh_layers_list()
        self.display_composite()

    # ---------- AI TOOLS ----------
    def ai_remove_background(self):
        if not self.layers:
            messagebox.showinfo("AI Remove BG", "Open an image first.")
            return
        layer = self.layers[self.active_layer_idx]
        self.status_var.set(f"AI: Removing background from {layer.name}... (may take 5-15s first time)")
        self.root.update_idletasks()
        self.push_undo(f"AI Remove BG {layer.name}")
        try:
            if REMBG_AVAILABLE:
                # rembg works on PIL Image
                # Convert layer image to RGBA bytes
                result = rembg_remove(layer.image)
                # rembg_remove returns RGBA with transparent BG
                layer.image = result
                self.display_composite()
                self.status_var.set(f"AI: Background removed from {layer.name} using rembg (AI model)")
            else:
                # Fallback: smart chroma / edge - make near-white transparent + grow
                # This is not true AI but gives visual result without dependency
                img = layer.image.convert("RGBA")
                # Simple heuristic: if image has distinct background, use alpha based on luminance variance
                # For demo, we use ImageOps to create mask: high tolerance white removal
                # Ask user to confirm fallback
                if not messagebox.askyesno("AI Dependency Missing",
                    "rembg not installed.\n\nTo get true AI background removal, run:\n\npip install rembg onnxruntime\n\nUse basic fallback (white background removal) for now?"):
                    # undo push
                    self.undo()
                    return
                # Fallback: remove white/very light background
                datas = img.getdata()
                new_data = []
                for item in datas:
                    # If pixel is very light and low saturation, make transparent
                    if item[0] > 230 and item[1] > 230 and item[2] > 230:
                        new_data.append((255, 255, 255, 0))
                    else:
                        new_data.append(item)
                img.putdata(new_data)
                layer.image = img
                self.display_composite()
                self.status_var.set("Fallback BG remove (white removal). Install rembg for AI model: pip install rembg onnxruntime")
                messagebox.showinfo("Fallback Used",
                    "Used basic white removal fallback.\n\nFor true AI:\n pip install rembg onnxruntime\nThen restart the editor.")
        except Exception as e:
            messagebox.showerror("AI Remove BG Error", str(e))
            self.status_var.set(f"AI BG Remove failed: {e}")

    def ai_upscale(self):
        if not self.layers:
            return
        self.push_undo(f"AI Upscale 2x {self.layers[self.active_layer_idx].name}")
        try:
            layer = self.layers[self.active_layer_idx]
            w, h = layer.image.size
            new_w, new_h = w*2, h*2
            if new_w > 8000 or new_h > 8000:
                if not messagebox.askyesno("Large Image", f"Upscaling to {new_w}x{new_h} is very large. Continue?"):
                    self.undo()
                    return
            self.status_var.set(f"Upscaling {layer.name} to {new_w}x{new_h}...")
            self.root.update_idletasks()
            # LANCZOS is high quality, acts as AI-lite upscaler. Real-ESRGAN could be plugged later.
            layer.image = layer.image.resize((new_w, new_h), Image.LANCZOS)
            # For all other layers, optionally upscale to match? For now, upscale all to keep composite aligned
            for i, l in enumerate(self.layers):
                if i != self.active_layer_idx:
                    l.image = l.image.resize((new_w, new_h), Image.LANCZOS)
            self.display_composite()
            self.update_resize_entries()
            self.status_var.set(f"Upscaled to {new_w}x{new_h} (LANCZOS). For Real-ESRGAN, install realesrgan.")
        except Exception as e:
            messagebox.showerror("Upscale Error", str(e))

    def ai_auto_enhance(self):
        if not self.layers:
            return
        self.push_undo(f"AI Auto Enhance {self.layers[self.active_layer_idx].name}")
        try:
            layer = self.layers[self.active_layer_idx]
            img = layer.image
            # Auto level: autocontrast + auto color balance approximation
            # 1. Autocontrast
            img_rgb = img.convert("RGB")
            # Use ImageOps.autocontrast
            auto_contrast = ImageOps.autocontrast(img_rgb, cutoff=2)
            # 2. Color balance - equalize
            # Estimate: enhance color
            auto_color = ImageEnhance.Color(auto_contrast).enhance(1.15)
            # 3. Slight brightness/contrast normalization based on stats
            stat = ImageStat.Stat(auto_color)
            # If mean too dark, brighten
            mean_brightness = sum(stat.mean[:3])/3
            if mean_brightness < 100:
                auto_color = ImageEnhance.Brightness(auto_color).enhance(1.1)
            # Convert back to RGBA preserving alpha
            if img.mode == "RGBA":
                alpha = img.split()[3]
                auto_rgba = auto_color.convert("RGBA")
                auto_rgba.putalpha(alpha)
                layer.image = auto_rgba
            else:
                layer.image = auto_color.convert("RGBA")
            self.display_composite()
            self.status_var.set(f"AI Auto Enhanced {layer.name}: autocontrast + color + brightness")
        except Exception as e:
            messagebox.showerror("Auto Enhance Error", str(e))

    def ai_denoise(self):
        if not self.layers:
            return
        self.push_undo(f"AI Denoise {self.layers[self.active_layer_idx].name}")
        try:
            layer = self.layers[self.active_layer_idx]
            # Median filter reduces noise
            layer.image = layer.image.filter(ImageFilter.MedianFilter(size=3))
            self.display_composite()
            self.status_var.set(f"Denoised {layer.name} (Median filter)")
        except Exception as e:
            messagebox.showerror("Denoise Error", str(e))

    def ai_smart_sharpen(self):
        if not self.layers:
            return
        self.push_undo(f"Smart Sharpen {self.layers[self.active_layer_idx].name}")
        try:
            layer = self.layers[self.active_layer_idx]
            # Unsharp mask = smart sharpen
            layer.image = layer.image.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
            self.display_composite()
            self.status_var.set(f"Smart Sharpened {layer.name}")
        except Exception as e:
            messagebox.showerror("Sharpen Error", str(e))

    # ---------- Other tools (crop, rotate, etc. same as M3) ----------
    def toggle_crop_mode(self):
        if not self.layers:
            messagebox.showinfo("Crop", "Open an image first.")
            return
        self.crop_mode = not self.crop_mode
        if self.crop_mode:
            self.status_var.set("CROP MODE: Drag > Apply Crop (ALL layers)")
            self.canvas.config(cursor="crosshair")
        else:
            self.status_var.set("Crop OFF")
            self.canvas.config(cursor="cross")
            if self.crop_rect_id:
                self.canvas.delete(self.crop_rect_id)
                self.crop_rect_id = None

    def on_crop_press(self, event):
        if not self.crop_mode or not self.layers:
            return
        self.crop_start = (event.x, event.y)
        if self.crop_rect_id:
            self.canvas.delete(self.crop_rect_id)
        self.crop_rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#00ff00", width=2, dash=(4,4))

    def on_crop_drag(self, event):
        if not self.crop_mode or not self.crop_start or self.crop_rect_id is None:
            return
        x0, y0 = self.crop_start
        self.canvas.coords(self.crop_rect_id, x0, y0, event.x, event.y)

    def on_crop_release(self, event):
        if not self.crop_mode or not self.crop_start:
            return
        x0, y0 = self.crop_start
        x1, y1 = event.x, event.y
        self.crop_coords = (min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1))

    def apply_crop(self):
        if not self.layers or self.crop_coords is None:
            messagebox.showinfo("Crop", "Drag a rectangle first.")
            return
        try:
            x0, y0, x1, y1 = self.crop_coords
            p0 = self.canvas_to_image_coords(x0, y0)
            p1 = self.canvas_to_image_coords(x1, y1)
            if p0 is None or p1 is None:
                return
            ix0, iy0 = p0
            ix1, iy1 = p1
            comp_w, comp_h = self.composited_image.size
            ix0 = max(0, min(comp_w, ix0))
            ix1 = max(0, min(comp_w, ix1))
            iy0 = max(0, min(comp_h, iy0))
            iy1 = max(0, min(comp_h, iy1))
            left, right = sorted([int(ix0), int(ix1)])
            top, bottom = sorted([int(iy0), int(iy1)])
            if right - left < 5 or bottom - top < 5:
                messagebox.showinfo("Crop", "Too small.")
                return
            self.push_undo(f"Crop to {right-left}x{bottom-top}")
            for layer in self.layers:
                layer.image = layer.image.crop((left, top, right, bottom))
            self.crop_mode = False
            self.canvas.config(cursor="cross")
            if self.crop_rect_id:
                self.canvas.delete(self.crop_rect_id)
            self.crop_coords = None
            self.display_composite()
            self.update_resize_entries()
        except Exception as e:
            messagebox.showerror("Crop Error", str(e))

    def rotate_image(self, angle):
        if not self.layers:
            return
        self.push_undo(f"Rotate {angle} {self.layers[self.active_layer_idx].name}")
        self.layers[self.active_layer_idx].image = self.layers[self.active_layer_idx].image.rotate(angle, expand=True, resample=Image.BICUBIC)
        self.display_composite()
        self.update_resize_entries()

    def rotate_custom_dialog(self):
        if not self.layers:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Custom Rotate")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        tk.Label(dialog, text="Angle:").pack(pady=10)
        entry = tk.Entry(dialog)
        entry.pack()
        entry.insert(0, "0")
        entry.focus()
        def do_rotate():
            try:
                ang = float(entry.get())
                dialog.destroy()
                self.push_undo(f"Rotate {ang} {self.layers[self.active_layer_idx].name}")
                self.layers[self.active_layer_idx].image = self.layers[self.active_layer_idx].image.rotate(ang, expand=True, resample=Image.BICUBIC)
                self.display_composite()
                self.update_resize_entries()
            except ValueError:
                messagebox.showerror("Error", "Valid number")
        tk.Button(dialog, text="Rotate", command=do_rotate).pack(pady=10)

    def flip_image(self, direction):
        if not self.layers:
            return
        self.push_undo(f"Flip {direction} {self.layers[self.active_layer_idx].name}")
        layer = self.layers[self.active_layer_idx]
        layer.image = ImageOps.mirror(layer.image) if direction=="h" else ImageOps.flip(layer.image)
        self.display_composite()

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
            messagebox.showinfo("Saved", f"Saved composite to:\n{path}\nOriginal untouched.")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    try:
        style = ttk.Style()
        style.theme_use("clam")
    except:
        pass
    app = ImageEditor(root)
    root.mainloop()
