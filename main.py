import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageEnhance, ImageOps
import os
import copy

class ImageEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("ImageEditor - Milestone 2")
        self.root.geometry("1300x850")
        self.root.minsize(1100, 700)

        # Image state
        self.original_path = None
        self.original_image = None  # Never modified - for "save as new"
        self.current_image = None   # Working image (PIL)
        self.photo = None           # Tk image for display
        self.zoom = 1.0

        # Undo/Redo - stores copies of PIL Images
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo = 20

        # Crop state
        self.crop_mode = False
        self.crop_start = None
        self.crop_rect_id = None
        self.crop_coords = None  # in canvas coords
        self.image_offset = (0, 0)  # where image is drawn on canvas
        self.display_size = (0, 0)

        # Resize lock
        self.lock_aspect = tk.BooleanVar(value=True)

        self.setup_ui()
        self.bind_shortcuts()

    def setup_ui(self):
        # --- Top Menu ---
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Image...  Ctrl+O", command=self.open_image)
        file_menu.add_command(label="Save As...    Ctrl+S", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo  Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="Redo  Ctrl+Y", command=self.redo)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        self.root.config(menu=menubar)

        # --- Main Layout: Toolbar | Canvas | Right Panels ---
        self.main_frame = tk.Frame(self.root, bg="#2b2b2b")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # LEFT TOOLBAR - Photoshop style
        self.toolbar = tk.Frame(self.main_frame, bg="#3c3c3c", width=80)
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y)
        self.toolbar.pack_propagate(False)

        tk.Label(self.toolbar, text="TOOLS", bg="#3c3c3c", fg="#aaaaaa", font=("Segoe UI", 8, "bold")).pack(pady=(15,10))

        self.make_tool_button("Open", self.open_image)
        self.make_tool_button("Crop Mode", self.toggle_crop_mode)
        self.make_tool_button("Apply Crop", self.apply_crop)
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=8)

        self.make_tool_button("↺ 90° Left", lambda: self.rotate_image(-90))
        self.make_tool_button("↻ 90° Right", lambda: self.rotate_image(90))
        self.make_tool_button("Rotate...", self.rotate_custom_dialog)
        self.make_tool_button("Flip H", lambda: self.flip_image("h"))
        self.make_tool_button("Flip V", lambda: self.flip_image("v"))

        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=8)
        self.make_tool_button("Undo", self.undo)
        self.make_tool_button("Redo", self.redo)
        self.make_tool_button("Reset", self.reset_image)

        # CENTER - Image Canvas
        center_frame = tk.Frame(self.main_frame, bg="#1e1e1e")
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(center_frame, bg="#1e1e1e", highlightthickness=0, cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas.bind("<ButtonPress-1>", self.on_crop_press)
        self.canvas.bind("<B1-Motion>", self.on_crop_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_crop_release)

        # Bottom status
        self.status_var = tk.StringVar(value="Open an image to start. Milestone 2 ready.")
        status_bar = tk.Label(center_frame, textvariable=self.status_var, anchor="w", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 9), padx=10, pady=4)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # RIGHT PANELS
        self.right_panel = tk.Frame(self.main_frame, bg="#2b2b2b", width=300)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_panel.pack_propagate(False)

        # --- Adjustments Panel ---
        adj_frame = tk.LabelFrame(self.right_panel, text="Adjustments", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=10)
        adj_frame.pack(fill=tk.X, padx=8, pady=8)

        self.sliders = {}
        for name, label in [("brightness", "Brightness"), ("contrast", "Contrast"), ("saturation", "Saturation"), ("sharpness", "Sharpness")]:
            row = tk.Frame(adj_frame, bg="#2b2b2b")
            row.pack(fill=tk.X, pady=4)
            tk.Label(row, text=label, bg="#2b2b2b", fg="#cccccc", width=12, anchor="w", font=("Segoe UI", 9)).pack(side=tk.LEFT)
            scale = tk.Scale(row, from_=0.0, to=2.0, resolution=0.05, orient=tk.HORIZONTAL, bg="#2b2b2b", fg="#cccccc",
                             highlightthickness=0, troughcolor="#444444", length=150, command=lambda v, n=name: self.on_adjust_live(n))
            scale.set(1.0)
            scale.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.sliders[name] = scale

        btn_row = tk.Frame(adj_frame, bg="#2b2b2b")
        btn_row.pack(fill=tk.X, pady=(10,0))
        tk.Button(btn_row, text="Apply Adjustments", command=self.apply_adjustments, bg="#0e639c", fg="white", relief=tk.FLAT, padx=10).pack(side=tk.LEFT)
        tk.Button(btn_row, text="Reset", command=self.reset_sliders, bg="#3c3c3c", fg="white", relief=tk.FLAT, padx=10).pack(side=tk.LEFT, padx=5)

        # --- Resize Panel ---
        resize_frame = tk.LabelFrame(self.right_panel, text="Resize & Save", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=10)
        resize_frame.pack(fill=tk.X, padx=8, pady=8)

        # current size info
        self.size_info_var = tk.StringVar(value="No image")
        tk.Label(resize_frame, textvariable=self.size_info_var, bg="#2b2b2b", fg="#888888", font=("Segoe UI", 8)).pack(anchor="w")

        row_w = tk.Frame(resize_frame, bg="#2b2b2b")
        row_w.pack(fill=tk.X, pady=4)
        tk.Label(row_w, text="Width:", bg="#2b2b2b", fg="#cccccc", width=8, anchor="w").pack(side=tk.LEFT)
        self.width_entry = tk.Entry(row_w, width=10, bg="#3c3c3c", fg="white", insertbackground="white")
        self.width_entry.pack(side=tk.LEFT)

        row_h = tk.Frame(resize_frame, bg="#2b2b2b")
        row_h.pack(fill=tk.X, pady=4)
        tk.Label(row_h, text="Height:", bg="#2b2b2b", fg="#cccccc", width=8, anchor="w").pack(side=tk.LEFT)
        self.height_entry = tk.Entry(row_h, width=10, bg="#3c3c3c", fg="white", insertbackground="white")
        self.height_entry.pack(side=tk.LEFT)

        tk.Checkbutton(resize_frame, text="Lock aspect ratio", variable=self.lock_aspect, bg="#2b2b2b", fg="#cccccc", selectcolor="#3c3c3c", activebackground="#2b2b2b").pack(anchor="w", pady=4)

        tk.Button(resize_frame, text="Apply Resize", command=self.apply_resize, bg="#0e639c", fg="white", relief=tk.FLAT, padx=10, pady=2).pack(fill=tk.X, pady=(8,4))
        tk.Button(resize_frame, text="Save As New File (Never Overwrites)", command=self.save_as, bg="#16825d", fg="white", relief=tk.FLAT, padx=10, pady=6).pack(fill=tk.X, pady=4)

        # Info
        info = tk.LabelFrame(self.right_panel, text="How to Use", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=10, pady=10)
        info.pack(fill=tk.BOTH, padx=8, pady=8, expand=True)
        tk.Label(info, text="1. Open image\n2. Crop Mode > drag on image > Apply Crop\n3. Use Rotate / Flip buttons\n4. Adjust sliders > Apply Adjustments\n5. Set Width/Height > Apply Resize\n6. Save As to new file\n\nUndo: Ctrl+Z  Redo: Ctrl+Y", justify=tk.LEFT, bg="#2b2b2b", fg="#888888", font=("Segoe UI", 8)).pack(anchor="w")

    def make_tool_button(self, text, cmd):
        b = tk.Button(self.toolbar, text=text, command=cmd, bg="#4a4a4a", fg="white", relief=tk.FLAT, font=("Segoe UI", 9), padx=5, pady=6, width=14, wraplength=70)
        b.pack(pady=2, padx=5)

    def bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self.open_image())
        self.root.bind("<Control-O>", lambda e: self.open_image())
        self.root.bind("<Control-s>", lambda e: self.save_as())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-Y>", lambda e: self.redo())

    # ---------- Core Helpers ----------
    def push_undo(self):
        if self.current_image is None:
            return
        if len(self.undo_stack) >= self.max_undo:
            self.undo_stack.pop(0)
        self.undo_stack.append(self.current_image.copy())
        self.redo_stack.clear()
        self.update_status(f"Undo stack: {len(self.undo_stack)} | Redo: {len(self.redo_stack)}")

    def open_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"), ("All", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path)
            img.load()
            # Convert to RGBA for consistent editing, but keep original for save logic
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            self.original_path = path
            self.original_image = img.copy()
            self.current_image = img.copy()
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.reset_sliders()
            self.display_image_on_canvas()
            self.update_resize_entries()
            self.status_var.set(f"Opened: {os.path.basename(path)} | {img.width}x{img.height}")
        except Exception as e:
            messagebox.showerror("Open Error", str(e))

    def display_image_on_canvas(self):
        if self.current_image is None:
            return
        self.canvas.delete("all")
        self.crop_rect_id = None
        self.crop_coords = None

        # Fit to canvas
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 50:
            cw = 800
            ch = 600

        img_w, img_h = self.current_image.size
        scale = min(cw / img_w, ch / img_h, 1.0) * 0.95
        self.zoom = scale
        dw = int(img_w * scale)
        dh = int(img_h * scale)
        self.display_size = (dw, dh)

        display_img = self.current_image.resize((dw, dh), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(display_img)

        x0 = (cw - dw) // 2
        y0 = (ch - dh) // 2
        self.image_offset = (x0, y0)
        self.canvas.create_image(x0, y0, anchor="nw", image=self.photo)
        self.size_info_var.set(f"{self.current_image.width} x {self.current_image.height} px (display {dw}x{dh})")

    def update_resize_entries(self):
        if self.current_image:
            self.width_entry.delete(0, tk.END)
            self.width_entry.insert(0, str(self.current_image.width))
            self.height_entry.delete(0, tk.END)
            self.height_entry.insert(0, str(self.current_image.height))

    def canvas_to_image_coords(self, cx, cy):
        ox, oy = self.image_offset
        dw, dh = self.display_size
        if dw == 0 or dh == 0:
            return None
        # clamp to image
        ix = (cx - ox) / self.zoom
        iy = (cy - oy) / self.zoom
        return (ix, iy)

    # ---------- Crop ----------
    def toggle_crop_mode(self):
        if self.current_image is None:
            messagebox.showinfo("Crop", "Open an image first.")
            return
        self.crop_mode = not self.crop_mode
        if self.crop_mode:
            self.status_var.set("CROP MODE: Drag on image to select area, then click Apply Crop")
            self.canvas.config(cursor="crosshair")
        else:
            self.status_var.set("Crop mode OFF")
            self.canvas.config(cursor="cross")
            if self.crop_rect_id:
                self.canvas.delete(self.crop_rect_id)
                self.crop_rect_id = None

    def on_crop_press(self, event):
        if not self.crop_mode or self.current_image is None:
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
        # normalize
        self.crop_coords = (min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1))

    def apply_crop(self):
        if self.current_image is None or self.crop_coords is None:
            messagebox.showinfo("Crop", "Enter crop mode and drag a rectangle first.")
            return
        try:
            x0, y0, x1, y1 = self.crop_coords
            # Convert canvas coords to image coords
            p0 = self.canvas_to_image_coords(x0, y0)
            p1 = self.canvas_to_image_coords(x1, y1)
            if p0 is None or p1 is None:
                return
            ix0, iy0 = p0
            ix1, iy1 = p1
            # clamp
            ix0 = max(0, min(self.current_image.width, ix0))
            ix1 = max(0, min(self.current_image.width, ix1))
            iy0 = max(0, min(self.current_image.height, iy0))
            iy1 = max(0, min(self.current_image.height, iy1))
            left, right = sorted([int(ix0), int(ix1)])
            top, bottom = sorted([int(iy0), int(iy1)])
            if right - left < 5 or bottom - top < 5:
                messagebox.showinfo("Crop", "Selection too small.")
                return
            self.push_undo()
            self.current_image = self.current_image.crop((left, top, right, bottom))
            self.crop_mode = False
            self.canvas.config(cursor="cross")
            if self.crop_rect_id:
                self.canvas.delete(self.crop_rect_id)
            self.crop_coords = None
            self.display_image_on_canvas()
            self.update_resize_entries()
            self.status_var.set(f"Cropped to {self.current_image.width}x{self.current_image.height}")
        except Exception as e:
            messagebox.showerror("Crop Error", str(e))

    # ---------- Rotate / Flip ----------
    def rotate_image(self, angle):
        if self.current_image is None:
            return
        self.push_undo()
        # PIL rotates counter-clockwise, expand to keep whole image
        self.current_image = self.current_image.rotate(angle, expand=True, resample=Image.BICUBIC)
        self.display_image_on_canvas()
        self.update_resize_entries()

    def rotate_custom_dialog(self):
        if self.current_image is None:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Custom Rotate")
        dialog.geometry("300x120")
        dialog.transient(self.root)
        tk.Label(dialog, text="Angle (degrees, -360 to 360):").pack(pady=10)
        entry = tk.Entry(dialog)
        entry.pack()
        entry.insert(0, "0")
        entry.focus()
        def do_rotate():
            try:
                ang = float(entry.get())
                dialog.destroy()
                self.push_undo()
                self.current_image = self.current_image.rotate(ang, expand=True, resample=Image.BICUBIC)
                self.display_image_on_canvas()
                self.update_resize_entries()
            except ValueError:
                messagebox.showerror("Error", "Enter a valid number")
        tk.Button(dialog, text="Rotate", command=do_rotate).pack(pady=10)

    def flip_image(self, direction):
        if self.current_image is None:
            return
        self.push_undo()
        if direction == "h":
            self.current_image = ImageOps.mirror(self.current_image)
        else:
            self.current_image = ImageOps.flip(self.current_image)
        self.display_image_on_canvas()

    # ---------- Adjustments ----------
    def on_adjust_live(self, name):
        # Live preview disabled to keep undo clean; we just update status
        # If you want live, uncomment below
        pass

    def apply_adjustments(self):
        if self.current_image is None:
            return
        self.push_undo()
        img = self.current_image
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

            self.current_image = img
            self.display_image_on_canvas()
            self.status_var.set(f"Adjustments applied: B={b:.2f} C={c:.2f} S={s:.2f} Sh={sh:.2f}")
        except Exception as e:
            messagebox.showerror("Adjustment Error", str(e))

    def reset_sliders(self):
        for scale in self.sliders.values():
            scale.set(1.0)

    # ---------- Resize ----------
    def apply_resize(self):
        if self.current_image is None:
            return
        try:
            w_text = self.width_entry.get().strip()
            h_text = self.height_entry.get().strip()
            if not w_text or not h_text:
                return
            new_w = int(w_text)
            new_h = int(h_text)
            if new_w <= 0 or new_h <= 0 or new_w > 10000 or new_h > 10000:
                raise ValueError("Width/Height must be 1-10000")

            if self.lock_aspect.get():
                # Use width as driver if it changed, else height
                orig_w, orig_h = self.current_image.size
                # Decide which entry the user edited last - simple heuristic: if aspect doesn't match, preserve
                # For now, just enforce aspect from width
                # If user changed both, we trust them but warn
                aspect = orig_w / orig_h
                # Check if entries are close to aspect
                # We'll use width to calculate height if height is not proportional
                if abs((new_w / new_h) - aspect) > 0.01:
                    # Recalculate height from width
                    new_h = int(new_w / aspect)
                    self.height_entry.delete(0, tk.END)
                    self.height_entry.insert(0, str(new_h))

            self.push_undo()
            self.current_image = self.current_image.resize((new_w, new_h), Image.LANCZOS)
            self.display_image_on_canvas()
            self.update_resize_entries()
            self.status_var.set(f"Resized to {new_w}x{new_h}")
        except ValueError as ve:
            messagebox.showerror("Resize Error", str(ve))
        except Exception as e:
            messagebox.showerror("Resize Error", str(e))

    # ---------- Undo/Redo/Reset ----------
    def undo(self):
        if not self.undo_stack:
            self.status_var.set("Nothing to undo")
            return
        self.redo_stack.append(self.current_image.copy())
        self.current_image = self.undo_stack.pop()
        self.display_image_on_canvas()
        self.update_resize_entries()
        self.status_var.set(f"Undo. Undo:{len(self.undo_stack)} Redo:{len(self.redo_stack)}")

    def redo(self):
        if not self.redo_stack:
            self.status_var.set("Nothing to redo")
            return
        self.undo_stack.append(self.current_image.copy())
        self.current_image = self.redo_stack.pop()
        self.display_image_on_canvas()
        self.update_resize_entries()
        self.status_var.set(f"Redo. Undo:{len(self.undo_stack)} Redo:{len(self.redo_stack)}")

    def reset_image(self):
        if self.original_image is None:
            return
        self.push_undo()
        self.current_image = self.original_image.copy()
        self.reset_sliders()
        self.display_image_on_canvas()
        self.update_resize_entries()
        self.status_var.set("Reset to original")

    # ---------- Save ----------
    def save_as(self):
        if self.current_image is None:
            messagebox.showinfo("Save", "No image to save.")
            return
        # Never overwrite original - default to new name
        initial = "edited_image.png"
        if self.original_path:
            base, ext = os.path.splitext(os.path.basename(self.original_path))
            initial = f"{base}_edited{ext or '.png'}"

        path = filedialog.asksaveasfilename(
            initialfile=initial,
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg"), ("All", "*.*")],
            title="Save As - Original will NOT be overwritten"
        )
        if not path:
            return
        # Safety: prevent overwriting original
        if self.original_path and os.path.abspath(path) == os.path.abspath(self.original_path):
            if not messagebox.askyesno("Warning", "You are about to overwrite the original! Milestone 2 rule says never overwrite. Save anyway?"):
                return
        try:
            # Handle RGBA -> JPEG
            save_img = self.current_image
            if path.lower().endswith((".jpg", ".jpeg")) and save_img.mode == "RGBA":
                save_img = save_img.convert("RGB")
            save_img.save(path)
            self.status_var.set(f"Saved as: {os.path.basename(path)} ({save_img.width}x{save_img.height})")
            messagebox.showinfo("Saved", f"Saved to:\n{path}\nOriginal untouched.")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def update_status(self, msg):
        self.status_var.set(msg)

if __name__ == "__main__":
    root = tk.Tk()
    # Optional: nicer theme
    try:
        style = ttk.Style()
        style.theme_use("clam")
    except:
        pass
    app = ImageEditor(root)
    # Resize canvas on window resize
    def on_resize(event):
        if app.current_image:
            app.display_image_on_canvas()
    root.bind("<Configure>", lambda e: root.after(100, lambda: app.display_image_on_canvas() if e.widget == root else None))
    root.mainloop()
