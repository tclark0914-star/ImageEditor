
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
from PIL import Image, ImageTk, ImageEnhance, ImageOps, ImageFilter, ImageStat, ImageDraw, ImageChops, ImageFont
import os
import math
import hashlib
import random
import io

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
        self.mask = None
        # TIER 6A: Transform properties
        self.offset_x = 0
        self.offset_y = 0
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.rotation = 0.0  # degrees
        # TIER 6B: Editable text & shapes metadata
        self.is_text_layer = False
        self.text_data = None  # {"text": "", "font_size": 40, "color": "#ffffff", "font_family": "Arial", "bold": False, "italic": False, "align": "left", "stroke": 0, "stroke_color": "#000000"}
        self.is_shape_layer = False
        self.shape_data = None  # {"type": "rect/ellipse/line/arrow/polygon", "fill": "#ff0000", "stroke": "#000000", "stroke_width": 2, "points": []}
        self.locked = False
        # TIER 6C: Enhanced text + shapes + layer management
        self.text_align = "left"  # left, center, right, justify
        self.line_spacing = 1.2
        self.letter_spacing = 0
        self.shape_corner_radius = 0  # for rounded rect
        self.blend_opacity_preview = True
        # TIER 7: Layer Styles + Groups + Real PSD
        self.layer_styles = {
            "drop_shadow": {"enabled": False, "offset_x": 5, "offset_y": 5, "blur": 10, "color": "#000000", "opacity": 0.5},
            "outer_glow": {"enabled": False, "blur": 15, "color": "#ffff00", "opacity": 0.8},
            "inner_glow": {"enabled": False, "blur": 10, "color": "#ffffff", "opacity": 0.5},
            "stroke": {"enabled": False, "width": 3, "color": "#000000", "opacity": 1.0, "position": "outside"},  # outside, inside, center
            "color_overlay": {"enabled": False, "color": "#ff0000", "opacity": 0.5, "blend_mode": "normal"},
            "inner_shadow": {"enabled": False, "offset_x": 3, "offset_y": 3, "blur": 8, "color": "#000000", "opacity": 0.5}
        }
        self.is_group = False
        self.group_layers = []  # for group layers
        self.group_collapsed = False
        # TIER 8: Smart Objects + Adjustment Layers + Filters + Timeline
        self.is_smart_object = False
        self.smart_original = None  # PIL Image backup for non-destructive
        self.smart_filters = []  # [{"type": "gaussian_blur", "params": {...}, "enabled": True}]
        self.is_adjustment_layer = False
        self.adjustment_type = None  # "levels", "curves", "hue_sat", "color_balance", "brightness_contrast"
        self.adjustment_data = {}  # params for adjustment
        self.is_frame = False
        self.frame_duration = 100  # ms for timeline
    def copy(self):
        c = Layer(self.name, self.image.copy(), self.visible, self.opacity, self.blend_mode)
        if self.mask is not None:
            c.mask = self.mask.copy()
        c.offset_x = self.offset_x
        c.offset_y = self.offset_y
        c.scale_x = self.scale_x
        c.scale_y = self.scale_y
        c.rotation = self.rotation
        c.is_text_layer = self.is_text_layer
        c.text_data = self.text_data.copy() if self.text_data else None
        c.is_shape_layer = self.is_shape_layer
        c.shape_data = self.shape_data.copy() if self.shape_data else None
        c.locked = self.locked
        c.text_align = self.text_align
        c.line_spacing = self.line_spacing
        c.letter_spacing = self.letter_spacing
        c.shape_corner_radius = self.shape_corner_radius
        c.blend_opacity_preview = self.blend_opacity_preview
        # TIER 7 copy
        import copy as copy_module
        c.layer_styles = copy_module.deepcopy(self.layer_styles)
        c.is_group = self.is_group
        c.group_layers = [gl.copy() for gl in self.group_layers] if self.group_layers else []
        c.group_collapsed = self.group_collapsed
        # TIER 8 copy
        c.is_smart_object = self.is_smart_object
        c.smart_original = self.smart_original.copy() if self.smart_original else None
        c.smart_filters = copy_module.deepcopy(self.smart_filters)
        c.is_adjustment_layer = self.is_adjustment_layer
        c.adjustment_type = self.adjustment_type
        c.adjustment_data = copy_module.deepcopy(self.adjustment_data)
        c.is_frame = self.is_frame
        c.frame_duration = self.frame_duration
        return c
    def get_transformed_image(self, base_size=None):
        """Return transformed image with scale/rotation applied"""
        img = self.image
        # Apply scale
        if self.scale_x != 1.0 or self.scale_y != 1.0:
            w, h = img.size
            new_w = max(1, int(w * self.scale_x))
            new_h = max(1, int(h * self.scale_y))
            img = img.resize((new_w, new_h), Image.LANCZOS)
        # Apply rotation
        if self.rotation != 0:
            img = img.rotate(self.rotation, expand=True, resample=Image.BICUBIC)
        return img
    def get_bounds(self):
        """TIER 6B: Get layer bounds in canvas coordinates (including offset)"""
        img = self.get_transformed_image()
        w, h = img.size
        return (self.offset_x, self.offset_y, self.offset_x + w, self.offset_y + h)
    def get_untransformed_bounds(self):
        """TIER 6C: Get bounds without transform (for center scaling)"""
        w, h = self.image.size
        return (self.offset_x, self.offset_y, self.offset_x + w, self.offset_y + h)
    def get_styled_image(self):
        """TIER 7: Apply layer styles (drop shadow, glow, stroke, etc) to get final image"""
        img = self.get_transformed_image()
        # If no styles enabled, return as-is
        if not any(s.get("enabled", False) for s in self.layer_styles.values()):
            return img
        
        # Create base for compositing styles
        # We need to handle drop shadow first (behind), then main, then stroke/glow on top
        
        # Start with drop shadow
        final_img = img.copy()
        w, h = img.size
        
        # Helper to create shadow/glow
        def apply_drop_shadow(base_img, style):
            if not style["enabled"]:
                return None
            offset_x = style["offset_x"]
            offset_y = style["offset_y"]
            blur = style["blur"]
            color = style["color"]
            opacity = style["opacity"]
            # Create shadow from alpha channel
            alpha = base_img.split()[3] if base_img.mode == "RGBA" else Image.new("L", base_img.size, 255)
            # Colorize shadow
            shadow = Image.new("RGBA", base_img.size, self.hex_to_rgba_static(color, int(255*opacity)))
            # Blur alpha
            if blur > 0:
                alpha = alpha.filter(ImageFilter.GaussianBlur(radius=blur))
            shadow.putalpha(alpha)
            return shadow, offset_x, offset_y
        
        # For simplicity, we'll composite drop shadow behind
        shadow_data = None
        if self.layer_styles["drop_shadow"]["enabled"]:
            s = self.layer_styles["drop_shadow"]
            # Create larger canvas for shadow
            pad = s["blur"] * 2 + abs(s["offset_x"]) + abs(s["offset_y"]) + 10
            new_w = w + pad * 2
            new_h = h + pad * 2
            canvas = Image.new("RGBA", (new_w, new_h), (0,0,0,0))
            # Shadow
            alpha = img.split()[3] if img.mode == "RGBA" else Image.new("L", img.size, 255)
            if s["blur"] > 0:
                alpha = alpha.filter(ImageFilter.GaussianBlur(radius=s["blur"]))
            shadow_color = self.hex_to_rgba_static(s["color"], int(255*s["opacity"]))
            shadow = Image.new("RGBA", img.size, shadow_color)
            shadow.putalpha(alpha)
            # Paste shadow at offset
            canvas.paste(shadow, (pad + s["offset_x"], pad + s["offset_y"]), shadow)
            # Paste original on top at pad
            canvas.paste(img, (pad, pad), img if img.mode == "RGBA" else None)
            final_img = canvas
            # Note: offset adjustment needed in real rendering - for now return canvas
        
        # Stroke
        if self.layer_styles["stroke"]["enabled"]:
            st = self.layer_styles["stroke"]
            # Simple stroke: create outline by expanding alpha
            # For now, add stroke as extra outline
            stroke_w = st["width"]
            alpha = final_img.split()[3] if final_img.mode == "RGBA" else Image.new("L", final_img.size, 255)
            # Dilate alpha for stroke
            # Use max filter for dilation
            stroke_alpha = alpha.filter(ImageFilter.MaxFilter(size=stroke_w*2+1))
            stroke_color = self.hex_to_rgba_static(st["color"], int(255*st["opacity"]))
            stroke_layer = Image.new("RGBA", final_img.size, stroke_color)
            stroke_layer.putalpha(stroke_alpha)
            # Composite stroke behind final (outside) or as per position
            if st["position"] == "outside":
                final_img = Image.alpha_composite(stroke_layer, final_img)
            else:
                # Inside/center - composite on top with masking
                final_img = Image.alpha_composite(final_img, stroke_layer) if st["position"] == "center" else final_img
        
        return final_img
    
    @staticmethod
    def hex_to_rgba_static(hex_color, alpha=255):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r,g,b,alpha)

class ImageEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("ImageEditor - TIER 8 (Filters + Liquify + Smart Objects + Adjustment Layers + Timeline) | v8 ALL")
        self.root.geometry("1550x1000")
        self.root.minsize(1300, 850)

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

        self.current_tool = tk.StringVar(value="select")
        self.crop_mode = False
        self.crop_start = None
        self.crop_rect_id = None
        self.crop_coords = None
        self.image_offset = (0, 0)
        self.display_size = (0, 0)
        self.lock_aspect = tk.BooleanVar(value=True)

        self.brush_size = tk.IntVar(value=12)
        self.brush_color = "#ff0000"
        self.gradient_color2 = "#0000ff"
        self.gradient_type = tk.StringVar(value="linear")
        self.brush_last_pos = None
        self.is_drawing = False

        self.wand_tolerance = tk.IntVar(value=32)
        self.wand_contiguous = tk.BooleanVar(value=True)
        self._last_wand_mask = None

        self.clone_source = None
        self._clone_offset = None

        self.lasso_points = []
        self.lasso_canvas_ids = []
        self.lasso_active = False
        self.feather_radius = tk.IntVar(value=5)
        self.mask_edit_mode = tk.BooleanVar(value=False)

        # Gradient (Tier4)
        self.gradient_start = None
        self.gradient_end = None
        self.gradient_preview_id = None

        # Shadows/Highlights (Tier4)
        self.shadows_amount = tk.IntVar(value=0)
        self.highlights_amount = tk.IntVar(value=0)

        # TIER 6A: Free Transform state
        self.transform_active = False
        self.transform_start_pos = None
        self.transform_start_offset = None
        self.transform_handle = None  # 'move', 'scale_nw', 'scale_ne', etc, 'rotate'
        self.transform_ids = []  # canvas IDs for handles
        self.layer_opacity_var = tk.DoubleVar(value=1.0)

        # TIER 6B: Shapes & Editable Text & Canvas Handles
        self.shape_type = tk.StringVar(value="rectangle")  # rectangle, ellipse, line, arrow, polygon
        self.shape_fill = "#ff0000"
        self.shape_stroke = "#000000"
        self.shape_stroke_width = tk.IntVar(value=3)
        self.shape_opacity = tk.DoubleVar(value=1.0)
        self.shape_start = None
        self.shape_preview_id = None
        self.show_transform_handles = tk.BooleanVar(value=True)
        self.snap_enabled = tk.BooleanVar(value=True)
        self.text_font_size = tk.IntVar(value=48)
        self.text_font_family = tk.StringVar(value="Arial")
        self.text_color = "#ffffff"
        self.text_bold = tk.BooleanVar(value=False)
        self.text_italic = tk.BooleanVar(value=False)
        self.text_stroke_width = tk.IntVar(value=0)
        self.text_stroke_color = "#000000"
        self.canvas_handles = []  # IDs for transform handles
        self.active_handle = None
        self.handle_size = 8

        # TIER 6C: Font Picker + Alignment + Rounded Rect + Pen Tool + Shift/Alt + Lock
        self.text_align = tk.StringVar(value="left")  # left, center, right, justify
        self.text_line_spacing = tk.DoubleVar(value=1.2)
        self.text_letter_spacing = tk.IntVar(value=0)
        self.shape_corner_radius = tk.IntVar(value=20)  # for rounded rect
        self.pen_points = []  # for pen tool freehand path
        self.pen_active = False
        self.pen_canvas_ids = []
        self.lock_aspect_ratio = tk.BooleanVar(value=False)  # Shift key
        self.scale_from_center = tk.BooleanVar(value=False)  # Alt key
        self.layer_locked = tk.BooleanVar(value=False)
        self.common_fonts = ["Arial", "Times New Roman", "Courier New", "Verdana", "Georgia", "Comic Sans MS", "Impact", "DejaVuSans", "DejaVuSerif", "Consolas", "Tahoma", "Trebuchet MS"]
        self.shift_pressed = False
        self.alt_pressed = False

        # TIER 8: Liquify + Timeline + Smart Objects + Adjustment Layers
        self.liquify_size = 80
        self.liquify_strength = 50
        self.liquify_mode = tk.StringVar(value="push")  # push, bloat, pucker, twirl
        self.timeline_frames = []  # list of composited PIL Images
        self.timeline_playing = False
        self.timeline_current_frame = 0
        self.timeline_fps = tk.IntVar(value=12)
        self.smart_objects_enabled = True
        self.adjustment_preview = None
        self.filter_preview_img = None
        self.oil_paint_radius = tk.IntVar(value=5)
        self.motion_blur_angle = tk.IntVar(value=0)
        self.motion_blur_distance = tk.IntVar(value=15)

        # AI Prompt (Tier 5 - Modular Plugin System)
        self.ai_prompt = tk.StringVar(value="a beautiful sunset over mountains, digital art")
        self.ai_negative_prompt = tk.StringVar(value="")
        self.ai_prompt_width = tk.IntVar(value=512)
        self.ai_prompt_height = tk.IntVar(value=512)
        self.ai_style = tk.StringVar(value="Realistic")
        self.ai_api_key = ""
        self.ai_providers = {}  # Plugin registry
        self.ai_provider_order = []
        self.ai_generators_dir = os.path.join(os.path.dirname(__file__) if "__file__" in globals() else os.getcwd(), "ai_generators")
        # AI Plugin config file - MUST be before load_ai_providers()
        self.ai_config_path = os.path.expanduser("~/.imageeditor_ai.json")
        self.pan_start = None
        self.load_ai_providers()  # Load plugin system
        try:
            # Load API key if exists
            import json
            if os.path.exists(self.ai_config_path):
                with open(self.ai_config_path, "r") as f:
                    data = json.load(f)
                    self.ai_api_key = data.get("openai_key", "")
        except:
            pass

        self.setup_ui()
        self.bind_shortcuts()

    def load_ai_providers(self):
        # Modular AI Provider Registry - Add new generators without editing main.py!
        self.ai_providers = {}
        self.ai_provider_order = []
        
        # Built-in providers (you can add more in ai_generators/ folder)
        self.register_ai_provider("pollinations", {
            "name": "Pollinations (FREE - No Key)",
            "description": "Free online AI, no install, no watermark, unlimited",
            "needs_key": False,
            "free": True,
            "func": self.ai_generate_pollinations,
            "enabled": True
        })
        self.register_ai_provider("huggingface", {
            "name": "HuggingFace Inference (FREE - Optional Token)",
            "description": "Free SD API, optional HF token for higher rate limits",
            "needs_key": False,
            "free": True,
            "func": self.ai_generate_huggingface,
            "enabled": True
        })
        self.register_ai_provider("openai", {
            "name": "OpenAI DALL-E 3 ($)",
            "description": "Best quality, requires OpenAI API key",
            "needs_key": True,
            "key_name": "openai_key",
            "free": False,
            "func": self.ai_generate_openai_dalle,
            "enabled": True
        })
        self.register_ai_provider("stability", {
            "name": "Stability AI (SDXL - $)",
            "description": "Stability.ai API, needs stability_key",
            "needs_key": True,
            "key_name": "stability_key",
            "free": False,
            "func": self.ai_generate_stability,
            "enabled": False  # Disabled by default, enable in config
        })
        self.register_ai_provider("replicate", {
            "name": "Replicate (Many models - $)",
            "description": "replicate.com API, needs replicate_key",
            "needs_key": True,
            "key_name": "replicate_key",
            "free": False,
            "func": self.ai_generate_replicate,
            "enabled": False
        })
        self.register_ai_provider("automatic1111", {
            "name": "Automatic1111 WebUI (Local - http://127.0.0.1:7860)",
            "description": "Local A1111 API, needs A1111 running with --api flag, BEST for local GPU",
            "needs_key": False,
            "free": True,
            "func": self.ai_generate_automatic1111,
            "enabled": True
        })
        self.register_ai_provider("comfyui", {
            "name": "ComfyUI (Local - http://127.0.0.1:8188)",
            "description": "Local ComfyUI, needs ComfyUI running, advanced workflows",
            "needs_key": False,
            "free": True,
            "func": self.ai_generate_comfyui,
            "enabled": True
        })
        self.register_ai_provider("local_sd", {
            "name": "Local Stable Diffusion (diffusers)",
            "description": "Local SD, needs: pip install diffusers transformers torch",
            "needs_key": False,
            "free": True,
            "func": self.ai_generate_stable_diffusion,
            "enabled": True
        })
        self.register_ai_provider("procedural", {
            "name": "Procedural Demo (Offline, No Watermark)",
            "description": "Offline fallback, keyword-based beautiful gradients, NO WATERMARK now!",
            "needs_key": False,
            "free": True,
            "func": self.ai_generate_procedural,
            "enabled": True
        })
        
        # Load external plugins from ai_generators/ folder
        self.load_external_ai_plugins()
        
        # Load config to enable/disable and order
        try:
            import json
            if os.path.exists(self.ai_config_path):
                with open(self.ai_config_path, "r") as f:
                    cfg = json.load(f)
                    # Restore enabled states
                    for pid, enabled in cfg.get("providers_enabled", {}).items():
                        if pid in self.ai_providers:
                            self.ai_providers[pid]["enabled"] = enabled
                    # Restore custom providers
                    for custom in cfg.get("custom_providers", []):
                        # custom = {"id": "myapi", "name": "...", "url": "...", "type": "openai_compat"}
                        self.register_custom_api_provider(custom)
        except Exception as e:
            print(f"Load AI config error: {e}")

    def register_ai_provider(self, provider_id, info):
        self.ai_providers[provider_id] = info
        if provider_id not in self.ai_provider_order:
            self.ai_provider_order.append(provider_id)

    def load_external_ai_plugins(self):
        # Scan ai_generators/ for .py files that define register() function
        try:
            os.makedirs(self.ai_generators_dir, exist_ok=True)
            # Create example plugin file if dir empty
            example_path = os.path.join(self.ai_generators_dir, "_example_plugin.py")
            if not os.path.exists(example_path):
                with open(example_path, "w") as f:
                    f.write('''# Example custom AI generator plugin
# Place your own .py files in ai_generators/ folder
# Each file must define register(editor) that calls editor.register_ai_provider()

def generate_my_custom_api(prompt, width, height, style, editor, status_var=None):
    # Your custom API call here
    # Must return PIL Image or None
    import requests
    from PIL import Image
    from io import BytesIO
    # Example: call your local ComfyUI or Automatic1111 API
    # response = requests.post("http://127.0.0.1:7860/sdapi/v1/txt2img", json={...})
    # return Image.open(BytesIO(response.content))
    return None

def register(editor):
    editor.register_ai_provider("my_custom", {
        "name": "My Custom API (Example)",
        "description": "Edit _example_plugin.py to add your own",
        "needs_key": False,
        "free": True,
        "func": lambda p,w,h,s, status=None: generate_my_custom_api(p,w,h,s,editor,status),
        "enabled": False
    })
''')
            
            for fname in os.listdir(self.ai_generators_dir):
                if not fname.endswith(".py") or fname.startswith("_") and fname != "_example_plugin.py":
                    if fname.startswith("_"):
                        continue
                fpath = os.path.join(self.ai_generators_dir, fname)
                try:
                    import importlib.util
                    spec = importlib.util.spec_from_file_location(f"ai_gen_{fname[:-3]}", fpath)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    if hasattr(mod, "register"):
                        mod.register(self)
                        print(f"Loaded AI plugin: {fname}")
                except Exception as e:
                    print(f"Failed to load plugin {fname}: {e}")
        except Exception as e:
            print(f"Plugin scan error: {e}")

    def register_custom_api_provider(self, custom):
        # custom = {"id": "myapi", "name": "My API", "url": "https://...", "type": "pollinations_compat"}
        pid = custom.get("id", "custom_"+str(len(self.ai_providers)))
        def make_func(cfg):
            def gen_func(prompt, width, height, style, status_var=None):
                import requests
                from io import BytesIO
                url = cfg.get("url", "")
                # Replace {prompt}, {width}, {height}, {style} in URL
                url = url.replace("{prompt}", requests.utils.quote(f"{prompt}, {style} style"))
                url = url.replace("{width}", str(width))
                url = url.replace("{height}", str(height))
                url = url.replace("{style}", style)
                headers = cfg.get("headers", {})
                # Add API key if present
                if cfg.get("api_key"):
                    headers["Authorization"] = f"Bearer {cfg['api_key']}"
                resp = requests.get(url, headers=headers, timeout=60)
                if resp.status_code == 200:
                    return Image.open(BytesIO(resp.content)).convert("RGBA").resize((width,height), Image.LANCZOS)
                else:
                    raise Exception(f"Custom API {resp.status_code}: {resp.text[:200]}")
            return gen_func
        
        self.register_ai_provider(pid, {
            "name": custom.get("name", pid),
            "description": custom.get("description", f"Custom API: {custom.get('url','')}"),
            "needs_key": False,
            "free": True,
            "func": make_func(custom),
            "enabled": custom.get("enabled", True),
            "custom": True,
            "config": custom
        })


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
        layer_menu.add_separator()
        layer_menu.add_command(label="Add Layer Mask", command=self.add_layer_mask)
        layer_menu.add_command(label="Delete Layer Mask", command=self.delete_layer_mask)
        layer_menu.add_command(label="Apply Mask", command=self.apply_layer_mask)
        layer_menu.add_separator()
        layer_menu.add_command(label="Layer Styles... (Tier 7)", command=self.layer_styles_dialog)
        layer_menu.add_command(label="Clear Layer Styles", command=self.clear_layer_styles)
        layer_menu.add_separator()
        layer_menu.add_command(label="New Group (Folder) - Tier7", command=self.create_group_layer)
        layer_menu.add_command(label="Add to Group - Tier7", command=self.add_to_group)
        layer_menu.add_command(label="Ungroup - Tier7", command=self.ungroup_layer)
        layer_menu.add_separator()
        layer_menu.add_command(label="Export REAL PSD (Tier7)", command=self.export_psd_layers)
        layer_menu.add_command(label="Export PNG Sequence", command=lambda: self.export_png_sequence(filedialog.askdirectory(title="Export folder") or "."))
        menubar.add_cascade(label="Layer", menu=layer_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo  Ctrl+Z", command=self.undo)
        edit_menu.add_command(label="Redo  Ctrl+Y", command=self.redo)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        select_menu = tk.Menu(menubar, tearoff=0)
        select_menu.add_command(label="Feather Selection...", command=self.feather_dialog)
        select_menu.add_command(label="Invert Selection", command=self.invert_selection)
        select_menu.add_command(label="Clear Selection", command=self.clear_selection)
        select_menu.add_command(label="Auto Crop to Content", command=self.auto_crop_content)
        menubar.add_cascade(label="Select", menu=select_menu)

        adjust_menu = tk.Menu(menubar, tearoff=0)
        adjust_menu.add_command(label="Levels...", command=self.levels_dialog)
        adjust_menu.add_command(label="Curves...", command=self.curves_dialog)
        adjust_menu.add_command(label="Hue/Saturation...", command=self.hue_saturation_dialog)
        adjust_menu.add_separator()
        adjust_menu.add_command(label="Shadows/Highlights... (Tier4)", command=self.shadows_highlights_dialog)
        adjust_menu.add_command(label="Vignette... (Tier4)", command=self.vignette_dialog)
        menubar.add_cascade(label="Adjust", menu=adjust_menu)

        # TIER 8: PRO FILTERS MENU
        filter_menu = tk.Menu(menubar, tearoff=0)
        filter_menu.add_command(label="Grayscale", command=lambda: self.apply_filter("grayscale"))
        filter_menu.add_command(label="Sepia", command=lambda: self.apply_filter("sepia"))
        filter_menu.add_command(label="Invert", command=lambda: self.apply_filter("invert"))
        filter_menu.add_separator()
        blur_sub = tk.Menu(filter_menu, tearoff=0)
        blur_sub.add_command(label="Gaussian Blur... (Tier8)", command=self.gaussian_blur_dialog)
        blur_sub.add_command(label="Motion Blur... (Tier8)", command=self.motion_blur_dialog)
        blur_sub.add_command(label="Radial Blur (Tier8)", command=lambda: self.apply_filter_advanced("radial_blur", {}))
        blur_sub.add_command(label="Box Blur", command=lambda: self.apply_filter("blur"))
        filter_menu.add_cascade(label="Blur", menu=blur_sub)
        sharpen_sub = tk.Menu(filter_menu, tearoff=0)
        sharpen_sub.add_command(label="Sharpen", command=lambda: self.apply_filter("sharpen"))
        sharpen_sub.add_command(label="Unsharp Mask... (Tier8)", command=self.unsharp_mask_dialog)
        sharpen_sub.add_command(label="High Pass (Tier8)", command=lambda: self.apply_filter_advanced("high_pass", {"radius": 10}))
        filter_menu.add_cascade(label="Sharpen", menu=sharpen_sub)
        filter_menu.add_separator()
        distort_sub = tk.Menu(filter_menu, tearoff=0)
        distort_sub.add_command(label="Wave... (Tier8)", command=self.wave_distort_dialog)
        distort_sub.add_command(label="Twirl... (Tier8)", command=self.twirl_dialog)
        distort_sub.add_command(label="Ripple (Tier8)", command=lambda: self.apply_filter_advanced("ripple", {}))
        distort_sub.add_command(label="Liquify Brush Tool (Tier8)", command=lambda: self.current_tool.set("liquify"))
        filter_menu.add_cascade(label="Distort (Tier8)", menu=distort_sub)
        stylize_sub = tk.Menu(filter_menu, tearoff=0)
        stylize_sub.add_command(label="Oil Paint... (Tier8)", command=self.oil_paint_dialog)
        stylize_sub.add_command(label="Emboss", command=lambda: self.apply_filter("emboss"))
        stylize_sub.add_command(label="Find Edges (Tier8)", command=lambda: self.apply_filter_advanced("find_edges", {}))
        stylize_sub.add_command(label="Pixelate... (Tier8)", command=self.pixelate_dialog)
        stylize_sub.add_command(label="Posterize... (Tier8)", command=self.posterize_dialog)
        filter_menu.add_cascade(label="Stylize (Tier8)", menu=stylize_sub)
        filter_menu.add_separator()
        filter_menu.add_command(label="Filter Gallery... (Tier8 ALL)", command=self.filter_gallery_dialog)
        filter_menu.add_command(label="BW High Contrast", command=lambda: self.apply_filter("bw_contrast"))
        menubar.add_cascade(label="Filters", menu=filter_menu)

        # TIER 8: ADJUSTMENT LAYERS MENU
        adj_layer_menu = tk.Menu(menubar, tearoff=0)
        adj_layer_menu.add_command(label="Brightness/Contrast... (Adj Layer)", command=lambda: self.add_adjustment_layer("brightness_contrast"))
        adj_layer_menu.add_command(label="Levels... (Adj Layer)", command=lambda: self.add_adjustment_layer("levels"))
        adj_layer_menu.add_command(label="Curves... (Adj Layer)", command=lambda: self.add_adjustment_layer("curves"))
        adj_layer_menu.add_command(label="Hue/Saturation... (Adj Layer)", command=lambda: self.add_adjustment_layer("hue_sat"))
        adj_layer_menu.add_command(label="Color Balance... (Adj)", command=lambda: self.add_adjustment_layer("color_balance"))
        adj_layer_menu.add_command(label="Black & White (Adj)", command=lambda: self.add_adjustment_layer("black_white"))
        adj_layer_menu.add_separator()
        adj_layer_menu.add_command(label="Convert to Smart Object (Tier8)", command=self.convert_to_smart_object)
        adj_layer_menu.add_command(label="Edit Smart Object", command=self.edit_smart_object)
        adj_layer_menu.add_command(label="Update Smart Object", command=self.update_smart_object)
        adj_layer_menu.add_separator()
        adj_layer_menu.add_command(label="Clear Smart Filters", command=self.clear_smart_filters)
        menubar.add_cascade(label="Smart+Adj (Tier8)", menu=adj_layer_menu)

        # TIER 8: TIMELINE MENU
        timeline_menu = tk.Menu(menubar, tearoff=0)
        timeline_menu.add_command(label="New Frame from Layers", command=self.timeline_add_frame)
        timeline_menu.add_command(label="Duplicate Frame", command=self.timeline_duplicate_frame)
        timeline_menu.add_command(label="Delete Frame", command=self.timeline_delete_frame)
        timeline_menu.add_separator()
        timeline_menu.add_command(label="Play Timeline (GIF Preview)", command=self.timeline_play)
        timeline_menu.add_command(label="Stop Timeline", command=self.timeline_stop)
        timeline_menu.add_command(label="Export GIF / MP4...", command=self.timeline_export_dialog)
        menubar.add_cascade(label="Timeline (Tier8)", menu=timeline_menu)

        ai_menu = tk.Menu(menubar, tearoff=0)
        ai_menu.add_command(label="Generate Image from Prompt...  Ctrl+G", command=self.ai_prompt_dialog)
        ai_menu.add_command(label="AI Fill Selection with Prompt...", command=self.ai_fill_selection_with_prompt)
        ai_menu.add_command(label="AI Replace Background with Prompt...", command=self.ai_replace_bg_with_prompt)
        ai_menu.add_separator()
        ai_menu.add_command(label="Remove Background (AI)  Ctrl+B", command=self.ai_remove_background)
        ai_menu.add_command(label="Upscale 2x (AI)", command=self.ai_upscale)
        ai_menu.add_command(label="Auto Enhance (AI)", command=self.ai_auto_enhance)
        ai_menu.add_command(label="Denoise (AI)", command=self.ai_denoise)
        ai_menu.add_separator()
        ai_menu.add_command(label="Manage AI Providers (Add/Remove)...", command=self.ai_manage_providers_dialog)
        ai_menu.add_command(label="Setup API Keys...", command=self.ai_setup_keys_dialog)
        ai_menu.add_command(label="Open ai_generators Folder", command=self.ai_open_generators_folder)
        menubar.add_cascade(label="AI", menu=ai_menu)

        self.root.config(menu=menubar)

        self.main_frame = tk.Frame(self.root, bg="#2b2b2b")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # LEFT Tools
        self.toolbar = tk.Frame(self.main_frame, bg="#3c3c3c", width=105)
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y)
        self.toolbar.pack_propagate(False)
        tk.Label(self.toolbar, text="TOOLS", bg="#3c3c3c", fg="#aaaaaa", font=("Segoe UI", 8, "bold")).pack(pady=(12,8))

        tools = [("Select", "select"), ("Move", "move"), ("Transform", "transform"), ("Shape", "shape"), ("Round Rect", "rounded_rect"), ("Pen", "pen"), ("Crop", "crop"), ("Brush", "brush"), ("Eraser", "eraser"), ("Text", "text"), ("Wand", "wand"), ("Lasso", "lasso"), ("Gradient", "gradient"), ("Clone", "clone"), ("💧Liquify", "liquify"), ("🎬Timeline", "timeline")]
        for label, mode in tools:
            b = tk.Radiobutton(self.toolbar, text=label, variable=self.current_tool, value=mode, bg="#3c3c3c", fg="white", selectcolor="#555555", indicatoron=0, width=11, command=self.on_tool_change)
            b.pack(pady=1, padx=5)

        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=5)
        self.make_tool_button("Open", self.open_image)
        self.make_tool_button("Crop Apply", self.apply_crop)
        self.make_tool_button("Smart Crop", self.auto_crop_content)
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=5)
        self.make_tool_button("90 Left", lambda: self.rotate_image(-90))
        self.make_tool_button("90 Right", lambda: self.rotate_image(90))
        self.make_tool_button("Flip H", lambda: self.flip_image("h"))
        self.make_tool_button("Flip V", lambda: self.flip_image("v"))
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=5)
        self.make_tool_button("New Layer", self.add_layer)
        self.make_tool_button("Add Mask", self.add_layer_mask)
        self.make_tool_button("Merge Down", self.merge_down)
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=5)
        self.make_tool_button("✨ AI Prompt", self.ai_prompt_dialog)
        self.make_tool_button("RM BG", self.ai_remove_background)
        self.make_tool_button("AI Fill", self.ai_fill_selection_with_prompt)
        self.make_tool_button("Shadow/HL", self.shadows_highlights_dialog)
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=4)
        self.make_tool_button("Zoom In", lambda: self.zoom_step(1.25))
        self.make_tool_button("Zoom Out", lambda: self.zoom_step(0.8))
        self.make_tool_button("Reset Zoom", self.reset_zoom)
        ttk.Separator(self.toolbar, orient='horizontal').pack(fill='x', padx=10, pady=4)
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
        self.canvas.bind("<Double-Button-1>", self.on_lasso_close)
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.zoom_step(1.1))
        self.canvas.bind("<Button-5>", lambda e: self.zoom_step(0.9))
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_drag)
        self.canvas.bind("<ButtonPress-3>", self.on_right_click)

        self.status_var = tk.StringVar(value="TIER 6B READY: Editable Text (double-click) + Shapes (rect/ellipse/line/arrow) + Canvas Handles (drag to resize) + Snap | TIER 6A + 6B")
        status_bar = tk.Label(center_frame, textvariable=self.status_var, anchor="w", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 9), padx=10, pady=4)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # RIGHT
        self.right_panel = tk.Frame(self.main_frame, bg="#2b2b2b", width=410)
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
        # Brush
        brush_frame = tk.LabelFrame(self.scrollable_frame, text="Brush / Eraser", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        brush_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(brush_frame, text="Size:", bg="#2b2b2b", fg="#cccccc").pack(anchor="w")
        tk.Scale(brush_frame, from_=1, to=100, orient="horizontal", variable=self.brush_size, bg="#2b2b2b", fg="white", highlightthickness=0, troughcolor="#555555").pack(fill="x")
        color_row = tk.Frame(brush_frame, bg="#2b2b2b")
        color_row.pack(fill="x", pady=4)
        tk.Label(color_row, text="Color:", bg="#2b2b2b", fg="#cccccc").pack(side="left")
        self.color_preview = tk.Label(color_row, bg=self.brush_color, width=3, relief="sunken")
        self.color_preview.pack(side="left", padx=6)
        tk.Button(color_row, text="Pick", command=self.pick_color, bg="#4a4a4a", fg="white", font=("Segoe UI", 8)).pack(side="left")
        tk.Button(brush_frame, text="Add Text...", command=self.add_text_dialog, bg="#4a7a9a", fg="white").pack(fill="x", pady=6)

        # Gradient (Tier4)
        grad_frame = tk.LabelFrame(self.scrollable_frame, text="Gradient Tool (Tier 4)", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        grad_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(grad_frame, text="Drag on canvas to create gradient", bg="#2b2b2b", fg="#aaaaaa", font=("Segoe UI", 7)).pack(anchor="w")
        grad_colors = tk.Frame(grad_frame, bg="#2b2b2b")
        grad_colors.pack(fill="x", pady=4)
        tk.Label(grad_colors, text="From:", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        self.grad_preview1 = tk.Label(grad_colors, bg=self.brush_color, width=3, relief="sunken")
        self.grad_preview1.pack(side="left", padx=3)
        tk.Button(grad_colors, text="Pick1", command=lambda: self.pick_gradient_color(1), bg="#4a4a4a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=2)
        tk.Label(grad_colors, text="To:", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left", padx=(8,0))
        self.grad_preview2 = tk.Label(grad_colors, bg=self.gradient_color2, width=3, relief="sunken")
        self.grad_preview2.pack(side="left", padx=3)
        tk.Button(grad_colors, text="Pick2", command=lambda: self.pick_gradient_color(2), bg="#4a4a4a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=2)
        type_row = tk.Frame(grad_frame, bg="#2b2b2b")
        type_row.pack(fill="x", pady=2)
        tk.Label(type_row, text="Type:", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        ttk.Radiobutton(type_row, text="Linear", variable=self.gradient_type, value="linear").pack(side="left", padx=4)
        ttk.Radiobutton(type_row, text="Radial", variable=self.gradient_type, value="radial").pack(side="left", padx=4)

        # Wand
        wand_frame = tk.LabelFrame(self.scrollable_frame, text="Wand + Selection", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        wand_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(wand_frame, text="Tolerance (0-100):", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8)).pack(anchor="w")
        tk.Scale(wand_frame, from_=0, to=100, orient="horizontal", variable=self.wand_tolerance, bg="#2b2b2b", fg="white", troughcolor="#555555", highlightthickness=0).pack(fill="x")
        tk.Checkbutton(wand_frame, text="Contiguous (flood fill)", variable=self.wand_contiguous, bg="#2b2b2b", fg="#cccccc", selectcolor="#3c3c3c").pack(anchor="w")
        btn_wand_row = tk.Frame(wand_frame, bg="#2b2b2b")
        btn_wand_row.pack(fill="x", pady=4)
        tk.Button(btn_wand_row, text="Delete Sel", command=lambda: self.apply_wand_delete(self._last_wand_mask) if self._last_wand_mask else None, bg="#9a4a4a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2)
        tk.Button(btn_wand_row, text="Clear Sel", command=self.clear_selection, bg="#4a4a4a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2)

        # Lasso + Feather
        lasso_frame = tk.LabelFrame(self.scrollable_frame, text="Lasso + Feather (Tier 3)", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        lasso_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(lasso_frame, text="Lasso: Draw freehand, double-click to close", bg="#2b2b2b", fg="#aaaaaa", font=("Segoe UI", 7)).pack(anchor="w")
        tk.Label(lasso_frame, text="Feather radius:", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8)).pack(anchor="w")
        tk.Scale(lasso_frame, from_=0, to=50, orient="horizontal", variable=self.feather_radius, bg="#2b2b2b", fg="white", troughcolor="#555555", highlightthickness=0).pack(fill="x")
        feather_row = tk.Frame(lasso_frame, bg="#2b2b2b")
        feather_row.pack(fill="x", pady=4)
        tk.Button(feather_row, text="Feather Sel", command=self.apply_feather, bg="#6a5a9a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2)
        tk.Button(feather_row, text="Invert Sel", command=self.invert_selection, bg="#4a4a4a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2)

        # Clone
        clone_frame = tk.LabelFrame(self.scrollable_frame, text="Clone Stamp (Alt+Click source)", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        clone_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(clone_frame, text="Alt+click to set source, then paint", bg="#2b2b2b", fg="#aaaaaa", font=("Segoe UI", 8)).pack(anchor="w")
        self.clone_label = tk.Label(clone_frame, text="Source: not set", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8))
        self.clone_label.pack(anchor="w")

        # Layers + Masks
        self.layers_frame = tk.LabelFrame(self.scrollable_frame, text="Layers + Masks", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        self.layers_frame.pack(fill="both", expand=False, padx=8, pady=6)
        self.layers_listbox = tk.Listbox(self.layers_frame, bg="#3c3c3c", fg="white", height=5, selectbackground="#5a5a5a")
        self.layers_listbox.pack(fill="x")
        self.layers_listbox.bind("<<ListboxSelect>>", self.on_layer_select)
        blend_row = tk.Frame(self.layers_frame, bg="#2b2b2b")
        blend_row.pack(fill="x", pady=4)
        tk.Label(blend_row, text="Blend:", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        self.blend_var = tk.StringVar(value="normal")
        blend_combo = ttk.Combobox(blend_row, textvariable=self.blend_var, values=["normal", "multiply", "screen", "overlay", "darken", "lighten"], width=10, state="readonly")
        blend_combo.pack(side="left", padx=4)
        blend_combo.bind("<<ComboboxSelected>>", self.on_blend_change)
        mask_row = tk.Frame(self.layers_frame, bg="#2b2b2b")
        mask_row.pack(fill="x", pady=4)
        tk.Button(mask_row, text="Add Mask", command=self.add_layer_mask, bg="#4a7a4a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2)
        tk.Button(mask_row, text="Del Mask", command=self.delete_layer_mask, bg="#9a4a4a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2)
        tk.Button(mask_row, text="Apply Mask", command=self.apply_layer_mask, bg="#4a4a4a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2)
        # TIER 6A: Layer reorder buttons
        reorder_row = tk.Frame(self.layers_frame, bg="#2b2b2b")
        reorder_row.pack(fill="x", pady=2)
        tk.Button(reorder_row, text="▲ Move Up", command=self.move_layer_up, bg="#4a5a8a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(reorder_row, text="▼ Move Down", command=self.move_layer_down, bg="#4a5a8a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2, fill="x", expand=True)
        # TIER 6A: Opacity slider
        opacity_row = tk.Frame(self.layers_frame, bg="#2b2b2b")
        opacity_row.pack(fill="x", pady=2)
        tk.Label(opacity_row, text="Opacity:", bg="#2b2b2b", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        tk.Scale(opacity_row, from_=0.0, to=1.0, resolution=0.05, orient="horizontal", variable=self.layer_opacity_var, bg="#2b2b2b", fg="white", troughcolor="#555555", highlightthickness=0, command=self.on_opacity_change, length=150).pack(side="left", fill="x", expand=True)
        tk.Checkbutton(self.layers_frame, text="Edit Mask (paint mask, not image)", variable=self.mask_edit_mode, bg="#2b2b2b", fg="#ffaa55", selectcolor="#3c3c3c", font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=2)
        self.mask_info = tk.Label(self.layers_frame, text="Mask: none", bg="#2b2b2b", fg="#aaaaaa", font=("Segoe UI", 7))
        self.mask_info.pack(anchor="w")

        # TIER 6A: Free Transform panel
        transform_frame = tk.LabelFrame(self.scrollable_frame, text="Free Transform (TIER 6A - NEW!)", bg="#2b1a1a", fg="#ffaa55", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        transform_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(transform_frame, text="Move layer, scale, rotate - like Photoshop Ctrl+T", bg="#2b1a1a", fg="#aaaaaa", font=("Segoe UI", 7)).pack(anchor="w")
        t_btn_row = tk.Frame(transform_frame, bg="#2b1a1a")
        t_btn_row.pack(fill="x", pady=4)
        tk.Button(t_btn_row, text="↔ Move Tool", command=lambda: self.enable_transform('move'), bg="#8a5a4a", fg="white", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(t_btn_row, text="Free Transform", command=self.free_transform_dialog, bg="#ff6a4a", fg="white", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2, fill="x", expand=True)
        t_btn_row2 = tk.Frame(transform_frame, bg="#2b1a1a")
        t_btn_row2.pack(fill="x", pady=2)
        tk.Button(t_btn_row2, text="Reset Transform", command=self.reset_transform, bg="#4a4a4a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(t_btn_row2, text="Center Layer", command=self.center_layer, bg="#4a4a4a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=2, fill="x", expand=True)

        # TIER 6B: Shapes + Editable Text + Canvas Handles
        shape_frame = tk.LabelFrame(self.scrollable_frame, text="TIER 6B: Shapes + Editable Text + Handles", bg="#1a2b1a", fg="#55ff55", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        shape_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(shape_frame, text="Vector shapes & re-editable text", bg="#1a2b1a", fg="#aaaaaa", font=("Segoe UI", 7)).pack(anchor="w")
        # Shape type selector
        shape_type_row = tk.Frame(shape_frame, bg="#1a2b1a")
        shape_type_row.pack(fill="x", pady=2)
        tk.Label(shape_type_row, text="Shape:", bg="#1a2b1a", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        ttk.Combobox(shape_type_row, textvariable=self.shape_type, values=["rectangle", "ellipse", "line", "arrow", "polygon", "star"], width=10, state="readonly").pack(side="left", padx=4)
        # Fill / Stroke
        fill_row = tk.Frame(shape_frame, bg="#1a2b1a")
        fill_row.pack(fill="x", pady=2)
        tk.Label(fill_row, text="Fill:", bg="#1a2b1a", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        tk.Button(fill_row, text="■", bg=self.shape_fill, fg="white", width=2, command=lambda: self.pick_shape_color("fill")).pack(side="left", padx=2)
        tk.Label(fill_row, text="Stroke:", bg="#1a2b1a", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left", padx=(6,2))
        tk.Button(fill_row, text="■", bg=self.shape_stroke, fg="white", width=2, command=lambda: self.pick_shape_color("stroke")).pack(side="left", padx=2)
        tk.Label(fill_row, text="W:", bg="#1a2b1a", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left", padx=(4,2))
        tk.Scale(fill_row, from_=1, to=20, orient="horizontal", variable=self.shape_stroke_width, bg="#1a2b1a", fg="white", troughcolor="#555555", highlightthickness=0, length=60).pack(side="left")
        # Text controls
        text_ctrl_row = tk.Frame(shape_frame, bg="#1a2b1a")
        text_ctrl_row.pack(fill="x", pady=4)
        tk.Label(text_ctrl_row, text="Font Size:", bg="#1a2b1a", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        tk.Scale(text_ctrl_row, from_=10, to=200, orient="horizontal", variable=self.text_font_size, bg="#1a2b1a", fg="white", troughcolor="#555555", highlightthickness=0, length=80).pack(side="left")
        tk.Button(text_ctrl_row, text="Bold", command=lambda: self.text_bold.set(not self.text_bold.get()), bg="#4a6a4a", fg="white", font=("Segoe UI", 7, "bold")).pack(side="left", padx=2)
        tk.Button(text_ctrl_row, text="Italic", command=lambda: self.text_italic.set(not self.text_italic.get()), bg="#4a6a4a", fg="white", font=("Segoe UI", 7, "italic")).pack(side="left", padx=2)
        # Handles & Snap
        handle_row = tk.Frame(shape_frame, bg="#1a2b1a")
        handle_row.pack(fill="x", pady=2)
        tk.Checkbutton(handle_row, text="Show Handles", variable=self.show_transform_handles, bg="#1a2b1a", fg="#55ff55", selectcolor="#2a4a2a", font=("Segoe UI", 8)).pack(side="left")
        tk.Checkbutton(handle_row, text="Snap Center", variable=self.snap_enabled, bg="#1a2b1a", fg="#55ff55", selectcolor="#2a4a2a", font=("Segoe UI", 8)).pack(side="left", padx=8)
        # Text layer edit
        text_edit_row = tk.Frame(shape_frame, bg="#1a2b1a")
        text_edit_row.pack(fill="x", pady=2)
        tk.Button(text_edit_row, text="✏️ Edit Text Layer", command=self.edit_text_layer_dialog, bg="#5a8a5a", fg="white", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(text_edit_row, text="🔄 Redraw Shape", command=self.redraw_shape_layer, bg="#4a6a8a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2, fill="x", expand=True)

        # TIER 6C: Font Picker + Alignment + Rounded Rect + Pen Tool + Lock
        tier6c_frame = tk.LabelFrame(self.scrollable_frame, text="TIER 6C: Font Picker + Align + Round Rect + Pen + Lock", bg="#2b1a2b", fg="#ff55ff", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        tier6c_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(tier6c_frame, text="Photoshop style text + advanced handles", bg="#2b1a2b", fg="#aaaaaa", font=("Segoe UI", 7)).pack(anchor="w")
        # Font family picker
        font_row = tk.Frame(tier6c_frame, bg="#2b1a2b")
        font_row.pack(fill="x", pady=2)
        tk.Label(font_row, text="Font:", bg="#2b1a2b", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        ttk.Combobox(font_row, textvariable=self.text_font_family, values=self.common_fonts, width=14, state="readonly").pack(side="left", padx=4)
        # Alignment
        align_row = tk.Frame(tier6c_frame, bg="#2b1a2b")
        align_row.pack(fill="x", pady=2)
        tk.Label(align_row, text="Align:", bg="#2b1a2b", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        for a in ["left", "center", "right"]:
            tk.Radiobutton(align_row, text=a.title(), variable=self.text_align, value=a, bg="#2b1a2b", fg="#ff88ff", selectcolor="#4a2a4a", font=("Segoe UI", 7), indicatoron=0, width=6).pack(side="left", padx=1)
        # Line spacing + Letter spacing
        spacing_row = tk.Frame(tier6c_frame, bg="#2b1a2b")
        spacing_row.pack(fill="x", pady=2)
        tk.Label(spacing_row, text="Line:", bg="#2b1a2b", fg="#cccccc", font=("Segoe UI", 7)).pack(side="left")
        tk.Scale(spacing_row, from_=0.8, to=2.5, resolution=0.1, orient="horizontal", variable=self.text_line_spacing, bg="#2b1a2b", fg="white", troughcolor="#555555", highlightthickness=0, length=50).pack(side="left", padx=2)
        tk.Label(spacing_row, text="Letter:", bg="#2b1a2b", fg="#cccccc", font=("Segoe UI", 7)).pack(side="left", padx=(4,0))
        tk.Scale(spacing_row, from_=0, to=20, orient="horizontal", variable=self.text_letter_spacing, bg="#2b1a2b", fg="white", troughcolor="#555555", highlightthickness=0, length=50).pack(side="left", padx=2)
        # Rounded rect radius
        round_row = tk.Frame(tier6c_frame, bg="#2b1a2b")
        round_row.pack(fill="x", pady=2)
        tk.Label(round_row, text="Round Radius:", bg="#2b1a2b", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        tk.Scale(round_row, from_=0, to=100, orient="horizontal", variable=self.shape_corner_radius, bg="#2b1a2b", fg="white", troughcolor="#555555", highlightthickness=0, length=100).pack(side="left", padx=4)
        tk.Button(round_row, text="Rounded Rect", command=lambda: self.current_tool.set("rounded_rect"), bg="#8a4a8a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=4)
        # Shift/Alt handles
        handle6c_row = tk.Frame(tier6c_frame, bg="#2b1a2b")
        handle6c_row.pack(fill="x", pady=2)
        tk.Checkbutton(handle6c_row, text="Shift=Lock Aspect", variable=self.lock_aspect_ratio, bg="#2b1a2b", fg="#ff88ff", selectcolor="#4a2a4a", font=("Segoe UI", 7)).pack(side="left")
        tk.Checkbutton(handle6c_row, text="Alt=From Center", variable=self.scale_from_center, bg="#2b1a2b", fg="#ff88ff", selectcolor="#4a2a4a", font=("Segoe UI", 7)).pack(side="left", padx=6)
        # Layer lock + duplicate + pen
        layer6c_row = tk.Frame(tier6c_frame, bg="#2b1a2b")
        layer6c_row.pack(fill="x", pady=2)
        tk.Button(layer6c_row, text="🔒 Lock Layer", command=self.lock_layer, bg="#7a4a7a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(layer6c_row, text="📋 Duplicate +20px", command=self.duplicate_layer_offset, bg="#6a4a7a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=2, fill="x", expand=True)
        pen_row = tk.Frame(tier6c_frame, bg="#2b1a2b")
        pen_row.pack(fill="x", pady=2)
        tk.Button(pen_row, text="✒️ Pen Tool (Click to add points)", command=lambda: self.current_tool.set("pen"), bg="#aa55aa", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(pen_row, text="Close Path", command=self.on_pen_close, bg="#cc77cc", fg="black", font=("Segoe UI", 7, "bold")).pack(side="left", padx=2)
        # Export PSD
        export_row = tk.Frame(tier6c_frame, bg="#2b1a2b")
        export_row.pack(fill="x", pady=2)
        tk.Button(export_row, text="💾 Export Layers as PNG Sequence", command=self.export_psd_layers, bg="#aa66aa", fg="white", font=("Segoe UI", 8, "bold")).pack(fill="x")

        # TIER 7: Layer Styles + Groups + Real PSD + True Blend
        tier7_frame = tk.LabelFrame(self.scrollable_frame, text="TIER 7: Layer Styles + Real PSD + Groups + Blend (NEW!)", bg="#1a1a2b", fg="#ffaa55", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        tier7_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(tier7_frame, text="Photoshop-style Layer Styles & Groups", bg="#1a1a2b", fg="#aaaaaa", font=("Segoe UI", 7)).pack(anchor="w")
        # Layer Styles button
        tk.Button(tier7_frame, text="✨ Layer Styles Dialog (Shadow/Glow/Stroke)", command=self.layer_styles_dialog, bg="#ff8c00", fg="black", font=("Segoe UI", 9, "bold")).pack(fill="x", pady=3)
        # Quick styles
        quick_row = tk.Frame(tier7_frame, bg="#1a1a2b")
        quick_row.pack(fill="x", pady=2)
        tk.Button(quick_row, text="Drop Shadow", command=lambda: self.quick_style("drop_shadow"), bg="#4a3a2a", fg="#ffaa55", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(quick_row, text="Outer Glow", command=lambda: self.quick_style("outer_glow"), bg="#4a3a2a", fg="#ffaa55", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(quick_row, text="Stroke", command=lambda: self.quick_style("stroke"), bg="#4a3a2a", fg="#ffaa55", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        quick_row2 = tk.Frame(tier7_frame, bg="#1a1a2b")
        quick_row2.pack(fill="x", pady=2)
        tk.Button(quick_row2, text="Color Overlay", command=lambda: self.quick_style("color_overlay"), bg="#4a3a2a", fg="#ffaa55", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(quick_row2, text="Clear Styles", command=self.clear_layer_styles, bg="#5a2a2a", fg="#ff6666", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        # Real PSD export
        psd_row = tk.Frame(tier7_frame, bg="#1a1a2b")
        psd_row.pack(fill="x", pady=3)
        tk.Button(psd_row, text="💾 Export REAL PSD (psd-tools)", command=self.export_psd_layers, bg="#ffaa55", fg="black", font=("Segoe UI", 8, "bold")).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(psd_row, text="PNG Seq", command=lambda: self.export_png_sequence(filedialog.askdirectory(title="Export folder") or "."), bg="#4a4a6a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=2)
        # Groups
        group_row = tk.Frame(tier7_frame, bg="#1a1a2b")
        group_row.pack(fill="x", pady=2)
        tk.Button(group_row, text="📁 New Group", command=self.create_group_layer, bg="#3a3a6a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(group_row, text="Add to Group", command=self.add_to_group, bg="#4a4a7a", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(group_row, text="Ungroup", command=self.ungroup_layer, bg="#6a4a4a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=2)
        # Blend modes extended
        blend7_row = tk.Frame(tier7_frame, bg="#1a1a2b")
        blend7_row.pack(fill="x", pady=2)
        tk.Label(blend7_row, text="Blend:", bg="#1a1a2b", fg="#cccccc", font=("Segoe UI", 7)).pack(side="left")
        self.blend_var7 = self.blend_var  # reuse
        ttk.Combobox(blend7_row, textvariable=self.blend_var, values=["normal", "multiply", "screen", "overlay", "soft_light", "hard_light", "color_dodge", "color_burn", "darken", "lighten", "difference"], width=12, state="readonly", font=("Segoe UI", 7)).pack(side="left", padx=4)

        # TIER 8: Filters + Liquify + Smart Objects + Timeline (ALL)
        tier8_frame = tk.LabelFrame(self.scrollable_frame, text="TIER 8: Filters + Liquify + Smart Objects + Timeline + Adj Layers (ALL NEW!)", bg="#2b1a0a", fg="#ffcc00", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        tier8_frame.pack(fill="x", padx=8, pady=6)
        tk.Label(tier8_frame, text="Pro Filters + Non-Destructive + Animation", bg="#2b1a0a", fg="#aaaaaa", font=("Segoe UI", 7)).pack(anchor="w")

        # Row 1: Filter Gallery
        tk.Button(tier8_frame, text="🎨 Filter Gallery (Blur/Distort/Stylize)", command=self.filter_gallery_dialog, bg="#ffcc00", fg="black", font=("Segoe UI", 9, "bold")).pack(fill="x", pady=3)
        f8_row1 = tk.Frame(tier8_frame, bg="#2b1a0a")
        f8_row1.pack(fill="x", pady=2)
        tk.Button(f8_row1, text="Gaussian Blur", command=self.gaussian_blur_dialog, bg="#4a3a1a", fg="#ffcc88", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(f8_row1, text="Motion Blur", command=self.motion_blur_dialog, bg="#4a3a1a", fg="#ffcc88", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(f8_row1, text="Unsharp", command=self.unsharp_mask_dialog, bg="#4a3a1a", fg="#ffcc88", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)

        f8_row2 = tk.Frame(tier8_frame, bg="#2b1a0a")
        f8_row2.pack(fill="x", pady=2)
        tk.Button(f8_row2, text="Oil Paint", command=self.oil_paint_dialog, bg="#5a3a1a", fg="#ffcc88", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(f8_row2, text="Wave", command=self.wave_distort_dialog, bg="#5a3a1a", fg="#ffcc88", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(f8_row2, text="Twirl", command=self.twirl_dialog, bg="#5a3a1a", fg="#ffcc88", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(f8_row2, text="Pixelate", command=self.pixelate_dialog, bg="#5a3a1a", fg="#ffcc88", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)

        # Row 3: Liquify
        liq_frame = tk.LabelFrame(tier8_frame, text="Liquify Brush (Push/Bloat/Pucker/Twirl)", bg="#2b1a0a", fg="#ffaa00", font=("Segoe UI", 8, "bold"))
        liq_frame.pack(fill="x", pady=4)
        tk.Button(liq_frame, text="💧 Liquify Tool", command=lambda: self.current_tool.set("liquify"), bg="#ff8800", fg="black", font=("Segoe UI", 8, "bold")).pack(fill="x", pady=2)
        liq_ctrl = tk.Frame(liq_frame, bg="#2b1a0a")
        liq_ctrl.pack(fill="x")
        tk.Label(liq_ctrl, text="Size:", bg="#2b1a0a", fg="#cccccc", font=("Segoe UI", 7)).pack(side="left")
        tk.Scale(liq_ctrl, from_=10, to=200, orient="horizontal", variable=tk.IntVar(value=self.liquify_size), command=lambda v: setattr(self, 'liquify_size', int(float(v))), bg="#2b1a0a", fg="white", troughcolor="#555555", highlightthickness=0, length=60).pack(side="left", padx=2)
        tk.Label(liq_ctrl, text="Str:", bg="#2b1a0a", fg="#cccccc", font=("Segoe UI", 7)).pack(side="left")
        tk.Scale(liq_ctrl, from_=1, to=100, orient="horizontal", variable=tk.IntVar(value=self.liquify_strength), command=lambda v: setattr(self, 'liquify_strength', int(float(v))), bg="#2b1a0a", fg="white", troughcolor="#555555", highlightthickness=0, length=60).pack(side="left", padx=2)
        liq_mode_row = tk.Frame(liq_frame, bg="#2b1a0a")
        liq_mode_row.pack(fill="x", pady=2)
        for mode in ["push", "bloat", "pucker", "twirl"]:
            tk.Radiobutton(liq_mode_row, text=mode.capitalize(), variable=self.liquify_mode, value=mode, bg="#2b1a0a", fg="#ffcc88", selectcolor="#4a2a0a", font=("Segoe UI", 7)).pack(side="left", padx=2)

        # Row 4: Smart Objects + Adj Layers
        smart_frame = tk.LabelFrame(tier8_frame, text="Smart Objects + Adjustment Layers", bg="#2b1a0a", fg="#ffaa00", font=("Segoe UI", 8, "bold"))
        smart_frame.pack(fill="x", pady=4)
        s_row1 = tk.Frame(smart_frame, bg="#2b1a0a")
        s_row1.pack(fill="x", pady=1)
        tk.Button(s_row1, text="🧠 Convert to Smart Object", command=self.convert_to_smart_object, bg="#3a2a5a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(s_row1, text="Edit Smart Obj", command=self.edit_smart_object, bg="#4a3a6a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        s_row2 = tk.Frame(smart_frame, bg="#2b1a0a")
        s_row2.pack(fill="x", pady=1)
        for adj in ["brightness_contrast", "levels", "hue_sat", "color_balance"]:
            tk.Button(s_row2, text=adj[:6], command=lambda a=adj: self.add_adjustment_layer(a), bg="#4a3a2a", fg="#ffcc88", font=("Segoe UI", 6)).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(s_row2, text="Clear Filters", command=self.clear_smart_filters, bg="#5a2a2a", fg="#ff6666", font=("Segoe UI", 6)).pack(side="left", padx=1)

        # Row 5: Timeline
        tl_frame = tk.LabelFrame(tier8_frame, text="Timeline / GIF Animation", bg="#2b1a0a", fg="#ffaa00", font=("Segoe UI", 8, "bold"))
        tl_frame.pack(fill="x", pady=4)
        tl_ctrl = tk.Frame(tl_frame, bg="#2b1a0a")
        tl_ctrl.pack(fill="x")
        tk.Button(tl_ctrl, text="➕ Add Frame", command=self.timeline_add_frame, bg="#4a5a2a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        tk.Button(tl_ctrl, text="▶ Play", command=self.timeline_play, bg="#2a5a2a", fg="white", font=("Segoe UI", 7, "bold")).pack(side="left", padx=1)
        tk.Button(tl_ctrl, text="⏹ Stop", command=self.timeline_stop, bg="#5a2a2a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=1)
        tk.Button(tl_ctrl, text="💾 Export GIF", command=self.timeline_export_dialog, bg="#2a4a6a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=1, fill="x", expand=True)
        fps_row = tk.Frame(tl_frame, bg="#2b1a0a")
        fps_row.pack(fill="x", pady=2)
        tk.Label(fps_row, text="FPS:", bg="#2b1a0a", fg="#cccccc", font=("Segoe UI", 7)).pack(side="left")
        tk.Scale(fps_row, from_=1, to=30, orient="horizontal", variable=self.timeline_fps, bg="#2b1a0a", fg="white", troughcolor="#555555", highlightthickness=0, length=80).pack(side="left", padx=4)
        self.timeline_label = tk.Label(fps_row, text="Frames: 0", bg="#2b1a0a", fg="#ffcc00", font=("Segoe UI", 7))
        self.timeline_label.pack(side="left", padx=8)


        # Shadows/Highlights Tier4
        sh_frame = tk.LabelFrame(self.scrollable_frame, text="Shadows/Highlights + Vignette (Tier 4)", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        sh_frame.pack(fill="x", padx=8, pady=6)
        tk.Button(sh_frame, text="Shadows/Highlights...", command=self.shadows_highlights_dialog, bg="#7a6a4a", fg="white").pack(fill="x", pady=2)
        tk.Button(sh_frame, text="Vignette...", command=self.vignette_dialog, bg="#4a4a7a", fg="white").pack(fill="x", pady=2)
        tk.Button(sh_frame, text="Auto Crop Content", command=self.auto_crop_content, bg="#4a7a4a", fg="white").pack(fill="x", pady=2)

        # AI Prompt Generator (Tier 4.5)
        ai_prompt_frame = tk.LabelFrame(self.scrollable_frame, text="AI Prompt Generator (NEW! Tier 4.5)", bg="#1a2a3a", fg="#7ab8ff", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        ai_prompt_frame.pack(fill="x", padx=8, pady=8)
        tk.Label(ai_prompt_frame, text="Describe what to generate:", bg="#1a2a3a", fg="#7ab8ff", font=("Segoe UI", 8, "bold")).pack(anchor="w")
        prompt_entry = tk.Entry(ai_prompt_frame, textvariable=self.ai_prompt, bg="#2a3a4a", fg="white", font=("Segoe UI", 9), insertbackground="white")
        prompt_entry.pack(fill="x", pady=3)
        tk.Label(ai_prompt_frame, text="Style:", bg="#1a2a3a", fg="#cccccc", font=("Segoe UI", 7)).pack(anchor="w")
        style_combo = ttk.Combobox(ai_prompt_frame, textvariable=self.ai_style, values=["Realistic", "Digital Art", "Anime", "Oil Painting", "Cyberpunk", "Fantasy", "Minimal"], width=20, state="readonly")
        style_combo.pack(fill="x", pady=2)
        size_row = tk.Frame(ai_prompt_frame, bg="#1a2a3a")
        size_row.pack(fill="x", pady=2)
        tk.Label(size_row, text="Size:", bg="#1a2a3a", fg="#cccccc", font=("Segoe UI", 8)).pack(side="left")
        tk.Entry(size_row, textvariable=self.ai_prompt_width, width=5, bg="#2a3a4a", fg="white").pack(side="left", padx=2)
        tk.Label(size_row, text="x", bg="#1a2a3a", fg="#cccccc").pack(side="left")
        tk.Entry(size_row, textvariable=self.ai_prompt_height, width=5, bg="#2a3a4a", fg="white").pack(side="left", padx=2)
        btn_row_ai = tk.Frame(ai_prompt_frame, bg="#1a2a3a")
        btn_row_ai.pack(fill="x", pady=4)
        tk.Button(btn_row_ai, text="✨ Generate", command=self.ai_prompt_dialog, bg="#5a8aff", fg="white", font=("Segoe UI", 9, "bold")).pack(side="left", padx=2, fill="x", expand=True)
        tk.Button(btn_row_ai, text="Fill Sel", command=self.ai_fill_selection_with_prompt, bg="#7a5aff", fg="white", font=("Segoe UI", 8)).pack(side="left", padx=2)


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

        zoom_frame = tk.LabelFrame(self.scrollable_frame, text="View", bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
        zoom_frame.pack(fill="x", padx=8, pady=6)
        self.zoom_label = tk.Label(zoom_frame, text="Zoom: 100%", bg="#2b2b2b", fg="#aaaaaa", font=("Segoe UI", 8))
        self.zoom_label.pack(anchor="w")

    def make_tool_button(self, text, command):
        btn = tk.Button(self.toolbar, text=text, command=command, bg="#4a4a4a", fg="white", font=("Segoe UI", 7), relief="flat", padx=4, pady=2)
        btn.pack(pady=1, padx=5, fill="x")

    def on_tool_change(self):
        tool = self.current_tool.get()
        # Reset transform undo flag when switching tools
        if tool not in ("move", "transform"):
            self._transform_undo_pushed = False
        if tool in ("move", "transform"):
            self.status_var.set(f"TIER 6B: Drag to move | Handles to resize/rotate | Ctrl+T dialog | Shape/Text editable | Snap enabled")
        elif tool == "shape":
            self.status_var.set(f"TIER 6B Shape Tool: Drag on canvas to create {self.shape_type.get()} | Fill {self.shape_fill} Stroke {self.shape_stroke}")
        elif tool == "text":
            self.status_var.set(f"TIER 6B Editable Text: Click to place, double-click layer to re-edit | Size {self.text_font_size.get()} Bold={self.text_bold.get()}")
        else:
            self.status_var.set(f"Tool: {tool} | Zoom {int(self.zoom*100)}% | Colors: {self.brush_color} -> {self.gradient_color2}")
        cursors = {"select": "arrow", "move": "fleur", "transform": "sizing", "shape": "crosshair", "crop": "crosshair", "brush": "pencil", "eraser": "dotbox", "text": "xterm", "wand": "tcross", "lasso": "crosshair", "gradient": "crosshair", "clone": "crosshair"}
        self.canvas.config(cursor=cursors.get(tool, "crosshair"))
        if tool != "lasso":
            self.clear_lasso_visual()
        self.display_composite()

    def exit_transform(self):
        self.current_tool.set("select")
        self.transform_active = False
        self._transform_undo_pushed = False
        self.on_tool_change()

    def bind_shortcuts(self):
        self.root.bind("<Control-o>", lambda e: self.open_image())
        self.root.bind("<Control-s>", lambda e: self.save_as())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<Control-l>", lambda e: self.add_layer())
        self.root.bind("<Control-e>", lambda e: self.merge_down())
        self.root.bind("<Control-b>", lambda e: self.ai_remove_background())
        self.root.bind("<Control-g>", lambda e: self.ai_prompt_dialog())
        self.root.bind("<Control-t>", lambda e: self.free_transform_dialog())
        self.root.bind("<Control-m>", lambda e: self.enable_transform('move'))
        self.root.bind("<Delete>", lambda e: self.delete_layer())
        self.root.bind("<Escape>", lambda e: self.exit_transform())

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
            mask_txt = " [MASK]" if l.mask is not None else ""
            lock_txt = " 🔒" if l.locked else ""
            type_txt = ""
            if l.is_text_layer:
                type_txt = " [T]"
            elif l.is_shape_layer:
                type_txt = f" [S:{l.shape_data.get('type','?')[:4]}]" if l.shape_data else " [S]"
            self.layers_listbox.insert(tk.END, f"{l.name}{type_txt}{lock_txt}{sel}{mask_txt} {'(hidden)' if not l.visible else ''}")
        if self.layers:
            rev_idx = len(self.layers)-1 - self.active_layer_idx
            self.layers_listbox.selection_clear(0, tk.END)
            self.layers_listbox.selection_set(rev_idx)
            active = self.layers[self.active_layer_idx]
            if active.mask is not None:
                self.mask_info.config(text=f"Mask: {active.mask.size[0]}x{active.mask.size[1]} | EditMode={self.mask_edit_mode.get()}")
            else:
                self.mask_info.config(text="Mask: none")

    def on_blend_change(self, e):
        if not self.layers:
            return
        self.push_undo(f"Blend {self.blend_var.get()}")
        self.layers[self.active_layer_idx].blend_mode = self.blend_var.get()
        self.display_composite()

    # ========== TIER 6A: Layer Reordering & Opacity & Transform ==========
    def move_layer_up(self):
        if not self.layers or self.active_layer_idx >= len(self.layers)-1:
            return
        self.push_undo("Move layer up")
        idx = self.active_layer_idx
        self.layers[idx], self.layers[idx+1] = self.layers[idx+1], self.layers[idx]
        self.active_layer_idx += 1
        self.refresh_layers_list()
        self.display_composite()
        self.status_var.set(f"Moved layer up to position {self.active_layer_idx}")

    def move_layer_down(self):
        if not self.layers or self.active_layer_idx <= 0:
            return
        self.push_undo("Move layer down")
        idx = self.active_layer_idx
        self.layers[idx], self.layers[idx-1] = self.layers[idx-1], self.layers[idx]
        self.active_layer_idx -= 1
        self.refresh_layers_list()
        self.display_composite()
        self.status_var.set(f"Moved layer down to position {self.active_layer_idx}")

    def on_opacity_change(self, value=None):
        if not self.layers:
            return
        try:
            op = float(value) if value is not None else self.layer_opacity_var.get()
            self.layers[self.active_layer_idx].opacity = op
            self.display_composite()
        except:
            pass

    def on_layer_select(self, e):
        sel = self.layers_listbox.curselection()
        if not sel:
            return
        rev_idx = sel[0]
        self.active_layer_idx = len(self.layers)-1 - rev_idx
        if self.layers:
            self.blend_var.set(self.layers[self.active_layer_idx].blend_mode)
            self.layer_opacity_var.set(self.layers[self.active_layer_idx].opacity)
        self.refresh_layers_list()
        self.display_composite()

    def enable_transform(self, mode='move'):
        if not self.layers:
            return
        self.current_tool.set('transform')
        self.transform_active = True
        self.transform_handle = mode
        self.status_var.set(f"TIER 6A Transform: {mode} mode - Drag on canvas to move/scale active layer. Press Esc to exit, Enter to apply.")
        self.on_tool_change()

    def reset_transform(self):
        if not self.layers:
            return
        self.push_undo("Reset transform")
        layer = self.layers[self.active_layer_idx]
        layer.offset_x = 0
        layer.offset_y = 0
        layer.scale_x = 1.0
        layer.scale_y = 1.0
        layer.rotation = 0.0
        self.display_composite()
        self.status_var.set("Transform reset")

    def center_layer(self):
        if not self.layers:
            return
        self.push_undo("Center layer")
        layer = self.layers[self.active_layer_idx]
        # Center calculation: (base_size - layer_size) // 2
        if len(self.layers) > 0:
            base_w, base_h = self.layers[0].image.size
            img = layer.get_transformed_image()
            lw, lh = img.size
            layer.offset_x = (base_w - lw) // 2
            layer.offset_y = (base_h - lh) // 2
        self.display_composite()

    def center_layer(self):
        if not self.layers:
            return
        self.push_undo("Center layer")
        layer = self.layers[self.active_layer_idx]
        # Center calculation: (base_size - layer_size) // 2
        if len(self.layers) > 0:
            base_w, base_h = self.layers[0].image.size
            img = layer.get_transformed_image()
            lw, lh = img.size
            layer.offset_x = (base_w - lw) // 2
            layer.offset_y = (base_h - lh) // 2
        self.display_composite()

    # ========== TIER 6B: Editable Text + Shapes + Canvas Handles ==========
    def pick_shape_color(self, which):
        color = colorchooser.askcolor()[1]
        if not color:
            return
        if which == "fill":
            self.shape_fill = color
        else:
            self.shape_stroke = color
        self.status_var.set(f"Shape {which} = {color}")

    def create_text_image(self, text, font_size, color, font_family="Arial", bold=False, italic=False, stroke_width=0, stroke_color="#000000"):
        """TIER 6B: Create text image that can be re-edited"""
        # Estimate size
        w = max(200, len(text) * font_size // 2 + 40)
        h = font_size + 60
        # Handle multiline
        lines = text.split('\n')
        h = len(lines) * (font_size + 10) + 40
        w = max([len(line) * font_size // 2 + 40 for line in lines] + [w])
        img = Image.new("RGBA", (w, h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        try:
            # Try to load truetype
            font_style = ""
            if bold and italic:
                font_style = "Bold Italic"
            elif bold:
                font_style = "Bold"
            elif italic:
                font_style = "Italic"
            # Try common fonts
            font = None
            for fname in [f"{font_family}.ttf", f"{font_family} {font_style}.ttf", "arial.ttf", "DejaVuSans.ttf"]:
                try:
                    font = ImageFont.truetype(fname, font_size)
                    break
                except:
                    continue
            if font is None:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        # Draw stroke if needed
        y = 20
        for line in lines:
            if stroke_width > 0:
                # Stroke by drawing offset copies
                for dx in range(-stroke_width, stroke_width+1):
                    for dy in range(-stroke_width, stroke_width+1):
                        if dx==0 and dy==0:
                            continue
                        draw.text((20+dx, y+dy), line, font=font, fill=stroke_color)
            draw.text((20, y), line, font=font, fill=color)
            y += font_size + 10
        # Auto-crop to content
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        return img

    def add_text_layer(self, text, x=None, y=None):
        """TIER 6B + 6C: Add editable text layer with alignment"""
        if not self.layers:
            w,h = 800,600
            base = Image.new("RGBA", (w,h), (255,255,255,255))
            self.layers = [Layer("Background", base)]
        else:
            w,h = self.layers[0].image.size
        font_size = self.text_font_size.get()
        # TIER 6C: Use v6c method with alignment, spacing
        try:
            img = self.create_text_image_v6c(text, font_size, self.text_color, self.text_font_family.get(), self.text_bold.get(), self.text_italic.get(), self.text_stroke_width.get(), self.text_stroke_color, self.text_align.get(), self.text_line_spacing.get(), self.text_letter_spacing.get())
        except:
            img = self.create_text_image(text, font_size, self.text_color, self.text_font_family.get(), self.text_bold.get(), self.text_italic.get(), self.text_stroke_width.get(), self.text_stroke_color)
        self.push_undo(f"Add text: {text[:20]}")
        layer = Layer(f"Text: {text[:15]}", img)
        layer.is_text_layer = True
        layer.text_data = {
            "text": text,
            "font_size": font_size,
            "color": self.text_color,
            "font_family": self.text_font_family.get(),
            "bold": self.text_bold.get(),
            "italic": self.text_italic.get(),
            "stroke": self.text_stroke_width.get(),
            "stroke_color": self.text_stroke_color,
            "align": self.text_align.get(),
            "line_spacing": self.text_line_spacing.get(),
            "letter_spacing": self.text_letter_spacing.get()
        }
        layer.text_align = self.text_align.get()
        layer.line_spacing = self.text_line_spacing.get()
        layer.letter_spacing = self.text_letter_spacing.get()
        if x is not None and y is not None:
            layer.offset_x = x
            layer.offset_y = y
        else:
            # Center
            layer.offset_x = (w - img.size[0]) // 2
            layer.offset_y = (h - img.size[1]) // 2
        self.layers.append(layer)
        self.active_layer_idx = len(self.layers)-1
        self.refresh_layers_list()
        self.display_composite()
        return layer

    def edit_text_layer_dialog(self):
        """TIER 6B: Re-edit existing text layer"""
        if not self.layers:
            return
        layer = self.layers[self.active_layer_idx]
        if not layer.is_text_layer or not layer.text_data:
            # If not text layer, prompt for new text
            text = simpledialog.askstring("Add Text (TIER 6B)", "Enter text for new editable text layer:")
            if text:
                self.add_text_layer(text)
            return

        # Edit existing
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Edit Text Layer - {layer.name} (TIER 6B)")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#1a2b1a")

        tk.Label(dialog, text="Edit Text (Re-editable!)", font=("Segoe UI", 12, "bold"), bg="#1a2b1a", fg="#55ff55").pack(pady=10)

        text_var = tk.StringVar(value=layer.text_data.get("text",""))
        tk.Label(dialog, text="Text:", bg="#1a2b1a", fg="white").pack(anchor="w", padx=10)
        text_entry = tk.Text(dialog, height=4, bg="#2a4a2a", fg="white", font=("Segoe UI", 11))
        text_entry.insert("1.0", layer.text_data.get("text",""))
        text_entry.pack(fill="x", padx=10, pady=5)

        # Font size
        size_row = tk.Frame(dialog, bg="#1a2b1a")
        size_row.pack(fill="x", padx=10, pady=5)
        tk.Label(size_row, text="Font Size:", bg="#1a2b1a", fg="white").pack(side="left")
        size_var = tk.IntVar(value=layer.text_data.get("font_size", 48))
        tk.Scale(size_row, from_=10, to=200, variable=size_var, orient="horizontal", bg="#1a2b1a", fg="white", length=200).pack(side="left", padx=10)

        # Color
        color_row = tk.Frame(dialog, bg="#1a2b1a")
        color_row.pack(fill="x", padx=10, pady=5)
        tk.Label(color_row, text="Color:", bg="#1a2b1a", fg="white").pack(side="left")
        color_var = tk.StringVar(value=layer.text_data.get("color", "#ffffff"))
        def pick_color():
            c = colorchooser.askcolor(color_var.get())[1]
            if c:
                color_var.set(c)
        tk.Button(color_row, text="Pick Color", command=pick_color, bg="#4a6a4a", fg="white").pack(side="left", padx=10)
        tk.Label(color_row, textvariable=color_var, bg="#1a2b1a", fg="white").pack(side="left")

        def on_apply():
            new_text = text_entry.get("1.0", "end-1c")
            if not new_text.strip():
                return
            self.push_undo(f"Edit text: {new_text[:20]}")
            # Recreate image
            new_img = self.create_text_image(new_text, size_var.get(), color_var.get(), layer.text_data.get("font_family","Arial"), layer.text_data.get("bold",False), layer.text_data.get("italic",False), layer.text_data.get("stroke",0), layer.text_data.get("stroke_color","#000000"))
            layer.image = new_img
            layer.text_data["text"] = new_text
            layer.text_data["font_size"] = size_var.get()
            layer.text_data["color"] = color_var.get()
            layer.name = f"Text: {new_text[:15]}"
            self.display_composite()
            self.refresh_layers_list()
            dialog.destroy()

        tk.Button(dialog, text="Apply Changes", command=on_apply, bg="#55ff55", fg="black", font=("Segoe UI", 10, "bold")).pack(pady=20)

    def create_shape_image(self, shape_type, width, height, fill, stroke, stroke_width):
        """TIER 6B: Create shape image"""
        w = max(10, abs(width))
        h = max(10, abs(height))
        # For line/arrow, need extra space
        if shape_type in ("line", "arrow"):
            w = max(w, 100)
            h = max(h, 20)
        img = Image.new("RGBA", (w, h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        fill_rgba = self.hex_to_rgba(fill, int(self.shape_opacity.get()*255))
        stroke_rgba = self.hex_to_rgba(stroke, 255)
        
        if shape_type == "rectangle":
            draw.rectangle([stroke_width//2, stroke_width//2, w-stroke_width//2, h-stroke_width//2], fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
        elif shape_type == "ellipse":
            draw.ellipse([stroke_width//2, stroke_width//2, w-stroke_width//2, h-stroke_width//2], fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
        elif shape_type == "line":
            draw.line([0, h//2, w, h//2], fill=stroke_rgba, width=stroke_width)
        elif shape_type == "arrow":
            # Line with arrow head
            draw.line([0, h//2, w-20, h//2], fill=stroke_rgba, width=stroke_width)
            # Arrow head
            draw.polygon([(w-20, h//2-10), (w, h//2), (w-20, h//2+10)], fill=stroke_rgba)
        elif shape_type == "polygon":
            # Hexagon
            points = []
            cx, cy = w//2, h//2
            r = min(w,h)//2 - stroke_width
            for i in range(6):
                angle = math.radians(60*i - 30)
                points.append((cx + r*math.cos(angle), cy + r*math.sin(angle)))
            draw.polygon(points, fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
        elif shape_type == "star":
            points = []
            cx, cy = w//2, h//2
            r_outer = min(w,h)//2 - stroke_width
            r_inner = r_outer * 0.4
            for i in range(10):
                r = r_outer if i%2==0 else r_inner
                angle = math.radians(36*i - 90)
                points.append((cx + r*math.cos(angle), cy + r*math.sin(angle)))
            draw.polygon(points, fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
        return img

    def hex_to_rgba(self, hex_color, alpha=255):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return (r,g,b,alpha)

    def add_shape_layer(self, shape_type, x1, y1, x2, y2):
        """TIER 6B: Add shape as new layer"""
        if not self.layers:
            w,h = 800,600
            base = Image.new("RGBA", (w,h), (255,255,255,255))
            self.layers = [Layer("Background", base)]
        w = abs(x2-x1)
        h = abs(y2-y1)
        if w < 5 or h < 5:
            w = max(w, 100)
            h = max(h, 100)
        img = self.create_shape_image(shape_type, w, h, self.shape_fill, self.shape_stroke, self.shape_stroke_width.get())
        self.push_undo(f"Add shape {shape_type}")
        layer = Layer(f"Shape: {shape_type}", img)
        layer.is_shape_layer = True
        layer.shape_data = {
            "type": shape_type,
            "fill": self.shape_fill,
            "stroke": self.shape_stroke,
            "stroke_width": self.shape_stroke_width.get(),
            "width": w,
            "height": h
        }
        layer.offset_x = min(x1,x2)
        layer.offset_y = min(y1,y2)
        self.layers.append(layer)
        self.active_layer_idx = len(self.layers)-1
        self.refresh_layers_list()
        self.display_composite()

    def redraw_shape_layer(self):
        """TIER 6B: Redraw selected shape with new settings"""
        if not self.layers:
            return
        layer = self.layers[self.active_layer_idx]
        if not layer.is_shape_layer or not layer.shape_data:
            messagebox.showinfo("Shape", "Select a shape layer first, or draw new shape with Shape tool!")
            return
        self.push_undo(f"Redraw shape {layer.shape_data['type']}")
        w = layer.shape_data.get("width", layer.image.size[0])
        h = layer.shape_data.get("height", layer.image.size[1])
        new_img = self.create_shape_image(layer.shape_data["type"], w, h, self.shape_fill, self.shape_stroke, self.shape_stroke_width.get())
        layer.image = new_img
        layer.shape_data["fill"] = self.shape_fill
        layer.shape_data["stroke"] = self.shape_stroke
        layer.shape_data["stroke_width"] = self.shape_stroke_width.get()
        self.display_composite()

    def draw_transform_handles(self):
        """TIER 6B: Draw 8 handles + rotation handle around active layer"""
        # Clear old handles
        for hid in self.canvas_handles:
            try:
                self.canvas.delete(hid)
            except:
                pass
        self.canvas_handles = []
        if not self.show_transform_handles.get() or not self.layers:
            return
        layer = self.layers[self.active_layer_idx]
        if layer.locked:
            return
        # Get layer bounds in canvas coords
        x1, y1, x2, y2 = layer.get_bounds()
        # Convert to display coords
        disp_x1 = self.image_offset[0] + x1 * self.zoom + self.pan_x
        disp_y1 = self.image_offset[1] + y1 * self.zoom + self.pan_y
        disp_x2 = self.image_offset[0] + x2 * self.zoom + self.pan_x
        disp_y2 = self.image_offset[1] + y2 * self.zoom + self.pan_y
        
        # Draw bounding box
        box_id = self.canvas.create_rectangle(disp_x1, disp_y1, disp_x2, disp_y2, outline="#55ff55", width=1, dash=(4,4))
        self.canvas_handles.append(box_id)
        
        # 8 handles: corners + mid edges
        handles = [
            ("nw", disp_x1, disp_y1),
            ("n", (disp_x1+disp_x2)/2, disp_y1),
            ("ne", disp_x2, disp_y1),
            ("e", disp_x2, (disp_y1+disp_y2)/2),
            ("se", disp_x2, disp_y2),
            ("s", (disp_x1+disp_x2)/2, disp_y2),
            ("sw", disp_x1, disp_y2),
            ("w", disp_x1, (disp_y1+disp_y2)/2),
        ]
        hs = self.handle_size
        for name, hx, hy in handles:
            hid = self.canvas.create_rectangle(hx-hs/2, hy-hs/2, hx+hs/2, hy+hs/2, fill="white", outline="#55ff55", width=1, tags=(f"handle_{name}",))
            self.canvas_handles.append(hid)
        
        # Rotation handle above top center
        rx = (disp_x1+disp_x2)/2
        ry = disp_y1 - 30
        rid = self.canvas.create_oval(rx-hs/2, ry-hs/2, rx+hs/2, ry+hs/2, fill="#ffaa55", outline="white", width=1, tags=("handle_rotate",))
        line_id = self.canvas.create_line(rx, disp_y1, rx, ry, fill="#ffaa55", width=1, dash=(2,2))
        self.canvas_handles.extend([rid, line_id])

    def hit_test_handle(self, x, y):
        """TIER 6B: Check if mouse hits a transform handle"""
        if not self.show_transform_handles.get() or not self.layers:
            return None
        layer = self.layers[self.active_layer_idx]
        x1, y1, x2, y2 = layer.get_bounds()
        disp_x1 = self.image_offset[0] + x1 * self.zoom + self.pan_x
        disp_y1 = self.image_offset[1] + y1 * self.zoom + self.pan_y
        disp_x2 = self.image_offset[0] + x2 * self.zoom + self.pan_x
        disp_y2 = self.image_offset[1] + y2 * self.zoom + self.pan_y
        hs = self.handle_size + 4
        handles = [
            ("nw", disp_x1, disp_y1),
            ("n", (disp_x1+disp_x2)/2, disp_y1),
            ("ne", disp_x2, disp_y1),
            ("e", disp_x2, (disp_y1+disp_y2)/2),
            ("se", disp_x2, disp_y2),
            ("s", (disp_x1+disp_x2)/2, disp_y2),
            ("sw", disp_x1, disp_y2),
            ("w", disp_x1, (disp_y1+disp_y2)/2),
            ("rotate", (disp_x1+disp_x2)/2, disp_y1-30),
        ]
        for name, hx, hy in handles:
            if abs(x-hx) <= hs and abs(y-hy) <= hs:
                return name
        # Inside bounds = move
        if disp_x1 <= x <= disp_x2 and disp_y1 <= y <= disp_y2:
            return "move"
        return None

    def free_transform_dialog(self):
        if not self.layers:
            return
        layer = self.layers[self.active_layer_idx]
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Free Transform - {layer.name} (TIER 6A)")
        dialog.geometry("420x380")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#2b1a1a")
        
        tk.Label(dialog, text=f"Transform: {layer.name}", font=("Segoe UI", 12, "bold"), bg="#2b1a1a", fg="#ffaa55").pack(pady=10)
        tk.Label(dialog, text="Move, Scale, Rotate - Photoshop Ctrl+T style", bg="#2b1a1a", fg="#aaaaaa", font=("Segoe UI", 8)).pack()
        
        # Position
        pos_frame = tk.LabelFrame(dialog, text="Position (Offset)", bg="#2b1a1a", fg="white", padx=10, pady=5)
        pos_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(pos_frame, text="X:", bg="#2b1a1a", fg="#cccccc").grid(row=0, column=0)
        x_var = tk.IntVar(value=layer.offset_x)
        tk.Scale(pos_frame, from_=-500, to=500, orient="horizontal", variable=x_var, bg="#2b1a1a", fg="white", troughcolor="#555", length=300).grid(row=0, column=1)
        tk.Label(pos_frame, text="Y:", bg="#2b1a1a", fg="#cccccc").grid(row=1, column=0)
        y_var = tk.IntVar(value=layer.offset_y)
        tk.Scale(pos_frame, from_=-500, to=500, orient="horizontal", variable=y_var, bg="#2b1a1a", fg="white", troughcolor="#555", length=300).grid(row=1, column=1)
        
        # Scale
        scale_frame = tk.LabelFrame(dialog, text="Scale", bg="#2b1a1a", fg="white", padx=10, pady=5)
        scale_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(scale_frame, text="Scale X:", bg="#2b1a1a", fg="#cccccc").grid(row=0, column=0)
        sx_var = tk.DoubleVar(value=layer.scale_x)
        tk.Scale(scale_frame, from_=0.1, to=3.0, resolution=0.05, orient="horizontal", variable=sx_var, bg="#2b1a1a", fg="white", troughcolor="#555", length=300).grid(row=0, column=1)
        tk.Label(scale_frame, text="Scale Y:", bg="#2b1a1a", fg="#cccccc").grid(row=1, column=0)
        sy_var = tk.DoubleVar(value=layer.scale_y)
        tk.Scale(scale_frame, from_=0.1, to=3.0, resolution=0.05, orient="horizontal", variable=sy_var, bg="#2b1a1a", fg="white", troughcolor="#555", length=300).grid(row=1, column=1)
        
        # Rotation
        rot_frame = tk.LabelFrame(dialog, text="Rotation", bg="#2b1a1a", fg="white", padx=10, pady=5)
        rot_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(rot_frame, text="Angle:", bg="#2b1a1a", fg="#cccccc").grid(row=0, column=0)
        rot_var = tk.DoubleVar(value=layer.rotation)
        tk.Scale(rot_frame, from_=-180, to=180, orient="horizontal", variable=rot_var, bg="#2b1a1a", fg="white", troughcolor="#555", length=300).grid(row=0, column=1)
        
        original_offset_x = layer.offset_x
        original_offset_y = layer.offset_y
        original_sx = layer.scale_x
        original_sy = layer.scale_y
        original_rot = layer.rotation
        
        def apply_live(*args):
            layer.offset_x = x_var.get()
            layer.offset_y = y_var.get()
            layer.scale_x = sx_var.get()
            layer.scale_y = sy_var.get()
            layer.rotation = rot_var.get()
            self.display_composite()
        
        x_var.trace_add("write", lambda *a: apply_live())
        y_var.trace_add("write", lambda *a: apply_live())
        sx_var.trace_add("write", lambda *a: apply_live())
        sy_var.trace_add("write", lambda *a: apply_live())
        rot_var.trace_add("write", lambda *a: apply_live())
        
        def on_ok():
            self.push_undo(f"Transform {layer.name}")
            dialog.destroy()
            self.status_var.set(f"Transformed {layer.name}: pos({layer.offset_x},{layer.offset_y}) scale({layer.scale_x:.2f},{layer.scale_y:.2f}) rot({layer.rotation:.1f})")
        
        def on_cancel():
            layer.offset_x = original_offset_x
            layer.offset_y = original_offset_y
            layer.scale_x = original_sx
            layer.scale_y = original_sy
            layer.rotation = original_rot
            self.display_composite()
            dialog.destroy()
        
        def on_reset():
            x_var.set(0)
            y_var.set(0)
            sx_var.set(1.0)
            sy_var.set(1.0)
            rot_var.set(0.0)
        
        btn_row = tk.Frame(dialog, bg="#2b1a1a")
        btn_row.pack(pady=12)
        tk.Button(btn_row, text="Reset", command=on_reset, width=8).pack(side="left", padx=4)
        tk.Button(btn_row, text="Cancel", command=on_cancel, width=10).pack(side="left", padx=6)
        tk.Button(btn_row, text="OK - Apply", command=on_ok, bg="#ff6a4a", fg="white", width=12, font=("Segoe UI", 9, "bold")).pack(side="left", padx=6)

    # ========== TIER 6C: Font Picker + Alignment + Rounded Rect + Pen Tool + Lock + PSD Export ==========
    def create_text_image_v6c(self, text, font_size, color, font_family="Arial", bold=False, italic=False, stroke_width=0, stroke_color="#000000", align="left", line_spacing=1.2, letter_spacing=0):
        """TIER 6C: Enhanced text with alignment, line spacing, letter spacing"""
        # Handle multiline with alignment
        lines = text.split('\n')
        # Estimate size based on longest line
        max_len = max([len(line) for line in lines]) if lines else 10
        w = max(300, max_len * font_size // 2 + 80)
        h = int(len(lines) * (font_size * line_spacing + 10) + 60)
        img = Image.new("RGBA", (w, h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        try:
            font = None
            for fname in [f"{font_family}.ttf", f"{font_family} Bold.ttf", "arial.ttf", "DejaVuSans.ttf", f"{font_family}.otf"]:
                try:
                    font = ImageFont.truetype(fname, font_size)
                    break
                except:
                    continue
            if font is None:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        # Calculate line heights with spacing
        y = 20
        for line in lines:
            # Measure text width for alignment
            try:
                bbox = draw.textbbox((0,0), line, font=font)
                text_w = bbox[2] - bbox[0]
            except:
                text_w = len(line) * font_size // 2
            
            # Apply letter spacing by expanding
            if letter_spacing != 0 and len(line) > 1:
                # Approximate with extra width
                text_w += letter_spacing * (len(line)-1)
            
            # Alignment offset
            if align == "center":
                x_offset = (w - text_w) // 2
            elif align == "right":
                x_offset = w - text_w - 20
            else:  # left
                x_offset = 20
            
            # Stroke
            if stroke_width > 0:
                for dx in range(-stroke_width, stroke_width+1):
                    for dy in range(-stroke_width, stroke_width+1):
                        if dx==0 and dy==0:
                            continue
                        if letter_spacing != 0 and len(line) > 1:
                            # Draw with letter spacing
                            cx = x_offset
                            for ch in line:
                                draw.text((cx+dx, y+dy), ch, font=font, fill=stroke_color)
                                cx += font_size//2 + letter_spacing + (draw.textbbox((0,0), ch, font=font)[2] - draw.textbbox((0,0), ch, font=font)[0])//2 if len(ch.strip())>0 else font_size//2
                        else:
                            draw.text((x_offset+dx, y+dy), line, font=font, fill=stroke_color)
            
            # Main text with letter spacing
            if letter_spacing != 0 and len(line) > 1:
                cx = x_offset
                for ch in line:
                    draw.text((cx, y), ch, font=font, fill=color)
                    try:
                        ch_w = draw.textbbox((0,0), ch, font=font)[2]
                    except:
                        ch_w = font_size // 2
                    cx += ch_w + letter_spacing
            else:
                draw.text((x_offset, y), line, font=font, fill=color)
            
            y += int(font_size * line_spacing + 10)
        
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)
        return img

    def create_shape_image_v6c(self, shape_type, width, height, fill, stroke, stroke_width, corner_radius=20):
        """TIER 6C: Enhanced shapes with rounded rect"""
        w = max(10, abs(width))
        h = max(10, abs(height))
        if shape_type in ("line", "arrow"):
            w = max(w, 100)
            h = max(h, 20)
        img = Image.new("RGBA", (w, h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        fill_rgba = self.hex_to_rgba(fill, int(self.shape_opacity.get()*255))
        stroke_rgba = self.hex_to_rgba(stroke, 255)
        
        if shape_type == "rounded_rectangle":
            # Rounded rectangle using corner radius
            r = min(corner_radius, min(w,h)//2)
            # Draw rounded rect
            draw.rounded_rectangle([stroke_width//2, stroke_width//2, w-stroke_width//2, h-stroke_width//2], radius=r, fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
        elif shape_type == "rectangle":
            draw.rectangle([stroke_width//2, stroke_width//2, w-stroke_width//2, h-stroke_width//2], fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
        elif shape_type == "ellipse":
            draw.ellipse([stroke_width//2, stroke_width//2, w-stroke_width//2, h-stroke_width//2], fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
        elif shape_type == "line":
            draw.line([0, h//2, w, h//2], fill=stroke_rgba, width=stroke_width)
        elif shape_type == "arrow":
            draw.line([0, h//2, w-20, h//2], fill=stroke_rgba, width=stroke_width)
            draw.polygon([(w-20, h//2-10), (w, h//2), (w-20, h//2+10)], fill=stroke_rgba)
        elif shape_type == "polygon":
            points = []
            cx, cy = w//2, h//2
            r = min(w,h)//2 - stroke_width
            for i in range(6):
                angle = math.radians(60*i - 30)
                points.append((cx + r*math.cos(angle), cy + r*math.sin(angle)))
            draw.polygon(points, fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
        elif shape_type == "star":
            points = []
            cx, cy = w//2, h//2
            r_outer = min(w,h)//2 - stroke_width
            r_inner = r_outer * 0.4
            for i in range(10):
                r = r_outer if i%2==0 else r_inner
                angle = math.radians(36*i - 90)
                points.append((cx + r*math.cos(angle), cy + r*math.sin(angle)))
            draw.polygon(points, fill=fill_rgba, outline=stroke_rgba, width=stroke_width)
        elif shape_type == "pen_path":
            # For pen tool, handled separately
            pass
        return img

    def add_rounded_rect_layer(self, x1, y1, x2, y2):
        """TIER 6C: Add rounded rectangle"""
        w = abs(x2-x1)
        h = abs(y2-y1)
        if w < 5 or h < 5:
            w = max(w, 120)
            h = max(h, 80)
        img = self.create_shape_image_v6c("rounded_rectangle", w, h, self.shape_fill, self.shape_stroke, self.shape_stroke_width.get(), self.shape_corner_radius.get())
        self.push_undo(f"Add rounded rect {w}x{h}")
        layer = Layer(f"RoundedRect {w}x{h}", img)
        layer.is_shape_layer = True
        layer.shape_data = {"type": "rounded_rectangle", "fill": self.shape_fill, "stroke": self.shape_stroke, "stroke_width": self.shape_stroke_width.get(), "corner_radius": self.shape_corner_radius.get(), "width": w, "height": h}
        layer.offset_x = min(x1,x2)
        layer.offset_y = min(y1,y2)
        layer.shape_corner_radius = self.shape_corner_radius.get()
        self.layers.append(layer)
        self.active_layer_idx = len(self.layers)-1
        self.refresh_layers_list()
        self.display_composite()

    def lock_layer(self):
        """TIER 6C: Toggle lock on active layer"""
        if not self.layers:
            return
        layer = self.layers[self.active_layer_idx]
        layer.locked = not layer.locked
        self.refresh_layers_list()
        self.display_composite()
        self.status_var.set(f"{'🔒 Locked' if layer.locked else '🔓 Unlocked'} {layer.name}")

    def toggle_layer_visibility(self, idx=None):
        """TIER 6C: Toggle visibility with eye icon"""
        if idx is None:
            idx = self.active_layer_idx
        if not self.layers or idx >= len(self.layers):
            return
        self.layers[idx].visible = not self.layers[idx].visible
        self.refresh_layers_list()
        self.display_composite()

    def duplicate_layer_offset(self):
        """TIER 6C: Duplicate with offset (like Photoshop Ctrl+J)"""
        if not self.layers:
            return
        self.push_undo("Duplicate with offset")
        dup = self.layers[self.active_layer_idx].copy()
        dup.name += " copy"
        dup.offset_x += 20
        dup.offset_y += 20
        self.layers.insert(self.active_layer_idx+1, dup)
        self.active_layer_idx += 1
        self.refresh_layers_list()
        self.display_composite()
        self.status_var.set(f"Duplicated {dup.name} with 20px offset")

    def export_psd_layers(self):
        """TIER 7: REAL PSD export with psd-tools + fallback"""
        if not self.layers:
            messagebox.showinfo("Export", "No layers to export")
            return
        
        path = filedialog.asksaveasfilename(title="Export PSD", defaultextension=".psd", filetypes=[("Photoshop PSD", "*.psd"), ("PNG Sequence", "folder"), ("All", "*.*")])
        if not path:
            return

        # If user picked folder path or wants sequence, fallback
        if os.path.isdir(path) or path.lower().endswith("/"):
            folder = path if os.path.isdir(path) else os.path.dirname(path)
            self.export_png_sequence(folder)
            return

        # Try real PSD
        try:
            from psd_tools import PSDImage
            from psd_tools.api.layers import PixelLayer
            from psd_tools.api.composer import Composer
            import numpy as np
            
            # Create PSD with base size
            base_w, base_h = self.layers[0].image.size
            # PSDImage.new doesn't exist in newer versions, create blank
            psd = PSDImage.new(base_w, base_h) if hasattr(PSDImage, 'new') else PSDImage.open(io.BytesIO()) # fallback
            
            # For psd-tools 1.9+, we need to build differently: use PSDImage with layers
            # Simple approach: create empty PSD and add pixel layers
            try:
                # Try new API
                psd = PSDImage.new(base_w, base_h, color=(0,0,0,0))
            except:
                # Create via numpy blank
                from psd_tools import PSDImage
                psd = PSDImage.create(base_w, base_h) if hasattr(PSDImage, 'create') else PSDImage.new(base_w, base_h)
            
            # Add layers in reverse (PSD bottom to top)
            for layer in self.layers:
                if not layer.visible:
                    continue
                img = layer.get_styled_image() if hasattr(layer, 'get_styled_image') else layer.get_transformed_image()
                # psd-tools wants RGBA as PIL
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                # Create pixel layer
                # Note: psd-tools PixelLayer.from_image is available
                try:
                    psd_layer = PixelLayer.from_image(img, name=layer.name[:30], top=layer.offset_y, left=layer.offset_x)
                    psd_layer.opacity = int(layer.opacity * 255)
                    psd_layer.visible = layer.visible
                    psd.append(psd_layer)
                except Exception as e2:
                    print(f"PSD layer add failed {e2}, using fallback")
                    raise
            
            psd.save(path)
            messagebox.showinfo("PSD Export", f"Real PSD exported to:\n{path}\n\n{len(self.layers)} layers, {base_w}x{base_h}")
            self.status_var.set(f"PSD exported: {path}")
            return
        except Exception as e:
            print(f"PSD export failed, fallback: {e}")
            # Fallback to PNG sequence in same folder
            folder = os.path.dirname(path) if os.path.dirname(path) else os.getcwd()
            self.export_png_sequence(folder)

    def export_png_sequence(self, folder):
        """Export layers as PNG sequence + flattened"""
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        for i, layer in enumerate(self.layers):
            if not layer.visible:
                continue
            img = layer.get_styled_image() if hasattr(layer, 'get_styled_image') else layer.image.copy()
            safe_name = "".join(c for c in layer.name if c.isalnum() or c in " _-").strip()[:30]
            p = os.path.join(folder, f"{i:02d}_{safe_name}.png")
            img.save(p, "PNG")
        comp = self.get_composite()
        if comp:
            comp.save(os.path.join(folder, "00_FLATTENED.png"), "PNG")
        messagebox.showinfo("Export", f"Exported {len(self.layers)} layers + flattened to:\n{folder}")

    # ================= TIER 7: Layer Styles + Groups + True Blend =================
    def apply_true_blend(self, base_rgb, blend_rgb, mode):
        """TIER 7: True blend modes with math"""
        if mode == "multiply":
            return ImageChops.multiply(base_rgb, blend_rgb)
        elif mode == "screen":
            return ImageChops.screen(base_rgb, blend_rgb)
        elif mode == "overlay":
            # overlay = base < 128 ? 2*base*blend/255 : 255-2*(255-base)*(255-blend)/255
            # Fast numpy path if available
            try:
                import numpy as np
                b = np.array(base_rgb, dtype=np.float32)
                bl = np.array(blend_rgb, dtype=np.float32)
                mask = b < 128
                result = np.empty_like(b)
                result[mask] = (2 * b[mask] * bl[mask] / 255)
                result[~mask] = 255 - 2 * (255 - b[~mask]) * (255 - bl[~mask]) / 255
                result = np.clip(result, 0, 255).astype(np.uint8)
                return Image.fromarray(result, mode="RGB")
            except:
                # PIL fallback loop (slower but ok for small)
                return ImageChops.overlay(base_rgb, blend_rgb) if hasattr(ImageChops, 'overlay') else ImageChops.multiply(base_rgb, blend_rgb)
        elif mode == "soft_light":
            try:
                import numpy as np
                b = np.array(base_rgb, dtype=np.float32)/255
                bl = np.array(blend_rgb, dtype=np.float32)/255
                # soft light formula
                result = np.where(bl < 0.5, b - (1-2*bl)*b*(1-b), b + (2*bl-1)*(np.sqrt(b)-b))
                result = np.clip(result*255, 0, 255).astype(np.uint8)
                return Image.fromarray(result, mode="RGB")
            except:
                return Image.blend(base_rgb, blend_rgb, 0.5)
        elif mode == "hard_light":
            # hard light is overlay with swapped
            return self.apply_true_blend(blend_rgb, base_rgb, "overlay")
        elif mode == "color_dodge":
            try:
                import numpy as np
                b = np.array(base_rgb, dtype=np.float32)
                bl = np.array(blend_rgb, dtype=np.float32)
                result = np.where(bl == 255, 255, np.minimum(255, b*255/(255-bl+1e-6)))
                return Image.fromarray(result.astype(np.uint8), mode="RGB")
            except:
                return ImageChops.lighter(base_rgb, blend_rgb)
        elif mode == "color_burn":
            try:
                import numpy as np
                b = np.array(base_rgb, dtype=np.float32)
                bl = np.array(blend_rgb, dtype=np.float32)
                result = np.where(bl == 0, 0, 255 - np.minimum(255, (255-b)*255/(bl+1e-6)))
                return Image.fromarray(result.astype(np.uint8), mode="RGB")
            except:
                return ImageChops.darker(base_rgb, blend_rgb)
        elif mode == "darken":
            return ImageChops.darker(base_rgb, blend_rgb)
        elif mode == "lighten":
            return ImageChops.lighter(base_rgb, blend_rgb)
        elif mode == "difference":
            return ImageChops.difference(base_rgb, blend_rgb)
        else:
            return blend_rgb

    def layer_styles_dialog(self):
        """TIER 7: Full Layer Styles dialog like Photoshop"""
        if not self.layers:
            return
        layer = self.layers[self.active_layer_idx]
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Layer Styles - {layer.name} (Tier 7)")
        dialog.geometry("520x680")
        dialog.configure(bg="#2b2b2b")
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Layer Styles - Photoshop Style", bg="#2b2b2b", fg="#ffaa55", font=("Segoe UI", 12, "bold")).pack(pady=10)

        # Scrollable
        canvas = tk.Canvas(dialog, bg="#2b2b2b", highlightthickness=0)
        scrollbar = tk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg="#2b2b2b")
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")

        style_vars = {}

        def make_style_section(parent, title, key):
            frame = tk.LabelFrame(parent, text=title, bg="#2b2b2b", fg="white", font=("Segoe UI", 9, "bold"), padx=8, pady=6)
            frame.pack(fill="x", padx=5, pady=5)
            
            style = layer.layer_styles[key]
            enabled_var = tk.BooleanVar(value=style["enabled"])
            tk.Checkbutton(frame, text=f"Enable {title}", variable=enabled_var, bg="#2b2b2b", fg="#ffaa55", selectcolor="#3c3c3c", font=("Segoe UI", 8, "bold")).pack(anchor="w")
            style_vars[f"{key}_enabled"] = enabled_var

            # Dynamic controls per style type
            if key in ("drop_shadow", "inner_shadow"):
                for lbl, sk in [("Offset X", "offset_x"), ("Offset Y", "offset_y"), ("Blur", "blur")]:
                    row = tk.Frame(frame, bg="#2b2b2b")
                    row.pack(fill="x", pady=2)
                    tk.Label(row, text=f"{lbl}:", bg="#2b2b2b", fg="#cccccc", width=10, anchor="w", font=("Segoe UI", 8)).pack(side="left")
                    var = tk.IntVar(value=style.get(sk, 5))
                    tk.Scale(row, from_=-30 if "offset" in sk else 0, to=30 if "offset" in sk else 50, orient="horizontal", variable=var, bg="#2b2b2b", fg="white", troughcolor="#555555", highlightthickness=0, length=200).pack(side="left", fill="x", expand=True)
                    style_vars[f"{key}_{sk}"] = var
            elif key in ("outer_glow", "inner_glow"):
                row = tk.Frame(frame, bg="#2b2b2b")
                row.pack(fill="x", pady=2)
                tk.Label(row, text="Blur:", bg="#2b2b2b", fg="#cccccc", width=10, anchor="w", font=("Segoe UI", 8)).pack(side="left")
                var = tk.IntVar(value=style.get("blur", 15))
                tk.Scale(row, from_=0, to=100, orient="horizontal", variable=var, bg="#2b2b2b", fg="white", troughcolor="#555555", highlightthickness=0, length=200).pack(side="left", fill="x", expand=True)
                style_vars[f"{key}_blur"] = var
            elif key == "stroke":
                for lbl, sk, fr, to in [("Width", "width", 0, 20), ("Opacity", "opacity", 0.0, 1.0)]:
                    row = tk.Frame(frame, bg="#2b2b2b")
                    row.pack(fill="x", pady=2)
                    tk.Label(row, text=f"{lbl}:", bg="#2b2b2b", fg="#cccccc", width=10, anchor="w", font=("Segoe UI", 8)).pack(side="left")
                    if isinstance(style.get(sk, 1), float):
                        var = tk.DoubleVar(value=style.get(sk, 1.0))
                        tk.Scale(row, from_=fr, to=to, resolution=0.05, orient="horizontal", variable=var, bg="#2b2b2b", fg="white", troughcolor="#555555", highlightthickness=0, length=200).pack(side="left", fill="x", expand=True)
                    else:
                        var = tk.IntVar(value=style.get(sk, 3))
                        tk.Scale(row, from_=fr, to=to, orient="horizontal", variable=var, bg="#2b2b2b", fg="white", troughcolor="#555555", highlightthickness=0, length=200).pack(side="left", fill="x", expand=True)
                    style_vars[f"{key}_{sk}"] = var
                # Position
                pos_row = tk.Frame(frame, bg="#2b2b2b")
                pos_row.pack(fill="x", pady=2)
                tk.Label(pos_row, text="Position:", bg="#2b2b2b", fg="#cccccc", width=10, anchor="w", font=("Segoe UI", 8)).pack(side="left")
                pos_var = tk.StringVar(value=style.get("position", "outside"))
                ttk.Combobox(pos_row, textvariable=pos_var, values=["outside", "inside", "center"], width=10, state="readonly").pack(side="left")
                style_vars[f"{key}_position"] = pos_var
            # Color + Opacity for all
            color_row = tk.Frame(frame, bg="#2b2b2b")
            color_row.pack(fill="x", pady=2)
            tk.Label(color_row, text="Color:", bg="#2b2b2b", fg="#cccccc", width=10, anchor="w", font=("Segoe UI", 8)).pack(side="left")
            color_var = tk.StringVar(value=style.get("color", "#000000"))
            preview = tk.Label(color_row, bg=color_var.get(), width=3, relief="sunken")
            preview.pack(side="left", padx=4)
            def pick_c(v=color_var, p=preview):
                c = colorchooser.askcolor(v.get())[1]
                if c:
                    v.set(c)
                    p.config(bg=c)
            tk.Button(color_row, text="Pick", command=pick_c, bg="#4a4a4a", fg="white", font=("Segoe UI", 7)).pack(side="left", padx=4)
            style_vars[f"{key}_color"] = color_var

            op_row = tk.Frame(frame, bg="#2b2b2b")
            op_row.pack(fill="x", pady=2)
            tk.Label(op_row, text="Opacity:", bg="#2b2b2b", fg="#cccccc", width=10, anchor="w", font=("Segoe UI", 8)).pack(side="left")
            op_var = tk.DoubleVar(value=style.get("opacity", 0.5))
            tk.Scale(op_row, from_=0.0, to=1.0, resolution=0.05, orient="horizontal", variable=op_var, bg="#2b2b2b", fg="white", troughcolor="#555555", highlightthickness=0, length=200).pack(side="left", fill="x", expand=True)
            style_vars[f"{key}_opacity"] = op_var

        # Make all 6 sections
        for title, key in [("Drop Shadow", "drop_shadow"), ("Outer Glow", "outer_glow"), ("Inner Glow", "inner_glow"), ("Stroke", "stroke"), ("Color Overlay", "color_overlay"), ("Inner Shadow", "inner_shadow")]:
            make_style_section(scroll_frame, title, key)

        def on_apply():
            self.push_undo(f"Layer Styles {layer.name}")
            for key in layer.layer_styles:
                s = layer.layer_styles[key]
                if f"{key}_enabled" in style_vars:
                    s["enabled"] = style_vars[f"{key}_enabled"].get()
                for prop in ["offset_x", "offset_y", "blur", "width", "opacity", "color", "position"]:
                    vk = f"{key}_{prop}"
                    if vk in style_vars:
                        s[prop] = style_vars[vk].get()
            self.display_composite()
            self.refresh_layers_list()
            dialog.destroy()
            self.status_var.set(f"Applied layer styles to {layer.name}")

        btn_row = tk.Frame(dialog, bg="#2b2b2b")
        btn_row.pack(fill="x", pady=10, padx=10)
        tk.Button(btn_row, text="Cancel", command=dialog.destroy, bg="#4a4a4a", fg="white").pack(side="right", padx=5)
        tk.Button(btn_row, text="Apply Styles", command=on_apply, bg="#ffaa55", fg="black", font=("Segoe UI", 10, "bold")).pack(side="right", padx=5)

    def create_group_layer(self):
        """TIER 7: Create layer group (folder)"""
        if not self.layers:
            return
        self.push_undo("Create Group")
        group = Layer(f"Group {len([l for l in self.layers if l.is_group])+1}", Image.new("RGBA", self.layers[0].image.size, (0,0,0,0)))
        group.is_group = True
        group.group_layers = []
        # If multiple layers selected? For now, create empty group at top
        self.layers.append(group)
        self.active_layer_idx = len(self.layers)-1
        self.refresh_layers_list()
        self.display_composite()
        self.status_var.set(f"Created {group.name}")

    def ungroup_layer(self):
        """TIER 7: Ungroup"""
        if not self.layers:
            return
        layer = self.layers[self.active_layer_idx]
        if not layer.is_group:
            messagebox.showinfo("Groups", "Active layer is not a group")
            return
        self.push_undo("Ungroup")
        idx = self.active_layer_idx
        # Insert group layers back
        for gl in reversed(layer.group_layers):
            self.layers.insert(idx, gl)
        del self.layers[idx + len(layer.group_layers)]
        self.active_layer_idx = idx
        self.refresh_layers_list()
        self.display_composite()

    def add_to_group(self):
        """TIER 7: Add active layer to group above/below"""
        if len(self.layers) < 2:
            return
        # Find nearest group
        active = self.layers[self.active_layer_idx]
        if active.is_group:
            messagebox.showinfo("Groups", "Select a non-group layer to add to a group")
            return
        # Look for group layer
        group_idx = None
        for i in range(len(self.layers)-1, -1, -1):
            if self.layers[i].is_group and i != self.active_layer_idx:
                group_idx = i
                break
        if group_idx is None:
            messagebox.showinfo("Groups", "No group found. Create a group first.")
            return
        self.push_undo("Add to Group")
        group = self.layers[group_idx]
        # Remove active from main list and add to group
        moving = self.layers.pop(self.active_layer_idx)
        # Adjust group_idx if needed
        if group_idx > self.active_layer_idx:
            group_idx -= 1
        group.group_layers.append(moving)
        self.active_layer_idx = group_idx
        self.refresh_layers_list()
        self.display_composite()
        self.status_var.set(f"Added {moving.name} to {group.name}")

    def quick_style(self, style_name):
        """TIER 7: Quick apply one style"""
        if not self.layers:
            return
        self.push_undo(f"Quick style {style_name}")
        layer = self.layers[self.active_layer_idx]
        layer.layer_styles[style_name]["enabled"] = not layer.layer_styles[style_name]["enabled"]
        self.display_composite()
        self.refresh_layers_list()
        self.status_var.set(f"{'Enabled' if layer.layer_styles[style_name]['enabled'] else 'Disabled'} {style_name} on {layer.name}")

    def clear_layer_styles(self):
        if not self.layers:
            return
        self.push_undo("Clear layer styles")
        layer = self.layers[self.active_layer_idx]
        for k in layer.layer_styles:
            layer.layer_styles[k]["enabled"] = False
        self.display_composite()
        self.refresh_layers_list()
        self.status_var.set(f"Cleared styles on {layer.name}")

    # Pen Tool
    # Pen Tool (Tier 6C)
    def on_pen_press(self, event):
        if not self.layers:
            return
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            return
        if not self.pen_active:
            self.pen_points = [coords]
            self.pen_active = True
            self.clear_pen_visual()
        else:
            self.pen_points.append(coords)
        self.draw_pen_visual()

    def on_pen_drag(self, event):
        if not self.pen_active or not self.layers:
            return
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            return
        # Add point if far enough
        if len(self.pen_points) == 0 or ((coords[0]-self.pen_points[-1][0])**2 + (coords[1]-self.pen_points[-1][1])**2) > 16:
            self.pen_points.append(coords)
            self.draw_pen_visual()

    def on_pen_release(self, event):
        pass

    def on_pen_close(self):
        if not self.pen_active or len(self.pen_points) < 2:
            return
        # Create pen path layer
        self.push_undo(f"Pen path {len(self.pen_points)} points")
        # Calculate bounds
        min_x = min(p[0] for p in self.pen_points)
        max_x = max(p[0] for p in self.pen_points)
        min_y = min(p[1] for p in self.pen_points)
        max_y = max(p[1] for p in self.pen_points)
        w = max(10, max_x - min_x + 20)
        h = max(10, max_y - min_y + 20)
        # Offset points to local
        local_points = [(p[0]-min_x+10, p[1]-min_y+10) for p in self.pen_points]
        
        img = Image.new("RGBA", (w, h), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        stroke_rgba = self.hex_to_rgba(self.shape_stroke, 255)
        # Draw path
        if len(local_points) >= 2:
            draw.line(local_points, fill=stroke_rgba, width=self.shape_stroke_width.get(), joint="curve")
        
        layer = Layer(f"Pen Path {len(local_points)} pts", img)
        layer.is_shape_layer = True
        layer.shape_data = {"type": "pen_path", "points": local_points, "stroke": self.shape_stroke, "stroke_width": self.shape_stroke_width.get(), "width": w, "height": h}
        layer.offset_x = min_x - 10
        layer.offset_y = min_y - 10
        self.layers.append(layer)
        self.active_layer_idx = len(self.layers)-1
        self.pen_active = False
        self.pen_points = []
        self.clear_pen_visual()
        self.refresh_layers_list()
        self.display_composite()
        self.status_var.set(f"Pen path created with {len(local_points)} points")

    def draw_pen_visual(self):
        self.clear_pen_visual()
        if len(self.pen_points) < 2:
            return
        for i in range(len(self.pen_points)-1):
            p1 = self.image_to_canvas_coords(self.pen_points[i][0], self.pen_points[i][1])
            p2 = self.image_to_canvas_coords(self.pen_points[i+1][0], self.pen_points[i+1][1])
            if p1 and p2:
                line_id = self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#ff55ff", width=2, dash=(2,2))
                self.pen_canvas_ids.append(line_id)
                # Draw points
                dot_id = self.canvas.create_oval(p1[0]-3, p1[1]-3, p1[0]+3, p1[1]+3, fill="#ff55ff", outline="white")
                self.pen_canvas_ids.append(dot_id)

    def clear_pen_visual(self):
        for lid in self.pen_canvas_ids:
            try:
                self.canvas.delete(lid)
            except:
                pass
        self.pen_canvas_ids = []

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
                if l.mask is not None:
                    alpha = base.split()[3]
                    m = l.mask
                    if m.size != alpha.size:
                        m = m.resize(alpha.size, Image.LANCZOS)
                    alpha = ImageChops.multiply(alpha, m)
                    base.putalpha(alpha)
            else:
                base = self.composite_two(Layer("base", base), l)
        self.layers = [Layer("Background", base.copy())]
        self.active_layer_idx = 0
        self.refresh_layers_list()
        self.display_composite()

    def composite_two(self, lower_layer, upper_layer):
        lower = lower_layer.image
        # TIER 7: Use styled image if available (drop shadow, glow, stroke etc)
        if hasattr(upper_layer, 'get_styled_image') and any(s.get("enabled", False) for s in getattr(upper_layer, 'layer_styles', {}).values()):
            try:
                upper = upper_layer.get_styled_image()
            except:
                upper = upper_layer.get_transformed_image() if hasattr(upper_layer, 'get_transformed_image') else upper_layer.image
        else:
            upper = upper_layer.get_transformed_image() if hasattr(upper_layer, 'get_transformed_image') else upper_layer.image
        
        # Handle group layers
        if getattr(upper_layer, 'is_group', False):
            # Composite group layers together
            group_base = None
            for gl in upper_layer.group_layers:
                if not gl.visible:
                    continue
                if group_base is None:
                    group_base = gl.get_styled_image() if hasattr(gl, 'get_styled_image') else gl.get_transformed_image()
                else:
                    group_base = self.composite_two(Layer("base", group_base), gl)
            if group_base is None:
                return lower
            upper = group_base

        lower_w, lower_h = lower.size
        if upper.mode != "RGBA":
            upper = upper.convert("RGBA")
        if lower.mode != "RGBA":
            lower = lower.convert("RGBA")
        
        offset_x = getattr(upper_layer, 'offset_x', 0)
        offset_y = getattr(upper_layer, 'offset_y', 0)
        
        if offset_x != 0 or offset_y != 0 or upper.size != lower.size:
            upper_canvas = Image.new("RGBA", (lower_w, lower_h), (0,0,0,0))
            upper_canvas.paste(upper, (offset_x, offset_y), upper)
            upper = upper_canvas
        
        if upper_layer.mask is not None:
            mask = upper_layer.mask
            if mask.size != upper.size:
                mask = mask.resize(upper.size, Image.LANCZOS)
            alpha = upper.split()[3]
            alpha = ImageChops.multiply(alpha, mask)
            upper.putalpha(alpha)
        
        mode = getattr(upper_layer, 'blend_mode', 'normal')
        if mode == "normal":
            blended_rgb = upper
        else:
            lower_rgb = lower.convert("RGB")
            upper_rgb = upper.convert("RGB")
            # TIER 7: Use true blend
            blended = self.apply_true_blend(lower_rgb, upper_rgb, mode)
            blended = blended.convert("RGBA")
            blended.putalpha(upper.split()[3])
            blended_rgb = blended
        
        # TIER 7: Color overlay style
        if hasattr(upper_layer, 'layer_styles') and upper_layer.layer_styles.get("color_overlay", {}).get("enabled"):
            co = upper_layer.layer_styles["color_overlay"]
            overlay_color = co["color"]
            overlay_op = co["opacity"]
            # Tint upper with overlay color
            r = int(overlay_color.lstrip("#")[0:2], 16)
            g = int(overlay_color.lstrip("#")[2:4], 16)
            b = int(overlay_color.lstrip("#")[4:6], 16)
            color_layer = Image.new("RGBA", blended_rgb.size, (r,g,b,int(255*overlay_op)))
            # Blend overlay with blend mode
            blend_mode_overlay = co.get("blend_mode", "normal")
            if blend_mode_overlay == "normal":
                blended_rgb = Image.alpha_composite(blended_rgb, color_layer)
            else:
                # Use true blend for overlay
                base_rgb = blended_rgb.convert("RGB")
                over_rgb = color_layer.convert("RGB")
                blended_over = self.apply_true_blend(base_rgb, over_rgb, blend_mode_overlay).convert("RGBA")
                blended_over.putalpha(ImageChops.multiply(blended_rgb.split()[3], color_layer.split()[3]))
                blended_rgb = Image.alpha_composite(blended_rgb, blended_over)
        
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
                # TIER 7: Use styled image
                if hasattr(l, 'get_styled_image') and any(s.get("enabled", False) for s in getattr(l, 'layer_styles', {}).values()):
                    try:
                        base = l.get_styled_image().copy()
                    except:
                        base = l.image.copy()
                else:
                    base = l.image.copy()
                if l.mask is not None:
                    alpha = base.split()[3]
                    m = l.mask
                    if m.size != alpha.size:
                        m = m.resize(alpha.size, Image.LANCZOS)
                    alpha = ImageChops.multiply(alpha, m)
                    base.putalpha(alpha)
            else:
                base = self.composite_two(Layer("base", base), l)
        return base

    def display_composite(self):
        # TIER 8: If any adjustment layer exists, use get_composited_image for correct preview
        has_adj = any(getattr(l, 'is_adjustment_layer', False) for l in self.layers) if self.layers else False
        if has_adj:
            comp = self.get_composited_image()
            if comp:
                self.composited_image = comp
                # Now display comp
                # Fall through to normal display logic using self.composited_image
                # We'll let original logic run but override with comp at end
                pass

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
        # TIER 6B: Draw handles after image
        self.root.after(10, self.draw_transform_handles)

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
        if self.layers[self.active_layer_idx].mask is not None:
            self.layers[self.active_layer_idx].mask = self.layers[self.active_layer_idx].mask.rotate(angle, expand=True, resample=Image.BICUBIC)
        self.display_composite()
        self.update_resize_entries()

    def flip_image(self, direction):
        if not self.layers:
            return
        self.push_undo(f"Flip {direction}")
        layer = self.layers[self.active_layer_idx]
        layer.image = ImageOps.mirror(layer.image) if direction=="h" else ImageOps.flip(layer.image)
        if layer.mask is not None:
            layer.mask = ImageOps.mirror(layer.mask) if direction=="h" else ImageOps.flip(layer.mask)
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
            self.grad_preview1.config(bg=self.brush_color)

    def pick_gradient_color(self, which):
        init = self.brush_color if which==1 else self.gradient_color2
        c = colorchooser.askcolor(initialcolor=init)
        if c[1]:
            if which==1:
                self.brush_color = c[1]
                self.color_preview.config(bg=c[1])
                self.grad_preview1.config(bg=c[1])
            else:
                self.gradient_color2 = c[1]
                self.grad_preview2.config(bg=c[1])

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

    def image_to_canvas_coords(self, ix, iy):
        if self.composited_image is None:
            return None
        iw, ih = self.layers[self.active_layer_idx].image.size if self.layers else self.composited_image.size
        ox, oy = self.image_offset
        dw, dh = self.display_size
        rx = ix / iw
        ry = iy / ih
        cx = ox + rx * dw
        cy = oy + ry * dh
        return (cx, cy)

    def on_canvas_press(self, event):
        # TIER 8: Liquify tool immediate
        if self.current_tool.get() == "liquify":
            self.push_undo("Liquify")
            cx, cy = self.canvas_to_image_coords(event.x, event.y)
            if cx is not None:
                self.liquify_at(cx, cy)
            return

        tool = self.current_tool.get()
        # TIER 6B: Check handles first for any tool if enabled
        if self.show_transform_handles.get() and self.layers and tool not in ("pen", "pen_path"):
            hit = self.hit_test_handle(event.x, event.y)
            if hit:
                self.active_handle = hit
                # TIER 6C: Capture Shift/Alt state
                self.shift_pressed = (event.state & 0x0001) != 0  # Shift
                self.alt_pressed = (event.state & 0x0008) != 0 or (event.state & 0x20000) != 0  # Alt (varies)
                self.on_transform_handle_press(event, hit)
                return
        if tool == "crop":
            self.on_crop_press(event)
        elif tool == "transform" or tool == "move":
            self.on_transform_press(event)
        elif tool == "shape":
            self.on_shape_press(event)
        elif tool == "rounded_rect":
            self.on_shape_press(event)  # reuse shape start
        elif tool == "pen" or tool == "pen_path":
            self.on_pen_press(event)
        elif tool in ("brush", "eraser"):
            self.on_brush_press(event)
        elif tool == "text":
            self.on_text_click(event)
        elif tool == "wand":
            self.on_wand_click(event)
        elif tool == "lasso":
            self.on_lasso_press(event)
        elif tool == "gradient":
            self.on_gradient_press(event)
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
        if self.current_tool.get() == "liquify":
            cx, cy = self.canvas_to_image_coords(event.x, event.y)
            if cx is not None:
                self.liquify_at(cx, cy)
            return

        tool = self.current_tool.get()
        if self.active_handle is not None:
            self.on_transform_handle_drag(event)
            return
        if tool == "crop":
            self.on_crop_drag(event)
        elif tool in ("transform", "move"):
            self.on_transform_drag(event)
        elif tool == "shape" or tool == "rounded_rect":
            self.on_shape_drag(event)
        elif tool == "pen" or tool == "pen_path":
            self.on_pen_drag(event)
        elif tool in ("brush", "eraser"):
            self.on_brush_drag(event)
        elif tool == "lasso":
            self.on_lasso_drag(event)
        elif tool == "gradient":
            self.on_gradient_drag(event)
        elif tool == "clone":
            self.on_clone_drag(event)

    def on_canvas_release(self, event):
        tool = self.current_tool.get()
        if self.active_handle is not None:
            self.on_transform_handle_release(event)
            self.active_handle = None
            return
        if tool == "crop":
            self.on_crop_release(event)
        elif tool in ("transform", "move"):
            self.on_transform_release(event)
        elif tool == "shape" or tool == "rounded_rect":
            self.on_shape_release(event)
        elif tool == "pen" or tool == "pen_path":
            self.on_pen_release(event)
        elif tool in ("brush", "eraser"):
            self.on_brush_release(event)
        elif tool == "lasso":
            self.on_lasso_release(event)
        elif tool == "gradient":
            self.on_gradient_release(event)
        elif tool == "clone":
            self.on_brush_release(event)

    # ========== TIER 6B: Shape Tool Handlers ==========
    def on_shape_press(self, event):
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            return
        self.shape_start = coords
        self.is_drawing = True

    def on_shape_drag(self, event):
        if not self.is_drawing or self.shape_start is None:
            return
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            return
        # Preview could be drawn on canvas, but for simplicity we just update status
        w = abs(coords[0]-self.shape_start[0])
        h = abs(coords[1]-self.shape_start[1])
        self.status_var.set(f"Shape {self.shape_type.get()}: {w}x{h} drag to size")

    def on_shape_release(self, event):
        if not self.is_drawing or self.shape_start is None:
            return
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            coords = self.shape_start
        self.is_drawing = False
        x1,y1 = self.shape_start
        x2,y2 = coords
        if abs(x2-x1) < 5 and abs(y2-y1) < 5:
            # Small click = 100x100 default
            x2 = x1 + 100
            y2 = y1 + 100
        tool = self.current_tool.get()
        if tool == "rounded_rect":
            # TIER 6C: Rounded rect
            self.add_rounded_rect_layer(x1, y1, x2, y2)
        else:
            self.add_shape_layer(self.shape_type.get(), x1, y1, x2, y2)
        self.shape_start = None
        self.status_var.set(f"Added {tool} shape layer")

    # ========== TIER 6B: Transform Handle Handlers ==========
    def on_transform_handle_press(self, event, handle):
        if not self.layers:
            return
        self.transform_start_pos = (event.x, event.y)
        layer = self.layers[self.active_layer_idx]
        self.transform_start_offset = (layer.offset_x, layer.offset_y)
        self.transform_start_scale = (layer.scale_x, layer.scale_y)
        self.transform_start_bounds = layer.get_bounds()
        self.transform_start_rotation = layer.rotation
        self.is_drawing = True
        if not hasattr(self, '_transform_undo_pushed') or not self._transform_undo_pushed:
            self.push_undo(f"Transform {handle} {layer.name}")
            self._transform_undo_pushed = True

    def on_transform_handle_drag(self, event):
        if not self.layers or self.transform_start_pos is None:
            return
        dx = event.x - self.transform_start_pos[0]
        dy = event.y - self.transform_start_pos[1]
        img_dx = int(dx / self.zoom) if self.zoom != 0 else dx
        img_dy = int(dy / self.zoom) if self.zoom != 0 else dy
        layer = self.layers[self.active_layer_idx]
        handle = self.active_handle
        x1,y1,x2,y2 = self.transform_start_bounds
        orig_w = x2 - x1
        orig_h = y2 - y1
        # TIER 6C: Check Shift/Alt state from event
        shift = (event.state & 0x0001) != 0 or self.lock_aspect_ratio.get()
        alt = (event.state & 0x0008) != 0 or self.scale_from_center.get() or (event.state & 0x20000) != 0
        if handle == "move":
            layer.offset_x = self.transform_start_offset[0] + img_dx
            layer.offset_y = self.transform_start_offset[1] + img_dy
            # Snap
            if self.snap_enabled.get() and len(self.layers) > 0:
                base_w, base_h = self.layers[0].image.size
                # Snap to center
                center_x = base_w//2
                layer_center_x = layer.offset_x + orig_w//2
                if abs(layer_center_x - center_x) < 20:
                    layer.offset_x = center_x - orig_w//2
                center_y = base_h//2
                layer_center_y = layer.offset_y + orig_h//2
                if abs(layer_center_y - center_y) < 20:
                    layer.offset_y = center_y - orig_h//2
        elif handle in ("e", "w"):
            # Horizontal scale
            if orig_w > 0:
                if handle == "e":
                    new_w = max(10, orig_w + img_dx)
                else:
                    new_w = max(10, orig_w - img_dx)
                    layer.offset_x = self.transform_start_offset[0] + img_dx
                # TIER 6C: Alt = scale from center (both sides)
                if alt:
                    new_w = max(10, orig_w + img_dx*2 if handle=="e" else orig_w - img_dx*2)
                    layer.offset_x = self.transform_start_offset[0] - img_dx if handle=="e" else self.transform_start_offset[0] + img_dx
                # Shift = lock aspect
                if shift:
                    scale_factor = new_w / orig_w
                    layer.scale_x = self.transform_start_scale[0] * scale_factor
                    layer.scale_y = self.transform_start_scale[1] * scale_factor
                else:
                    layer.scale_x = self.transform_start_scale[0] * (new_w / orig_w) if orig_w != 0 else 1.0
        elif handle in ("s", "n"):
            if orig_h > 0:
                if handle == "s":
                    new_h = max(10, orig_h + img_dy)
                else:
                    new_h = max(10, orig_h - img_dy)
                    layer.offset_y = self.transform_start_offset[1] + img_dy
                if alt:
                    new_h = max(10, orig_h + img_dy*2 if handle=="s" else orig_h - img_dy*2)
                    layer.offset_y = self.transform_start_offset[1] - img_dy if handle=="s" else self.transform_start_offset[1] + img_dy
                if shift:
                    scale_factor = new_h / orig_h
                    layer.scale_x = self.transform_start_scale[0] * scale_factor
                    layer.scale_y = self.transform_start_scale[1] * scale_factor
                else:
                    layer.scale_y = self.transform_start_scale[1] * (new_h / orig_h) if orig_h != 0 else 1.0
        elif handle in ("se", "nw", "ne", "sw"):
            # Corner = both axes
            if orig_w > 0 and orig_h > 0:
                if handle == "se":
                    new_w = max(10, orig_w + img_dx)
                    new_h = max(10, orig_h + img_dy)
                elif handle == "nw":
                    new_w = max(10, orig_w - img_dx)
                    new_h = max(10, orig_h - img_dy)
                    layer.offset_x = self.transform_start_offset[0] + img_dx
                    layer.offset_y = self.transform_start_offset[1] + img_dy
                elif handle == "ne":
                    new_w = max(10, orig_w + img_dx)
                    new_h = max(10, orig_h - img_dy)
                    layer.offset_y = self.transform_start_offset[1] + img_dy
                elif handle == "sw":
                    new_w = max(10, orig_w - img_dx)
                    new_h = max(10, orig_h + img_dy)
                    layer.offset_x = self.transform_start_offset[0] + img_dx
                # TIER 6C: Shift = lock aspect ratio
                if shift:
                    # Use larger delta as driver
                    scale_x = new_w / orig_w
                    scale_y = new_h / orig_h
                    scale = max(scale_x, scale_y) if abs(img_dx) > abs(img_dy) else min(scale_x, scale_y)
                    # Or average for uniform
                    avg_scale = (scale_x + scale_y)/2
                    if handle in ("se", "nw"):
                        # Keep aspect: use same scale
                        scale = (scale_x + scale_y)/2
                    layer.scale_x = self.transform_start_scale[0] * scale
                    layer.scale_y = self.transform_start_scale[1] * scale
                else:
                    layer.scale_x = self.transform_start_scale[0] * (new_w / orig_w)
                    layer.scale_y = self.transform_start_scale[1] * (new_h / orig_h)
                # Alt = scale from center
                if alt:
                    # Move offset to keep center
                    layer.offset_x = self.transform_start_offset[0] - (new_w - orig_w)/2
                    layer.offset_y = self.transform_start_offset[1] - (new_h - orig_h)/2
        elif handle == "rotate":
            # Calculate angle from center
            cx = x1 + orig_w/2
            cy = y1 + orig_h/2
            # Convert mouse to image coords for angle
            mx, my = self.canvas_to_image_coords(event.x, event.y)
            if mx is None:
                return
            angle = math.degrees(math.atan2(my - cy, mx - cx)) + 90
            # TIER 6C: Shift = snap to 15 degree increments
            if shift:
                angle = round(angle / 15) * 15
            layer.rotation = angle
        self.display_composite()
        extra = []
        if shift:
            extra.append("Shift=AspectLock")
        if alt:
            extra.append("Alt=Center")
        extra_str = f" [{' + '.join(extra)}]" if extra else ""
        self.status_var.set(f"Handle {handle}{extra_str}: offset ({layer.offset_x},{layer.offset_y}) scale ({layer.scale_x:.2f},{layer.scale_y:.2f}) rot {layer.rotation:.1f}°")

    def on_transform_handle_release(self, event):
        self.is_drawing = False
        self.transform_start_pos = None
        self.display_composite()

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
        layer = self.layers[self.active_layer_idx]
        size = self.brush_size.get()
        tool = self.current_tool.get()
        if self.mask_edit_mode.get() and layer.mask is not None:
            mask = layer.mask
            if mask.mode != "L":
                mask = mask.convert("L")
            draw = ImageDraw.Draw(mask)
            color = 255 if tool == "brush" else 0
            draw.line([p1, p2], fill=color, width=size, joint="curve")
            draw.ellipse([p1[0]-size//2, p1[1]-size//2, p1[0]+size//2, p1[1]+size//2], fill=color)
            layer.mask = mask
            self.refresh_layers_list()
            self.display_composite()
            return
        layer_img = layer.image
        if layer_img.mode != "RGBA":
            layer_img = layer_img.convert("RGBA")
            layer.image = layer_img
        draw = ImageDraw.Draw(layer_img)
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
        layer.image = layer_img
        self.display_composite()

    def on_text_click(self, event):
        self.add_text_dialog(prefill_pos=self.canvas_to_image_coords(event.x, event.y))

    # ========== TIER 6A: Free Transform Handlers ==========
    def on_transform_press(self, event):
        if not self.layers:
            return
        self.transform_start_pos = (event.x, event.y)
        layer = self.layers[self.active_layer_idx]
        self.transform_start_offset = (layer.offset_x, layer.offset_y)
        self.transform_start_scale = (layer.scale_x, layer.scale_y)
        self.is_drawing = True
        # Push undo only on first press of a transform session
        if not hasattr(self, '_transform_undo_pushed') or not self._transform_undo_pushed:
            self.push_undo(f"Transform {layer.name}")
            self._transform_undo_pushed = True

    def on_transform_drag(self, event):
        if not self.layers or not self.is_drawing or self.transform_start_pos is None:
            return
        dx = event.x - self.transform_start_pos[0]
        dy = event.y - self.transform_start_pos[1]
        # Convert canvas delta to image delta (account for zoom)
        if self.display_size[0] > 0 and self.composited_image:
            # Estimate image delta: canvas delta / zoom
            img_dx = int(dx / self.zoom) if self.zoom != 0 else dx
            img_dy = int(dy / self.zoom) if self.zoom != 0 else dy
        else:
            img_dx = dx
            img_dy = dy
        
        layer = self.layers[self.active_layer_idx]
        # Move
        if self.transform_handle in ('move', None):
            layer.offset_x = self.transform_start_offset[0] + img_dx
            layer.offset_y = self.transform_start_offset[1] + img_dy
        self.display_composite()
        self.status_var.set(f"Transform: offset ({layer.offset_x}, {layer.offset_y}) scale ({layer.scale_x:.2f}, {layer.scale_y:.2f}) rot {layer.rotation:.1f}° - Drag to move, use dialog for scale/rotate")

    def on_transform_release(self, event):
        self.is_drawing = False
        self.transform_start_pos = None
        # Keep undo flag for session, reset after short delay? For now reset on release
        # Actually keep it so multiple drags in same session don't push many undos
        # We'll reset when tool changes
        self.display_composite()

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
        return sum(1 for v in mask.get_flattened_data() if v>0) if hasattr(mask, 'get_flattened_data') else sum(1 for p in mask.getdata() if p>0)

    # LASSO
    def on_lasso_press(self, event):
        if not self.layers:
            return
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            return
        if not self.lasso_active:
            self.lasso_points = [coords]
            self.lasso_active = True
            self.clear_lasso_visual()
        else:
            self.lasso_points.append(coords)
        self.draw_lasso_visual()

    def on_lasso_drag(self, event):
        if not self.lasso_active or not self.layers:
            return
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            return
        if len(self.lasso_points) == 0 or ((coords[0]-self.lasso_points[-1][0])**2 + (coords[1]-self.lasso_points[-1][1])**2) > 25:
            self.lasso_points.append(coords)
            self.draw_lasso_visual()

    def on_lasso_release(self, event):
        pass

    def on_lasso_close(self, event):
        if not self.lasso_active or len(self.lasso_points) < 3:
            return
        self.push_undo("Lasso selection")
        mask = self.create_lasso_mask()
        if mask:
            r = self.feather_radius.get()
            if r > 0:
                mask = mask.filter(ImageFilter.GaussianBlur(radius=r))
            self._last_wand_mask = mask
            cnt = self.count_mask_pixels(mask)
            self.status_var.set(f"Lasso selected {cnt} pixels, feather={r}. Press Delete Selected.")
            self.display_composite_with_mask(mask)
        self.lasso_active = False
        self.lasso_points = []
        self.clear_lasso_visual()

    def create_lasso_mask(self):
        if not self.layers or len(self.lasso_points) < 3:
            return None
        w,h = self.layers[self.active_layer_idx].image.size
        mask = Image.new("L", (w,h), 0)
        draw = ImageDraw.Draw(mask)
        draw.polygon(self.lasso_points, fill=255)
        return mask

    def draw_lasso_visual(self):
        self.clear_lasso_visual()
        if len(self.lasso_points) < 2:
            return
        for i in range(len(self.lasso_points)-1):
            p1 = self.image_to_canvas_coords(self.lasso_points[i][0], self.lasso_points[i][1])
            p2 = self.image_to_canvas_coords(self.lasso_points[i+1][0], self.lasso_points[i+1][1])
            if p1 and p2:
                line_id = self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#00ff00", width=2, dash=(3,3))
                self.lasso_canvas_ids.append(line_id)

    def clear_lasso_visual(self):
        for lid in self.lasso_canvas_ids:
            try:
                self.canvas.delete(lid)
            except:
                pass
        self.lasso_canvas_ids = []

    def apply_feather(self):
        if self._last_wand_mask is None:
            messagebox.showinfo("Feather", "Make a selection first (Wand or Lasso)")
            return
        self.push_undo(f"Feather {self.feather_radius.get()}px")
        r = self.feather_radius.get()
        if r > 0:
            self._last_wand_mask = self._last_wand_mask.filter(ImageFilter.GaussianBlur(radius=r))
            self.display_composite_with_mask(self._last_wand_mask)
            self.status_var.set(f"Feathered selection by {r}px!")

    def feather_dialog(self):
        if self._last_wand_mask is None:
            messagebox.showinfo("Feather", "Make a selection first")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Feather Selection")
        dialog.geometry("350x180")
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text="Feather radius (soft edge)", font=("Segoe UI", 10, "bold")).pack(pady=10)
        radius_var = tk.IntVar(value=self.feather_radius.get())
        tk.Scale(dialog, from_=0, to=50, orient="horizontal", variable=radius_var, length=250).pack()
        original_mask = self._last_wand_mask.copy()
        def preview(*args):
            r = radius_var.get()
            if r == 0:
                self._last_wand_mask = original_mask.copy()
            else:
                self._last_wand_mask = original_mask.filter(ImageFilter.GaussianBlur(radius=r))
            self.display_composite_with_mask(self._last_wand_mask)
        radius_var.trace_add("write", lambda *a: preview())
        def on_ok():
            self.feather_radius.set(radius_var.get())
            dialog.destroy()
        def on_cancel():
            self._last_wand_mask = original_mask
            self.display_composite_with_mask(self._last_wand_mask)
            dialog.destroy()
        row = tk.Frame(dialog)
        row.pack(pady=10)
        tk.Button(row, text="Cancel", command=on_cancel).pack(side="left", padx=6)
        tk.Button(row, text="OK", command=on_ok, bg="#6a5a9a", fg="white").pack(side="left", padx=6)

    def invert_selection(self):
        if self._last_wand_mask is None:
            return
        self.push_undo("Invert selection")
        self._last_wand_mask = ImageOps.invert(self._last_wand_mask)
        self.display_composite_with_mask(self._last_wand_mask)

    def clear_selection(self):
        self._last_wand_mask = None
        self.lasso_points = []
        self.lasso_active = False
        self.clear_lasso_visual()
        self.display_composite()
        self.status_var.set("Selection cleared")

    # MASKS
    def add_layer_mask(self):
        if not self.layers:
            return
        self.push_undo("Add layer mask")
        layer = self.layers[self.active_layer_idx]
        w,h = layer.image.size
        layer.mask = Image.new("L", (w,h), 255)
        self.refresh_layers_list()
        self.display_composite()
        self.status_var.set(f"Added white mask to {layer.name}.")

    def delete_layer_mask(self):
        if not self.layers or self.layers[self.active_layer_idx].mask is None:
            return
        self.push_undo("Delete mask")
        self.layers[self.active_layer_idx].mask = None
        self.mask_edit_mode.set(False)
        self.refresh_layers_list()
        self.display_composite()

    def apply_layer_mask(self):
        if not self.layers or self.layers[self.active_layer_idx].mask is None:
            return
        self.push_undo("Apply mask")
        layer = self.layers[self.active_layer_idx]
        img = layer.image.convert("RGBA")
        alpha = img.split()[3]
        m = layer.mask
        if m.size != alpha.size:
            m = m.resize(alpha.size, Image.LANCZOS)
        alpha = ImageChops.multiply(alpha, m)
        img.putalpha(alpha)
        layer.image = img
        layer.mask = None
        self.mask_edit_mode.set(False)
        self.refresh_layers_list()
        self.display_composite()

    # ===== TIER 4: GRADIENT =====
    def on_gradient_press(self, event):
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            return
        self.gradient_start = coords
        self.gradient_end = coords

    def on_gradient_drag(self, event):
        if self.gradient_start is None:
            return
        coords = self.canvas_to_image_coords(event.x, event.y)
        if coords is None:
            return
        self.gradient_end = coords
        # Draw preview line on canvas
        if self.gradient_preview_id:
            try:
                self.canvas.delete(self.gradient_preview_id)
            except:
                pass
        c1 = self.image_to_canvas_coords(self.gradient_start[0], self.gradient_start[1])
        c2 = self.image_to_canvas_coords(self.gradient_end[0], self.gradient_end[1])
        if c1 and c2:
            self.gradient_preview_id = self.canvas.create_line(c1[0], c1[1], c2[0], c2[1], fill="#00ffff", width=3, arrow=tk.LAST)

    def on_gradient_release(self, event):
        if self.gradient_start is None or self.gradient_end is None or not self.layers:
            return
        if self.gradient_preview_id:
            try:
                self.canvas.delete(self.gradient_preview_id)
            except:
                pass
            self.gradient_preview_id = None
        start = self.gradient_start
        end = self.gradient_end
        self.gradient_start = self.gradient_end = None
        if ((start[0]-end[0])**2 + (start[1]-end[1])**2) < 25:
            return
        self.push_undo("Gradient")
        self.apply_gradient(start, end)
        self.display_composite()

    def apply_gradient(self, start, end):
        layer = self.layers[self.active_layer_idx]
        w,h = layer.image.size
        # Parse colors
        def hex_to_rgb(hx):
            hx = hx.lstrip("#")
            return (int(hx[0:2],16), int(hx[2:4],16), int(hx[4:6],16))
        c1 = hex_to_rgb(self.brush_color)
        c2 = hex_to_rgb(self.gradient_color2)
        gtype = self.gradient_type.get()
        grad_img = Image.new("RGBA", (w,h), (0,0,0,0))
        if gtype == "linear":
            # Linear gradient along line start->end
            dx = end[0]-start[0]
            dy = end[1]-start[1]
            length = math.hypot(dx, dy)
            if length == 0:
                return
            # For each pixel, project onto gradient vector
            for y in range(h):
                for x in range(w):
                    # Vector from start to pixel
                    px = x - start[0]
                    py = y - start[1]
                    # Projection t = dot / |grad|^2
                    t = (px*dx + py*dy) / (length*length)
                    t = max(0.0, min(1.0, t))
                    r = int(c1[0]*(1-t) + c2[0]*t)
                    g = int(c1[1]*(1-t) + c2[1]*t)
                    b = int(c1[2]*(1-t) + c2[2]*t)
                    grad_img.putpixel((x,y), (r,g,b,255))
        else:  # radial
            cx, cy = start
            radius = math.hypot(end[0]-start[0], end[1]-start[1])
            if radius == 0:
                radius = 1
            for y in range(h):
                for x in range(w):
                    dist = math.hypot(x-cx, y-cy)
                    t = dist / radius
                    t = max(0.0, min(1.0, t))
                    r = int(c1[0]*(1-t) + c2[0]*t)
                    g = int(c1[1]*(1-t) + c2[1]*t)
                    b = int(c1[2]*(1-t) + c2[2]*t)
                    grad_img.putpixel((x,y), (r,g,b,255))
        # Composite gradient onto layer, respecting selection mask if any
        if self._last_wand_mask is not None and self._last_wand_mask.size == (w,h):
            layer_img = layer.image.convert("RGBA")
            # Use mask to blend gradient only in selected area
            layer_img = Image.composite(grad_img, layer_img, self._last_wand_mask)
            layer.image = layer_img
        else:
            # If mask edit mode, gradient goes to mask? No, to image
            # Alpha composite gradient over layer with opacity based on brush size? Simplify: paste with 100% opacity
            layer_img = layer.image.convert("RGBA")
            layer_img = Image.alpha_composite(layer_img, grad_img)
            layer.image = layer_img

    # ===== TIER 4: SHADOWS/HIGHLIGHTS =====
    def shadows_highlights_dialog(self):
        if not self.layers:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Shadows / Highlights (Tier 4)")
        dialog.geometry("420x300")
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text="Recover Shadows & Highlights", font=("Segoe UI", 11, "bold")).pack(pady=10)
        sh_var = tk.IntVar(value=30)
        hl_var = tk.IntVar(value=30)
        tk.Label(dialog, text="Shadows (brighten dark areas):").pack(anchor="w", padx=12)
        tk.Scale(dialog, from_=0, to=100, orient="horizontal", variable=sh_var, length=350).pack()
        tk.Label(dialog, text="Highlights (darken bright areas):").pack(anchor="w", padx=12)
        tk.Scale(dialog, from_=0, to=100, orient="horizontal", variable=hl_var, length=350).pack()
        original = self.layers[self.active_layer_idx].image.copy()
        def apply_sh(*args):
            img = original.copy().convert("RGBA")
            sh = sh_var.get() / 100.0
            hl = hl_var.get() / 100.0
            if sh == 0 and hl == 0:
                self.layers[self.active_layer_idx].image = img
                self.display_composite()
                return
            # Process each pixel: luminance based
            r,g,b,a = img.split()
            rgb = Image.merge("RGB", (r,g,b))
            # Apply shadows/highlights via simple curves
            def sh_map(p):
                # p 0-255, luminance approx
                # Brighten shadows: increase low values
                if p < 128:
                    factor = (128 - p) / 128.0
                    p = p + int(factor * sh * 80)
                # Darken highlights: decrease high values
                if p > 128:
                    factor = (p - 128) / 127.0
                    p = p - int(factor * hl * 60)
                return max(0, min(255, p))
            r = r.point(sh_map); g = g.point(sh_map); b = b.point(sh_map)
            img = Image.merge("RGBA", (r,g,b,a))
            self.layers[self.active_layer_idx].image = img
            self.display_composite()
        sh_var.trace_add("write", lambda *a: apply_sh())
        hl_var.trace_add("write", lambda *a: apply_sh())
        def on_ok(): dialog.destroy()
        def on_cancel():
            self.layers[self.active_layer_idx].image = original
            self.display_composite()
            dialog.destroy()
        row = tk.Frame(dialog)
        row.pack(pady=12)
        tk.Button(row, text="Cancel", command=on_cancel, width=10).pack(side="left", padx=6)
        tk.Button(row, text="OK", command=on_ok, bg="#7a6a4a", fg="white", width=10).pack(side="left", padx=6)

    def vignette_dialog(self):
        if not self.layers:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Vignette (Tier 4)")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text="Vignette - darken edges", font=("Segoe UI", 11, "bold")).pack(pady=10)
        strength = tk.IntVar(value=40)
        tk.Label(dialog, text="Strength:").pack(anchor="w", padx=12)
        tk.Scale(dialog, from_=0, to=100, orient="horizontal", variable=strength, length=350).pack()
        original = self.layers[self.active_layer_idx].image.copy()
        def apply_vig(*args):
            img = original.copy().convert("RGBA")
            s = strength.get() / 100.0
            if s == 0:
                self.layers[self.active_layer_idx].image = img
                self.display_composite()
                return
            w,h = img.size
            # Create vignette mask: radial gradient dark at edges
            vig = Image.new("L", (w,h), 0)
            cx, cy = w//2, h//2
            max_dist = math.hypot(cx, cy)
            for y in range(h):
                for x in range(w):
                    dist = math.hypot(x-cx, y-cy) / max_dist
                    # dist 0 center, 1 corner
                    # vignette: darken proportional to dist^2 * strength
                    darken = int((dist**1.8) * s * 180)
                    vig.putpixel((x,y), min(255, darken))
            # Darken image by vignette
            # Create black overlay with vignette alpha
            black = Image.new("RGBA", (w,h), (0,0,0,255))
            img = Image.composite(black, img, vig) if False else img  # We'll use blend
            # Simpler: multiply brightness by (1 - darken/255)
            r,g,b,a = img.split()
            def vig_map_factory(darken_img):
                # Not efficient per pixel but okay for demo
                return darken_img
            # Use ImageChops? Let's do pixel loop for small images, for large use faster
            # Fast version: create darkened version
            dark_factor = 1.0 - s*0.7
            # Apply radial darkening via alpha composite
            overlay = Image.new("RGBA", (w,h), (0,0,0,0))
            draw = ImageDraw.Draw(overlay)
            # Draw black with varying alpha? Use vig as alpha
            overlay.putalpha(vig)
            # Composite black over image with vignette alpha
            img = Image.alpha_composite(img, overlay)
            self.layers[self.active_layer_idx].image = img
            self.display_composite()
        strength.trace_add("write", lambda *a: apply_vig())
        def on_ok(): dialog.destroy()
        def on_cancel():
            self.layers[self.active_layer_idx].image = original
            self.display_composite()
            dialog.destroy()
        row = tk.Frame(dialog)
        row.pack(pady=12)
        tk.Button(row, text="Cancel", command=on_cancel, width=10).pack(side="left", padx=6)
        tk.Button(row, text="OK", command=on_ok, bg="#4a4a7a", fg="white", width=10).pack(side="left", padx=6)

    def auto_crop_content(self):
        if not self.layers:
            return
        # Find bounding box of non-transparent pixels in composite or active layer
        self.push_undo("Auto Crop to Content")
        comp = self.get_composite()
        if comp is None:
            return
        # Use alpha to find content bounds
        if comp.mode != "RGBA":
            comp = comp.convert("RGBA")
        alpha = comp.split()[3]
        bbox = alpha.getbbox()
        if bbox is None:
            messagebox.showinfo("Auto Crop", "Image is fully transparent")
            return
        # Add small padding
        pad = 5
        x0,y0,x1,y1 = bbox
        x0 = max(0, x0-pad); y0 = max(0, y0-pad)
        x1 = min(comp.size[0], x1+pad); y1 = min(comp.size[1], y1+pad)
        # Crop all layers
        for layer in self.layers:
            layer.image = layer.image.crop((x0,y0,x1,y1))
            if layer.mask is not None:
                layer.mask = layer.mask.crop((x0,y0,x1,y1))
        self.display_composite()
        self.update_resize_entries()
        self.status_var.set(f"Auto-cropped to content: {x1-x0}x{y1-y0} from {comp.size[0]}x{comp.size[1]}")

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
        # TIER 6B: Now creates editable text layer instead of painting directly
        text = simpledialog.askstring("Add Editable Text (TIER 6B)", "Enter text (will be editable layer):", initialvalue="Hello Tola!")
        if not text:
            return
        x = None; y = None
        if prefill_pos:
            x, y = prefill_pos
        self.add_text_layer(text, x, y)
        self.status_var.set(f"TIER 6B: Added editable text layer '{text[:20]}' - double-click layer to edit!")

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
        menu.add_command(label="Feather Selection", command=self.feather_dialog)
        menu.add_command(label="Clear Selection", command=self.clear_selection)
        menu.add_command(label="Shadows/Highlights", command=self.shadows_highlights_dialog)
        menu.tk_popup(event.x_root, event.y_root)

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
        # Draw rule-of-thirds guides (Tier4)
        mid_x = (x0+x1)//2
        mid_y = (y0+y1)//2
        self.canvas.create_line(x0, mid_y, x1, mid_y, fill="#ffffff", dash=(2,2))
        self.canvas.create_line(mid_x, y0, mid_x, y1, fill="#ffffff", dash=(2,2))

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
                    if layer.mask is not None:
                        layer.mask = layer.mask.crop((ix0,iy0,ix1,iy1))
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
                if layer.mask is not None:
                    layer.mask = layer.mask.resize((new_w, new_h), Image.LANCZOS)
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
        def on_ok(): dialog.destroy()
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

    # ===== TIER 4.5: AI PROMPT GENERATION =====
    def ai_open_generators_folder(self):
        try:
            os.makedirs(self.ai_generators_dir, exist_ok=True)
            os.startfile(self.ai_generators_dir)
        except Exception as e:
            # Cross-platform
            try:
                import subprocess, sys
                if sys.platform == "darwin":
                    subprocess.Popen(["open", self.ai_generators_dir])
                else:
                    subprocess.Popen(["xdg-open", self.ai_generators_dir])
            except:
                messagebox.showinfo("Generators Folder", f"Folder: {self.ai_generators_dir}\n\nPlace .py files there that define register(editor) to add custom AI generators!")

    def ai_manage_providers_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage AI Providers - Modular System")
        dialog.geometry("700x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        tk.Label(dialog, text="AI Providers - Enable/Disable & Add Custom", font=("Segoe UI", 12, "bold")).pack(pady=10)
        tk.Label(dialog, text="Check enabled providers will be tried in Auto mode. Add new ones via custom API or .py files in ai_generators/", wraplength=650, justify="left").pack(pady=2)
        
        # List frame with checkboxes
        list_frame = tk.Frame(dialog)
        list_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        canvas = tk.Canvas(list_frame)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable = tk.Frame(canvas)
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0,0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        vars_dict = {}
        for pid in self.ai_provider_order:
            info = self.ai_providers.get(pid, {})
            row = tk.Frame(scrollable, relief="groove", borderwidth=1)
            row.pack(fill="x", pady=2, padx=2)
            
            var = tk.BooleanVar(value=info.get("enabled", True))
            vars_dict[pid] = var
            tk.Checkbutton(row, variable=var).pack(side="left")
            tk.Label(row, text=info.get("name",""), font=("Segoe UI", 9, "bold"), width=35, anchor="w").pack(side="left", padx=5)
            tk.Label(row, text=info.get("description","")[:60], font=("Segoe UI", 7), fg="#666666", width=45, anchor="w").pack(side="left")
            tk.Label(row, text="FREE" if info.get("free") else "$", fg="green" if info.get("free") else "orange", font=("Segoe UI", 8, "bold")).pack(side="left", padx=5)
        
        # Add custom provider section
        add_frame = tk.LabelFrame(dialog, text="Add Custom API Provider (No Coding)", padx=8, pady=6)
        add_frame.pack(fill="x", padx=10, pady=8)
        
        tk.Label(add_frame, text="Name:").grid(row=0, column=0, sticky="w")
        custom_name_var = tk.StringVar(value="My Custom Generator")
        tk.Entry(add_frame, textvariable=custom_name_var, width=20).grid(row=0, column=1, padx=5)
        
        tk.Label(add_frame, text="API URL (use {prompt}, {width}, {height}):").grid(row=0, column=2, sticky="w", padx=(10,0))
        custom_url_var = tk.StringVar(value="https://image.pollinations.ai/prompt/{prompt}?width={width}&height={height}&nologo=true")
        tk.Entry(add_frame, textvariable=custom_url_var, width=40).grid(row=0, column=3, padx=5)
        
        def add_custom():
            custom = {
                "id": f"custom_{len(self.ai_providers)}",
                "name": custom_name_var.get(),
                "url": custom_url_var.get(),
                "description": f"Custom API: {custom_url_var.get()[:40]}",
                "enabled": True
            }
            self.register_custom_api_provider(custom)
            # Save to config
            try:
                import json
                cfg = {}
                if os.path.exists(self.ai_config_path):
                    with open(self.ai_config_path, "r") as f:
                        cfg = json.load(f)
                cfg.setdefault("custom_providers", []).append(custom)
                with open(self.ai_config_path, "w") as f:
                    json.dump(cfg, f, indent=2)
                messagebox.showinfo("Added", f"Added custom provider: {custom['name']}\nRestart dialog to see it!")
            except Exception as e:
                messagebox.showerror("Error", str(e))
        
        tk.Button(add_frame, text="+ Add Custom Provider", command=add_custom, bg="#4a7a4a", fg="white").grid(row=0, column=4, padx=10)
        
        def save_and_close():
            # Save enabled states
            try:
                import json
                cfg = {}
                if os.path.exists(self.ai_config_path):
                    with open(self.ai_config_path, "r") as f:
                        cfg = json.load(f)
                cfg["providers_enabled"] = {pid: var.get() for pid, var in vars_dict.items()}
                with open(self.ai_config_path, "w") as f:
                    json.dump(cfg, f, indent=2)
                # Apply to current providers
                for pid, var in vars_dict.items():
                    if pid in self.ai_providers:
                        self.ai_providers[pid]["enabled"] = var.get()
                messagebox.showinfo("Saved", "Provider settings saved! Auto mode will now use only enabled providers.")
            except Exception as e:
                messagebox.showerror("Error", str(e))
            dialog.destroy()
        
        btn_row = tk.Frame(dialog)
        btn_row.pack(pady=10)
        tk.Button(btn_row, text="Cancel", command=dialog.destroy, width=10).pack(side="left", padx=5)
        tk.Button(btn_row, text="Open Generators Folder", command=self.ai_open_generators_folder, bg="#4a4a4a", fg="white").pack(side="left", padx=5)
        tk.Button(btn_row, text="Save & Close", command=save_and_close, bg="#4a7a9a", fg="white", width=15).pack(side="left", padx=5)

    def ai_setup_keys_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("AI Setup")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text="AI Image Generation Setup", font=("Segoe UI", 12, "bold")).pack(pady=10)
        tk.Label(dialog, text="For REAL AI images (not procedural demo), you need:", font=("Segoe UI", 9), wraplength=450, justify="left").pack(pady=5, padx=10)
        text = tk.Text(dialog, height=10, wrap="word")
        text.pack(fill="both", expand=True, padx=10, pady=5)
        instructions = """Option 1 - FREE Local (Recommended for class):
  pip install diffusers transformers torch accelerate
  Then it will use Stable Diffusion locally.

Option 2 - OpenAI DALL-E (Best quality, costs money):
  1. Get API key from platform.openai.com
  2. pip install openai
  3. Paste key below

Option 3 - Demo Mode (Current):
  No install needed! Uses procedural generation based on your prompt keywords.
  Example prompts:
  - 'sunset over mountains' -> orange/purple gradient
  - 'ocean waves' -> blue tones
  - 'forest at night' -> green dark
  - 'cyberpunk city' -> neon

Current Status:"""
        text.insert("1.0", instructions)
        # Check what's installed
        status = "\n"
        try:
            import diffusers
            status += "✓ diffusers installed - Local SD available\n"
        except:
            status += "✗ diffusers NOT installed (pip install diffusers)\n"
        try:
            import openai
            status += "✓ openai installed\n"
        except:
            status += "✗ openai NOT installed\n"
        try:
            from rembg import remove
            status += "✓ rembg installed - BG removal works\n"
        except:
            status += "✗ rembg NOT installed\n"
        text.insert("end", status)
        text.config(state="disabled")

        # HuggingFace token
        hf_row = tk.Frame(dialog)
        hf_row.pack(fill="x", padx=10, pady=5)
        tk.Label(hf_row, text="HF Token (FREE - huggingface.co/settings/tokens):").pack(side="left")
        hf_var = tk.StringVar(value="")
        try:
            import json
            if os.path.exists(os.path.expanduser("~/.imageeditor_ai.json")):
                with open(os.path.expanduser("~/.imageeditor_ai.json"), "r") as f:
                    data = json.load(f)
                    hf_var.set(data.get("hf_token", ""))
        except:
            pass
        tk.Entry(hf_row, textvariable=hf_var, width=25).pack(side="left", padx=5, fill="x", expand=True)

        key_row = tk.Frame(dialog)
        key_row.pack(fill="x", padx=10, pady=8)
        tk.Label(key_row, text="OpenAI API Key:").pack(side="left")
        key_var = tk.StringVar(value=self.ai_api_key)
        tk.Entry(key_row, textvariable=key_var, width=35, show="*").pack(side="left", padx=5, fill="x", expand=True)
        def save_key():
            self.ai_api_key = key_var.get()
            try:
                import json
                data = {}
                if os.path.exists(os.path.expanduser("~/.imageeditor_ai.json")):
                    with open(os.path.expanduser("~/.imageeditor_ai.json"), "r") as f:
                        data = json.load(f)
                data["openai_key"] = key_var.get()
                data["hf_token"] = hf_var.get()
                with open(os.path.expanduser("~/.imageeditor_ai.json"), "w") as f:
                    json.dump(data, f)
                messagebox.showinfo("Saved", f"Keys saved!\nOpenAI: {'set' if key_var.get() else 'empty'}\nHF: {'set' if hf_var.get() else 'empty (optional, Pollinations works without)'}")
            except Exception as e:
                messagebox.showerror("Error", str(e))
            dialog.destroy()
        tk.Button(key_row, text="Save", command=save_key, bg="#4a7a9a", fg="white").pack(side="left", padx=4)
        tk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=6)

    def ai_prompt_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("✨ AI Generate Image from Prompt - Tier 4.5")
        dialog.geometry("600x520")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg="#1e1e1e")

        header = tk.Frame(dialog, bg="#1a2a3a", height=50)
        header.pack(fill="x")
        tk.Label(header, text="✨ AI Image Prompt Generator", font=("Segoe UI", 14, "bold"), bg="#1a2a3a", fg="#7ab8ff").pack(pady=10)
        tk.Label(header, text="Integrated into AI pipeline - generates as new layer!", font=("Segoe UI", 8), bg="#1a2a3a", fg="#aaaaaa").pack()

        # Prompt
        prompt_frame = tk.Frame(dialog, bg="#1e1e1e")
        prompt_frame.pack(fill="x", padx=15, pady=10)
        tk.Label(prompt_frame, text="Prompt (describe what you want):", bg="#1e1e1e", fg="white", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        prompt_text = tk.Text(prompt_frame, height=3, bg="#2a2a2a", fg="white", insertbackground="white", font=("Segoe UI", 10), wrap="word")
        prompt_text.pack(fill="x", pady=5)
        prompt_text.insert("1.0", self.ai_prompt.get())

        tk.Label(prompt_frame, text="Negative Prompt (what to avoid):", bg="#1e1e1e", fg="#aaaaaa", font=("Segoe UI", 8)).pack(anchor="w", pady=(8,0))
        neg_entry = tk.Entry(prompt_frame, textvariable=self.ai_negative_prompt, bg="#2a2a2a", fg="#aaaaaa")
        neg_entry.pack(fill="x", pady=2)

        # Options row
        opts = tk.Frame(dialog, bg="#1e1e1e")
        opts.pack(fill="x", padx=15, pady=5)
        tk.Label(opts, text="Style:", bg="#1e1e1e", fg="#cccccc").pack(side="left")
        style_var = tk.StringVar(value=self.ai_style.get())
        style_combo = ttk.Combobox(opts, textvariable=style_var, values=["Realistic", "Digital Art", "Anime", "Oil Painting", "Cyberpunk", "Fantasy", "Minimal", "Photographic"], width=14, state="readonly")
        style_combo.pack(side="left", padx=5)
        tk.Label(opts, text="Width:", bg="#1e1e1e", fg="#cccccc").pack(side="left", padx=(15,2))
        w_var = tk.IntVar(value=self.ai_prompt_width.get())
        tk.Entry(opts, textvariable=w_var, width=5, bg="#2a2a2a", fg="white").pack(side="left")
        tk.Label(opts, text="Height:", bg="#1e1e1e", fg="#cccccc").pack(side="left", padx=2)
        h_var = tk.IntVar(value=self.ai_prompt_height.get())
        tk.Entry(opts, textvariable=h_var, width=5, bg="#2a2a2a", fg="white").pack(side="left")

        # Model selection
        model_frame = tk.Frame(dialog, bg="#1e1e1e")
        model_frame.pack(fill="x", padx=15, pady=5)
        tk.Label(model_frame, text="AI Engine:", bg="#1e1e1e", fg="#cccccc", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        engine_var = tk.StringVar(value="Auto (best available)")
        engine_combo = ttk.Combobox(model_frame, textvariable=engine_var, values=["Auto (best available) - NOW WITH FREE ONLINE AI!", "FREE Online AI (Pollinations - No Install!)", "HuggingFace Free API", "Local Stable Diffusion (diffusers)", "OpenAI DALL-E 3 (needs API key)", "Procedural Demo (no install)"], width=50, state="readonly")
        engine_combo.pack(fill="x", pady=2)

        status_var = tk.StringVar(value="Ready to generate! Your prompt will become a new layer.")
        status_label = tk.Label(dialog, textvariable=status_var, bg="#1e1e1e", fg="#7ab8ff", font=("Segoe UI", 8), wraplength=550)
        status_label.pack(pady=5)

        def do_generate():
            prompt = prompt_text.get("1.0", "end-1c").strip()
            if not prompt:
                messagebox.showinfo("Prompt", "Enter a prompt!")
                return
            self.ai_prompt.set(prompt)
            self.ai_style.set(style_var.get())
            self.ai_prompt_width.set(w_var.get())
            self.ai_prompt_height.set(h_var.get())
            status_var.set(f"Generating '{prompt[:40]}...' with {style_var.get()} style...")
            dialog.update()
            try:
                width = max(64, min(1024, w_var.get()))
                height = max(64, min(1024, h_var.get()))
                engine = engine_var.get()
                img = self.ai_generate_from_prompt(prompt, width, height, style_var.get(), engine, status_var)
                if img:
                    self.push_undo(f"AI Generate: {prompt[:20]}")
                    # Add as new layer
                    new_layer = Layer(f"AI: {prompt[:25]}", img.convert("RGBA"))
                    self.layers.append(new_layer)
                    self.active_layer_idx = len(self.layers)-1
                    self.refresh_layers_list()
                    self.display_composite()
                    self.status_var.set(f"✨ AI Generated: {prompt[:40]} -> new layer! Style: {style_var.get()}")
                    status_var.set("Done! Added as new layer. Close this dialog.")
            except Exception as e:
                import traceback
                traceback.print_exc()
                messagebox.showerror("AI Generate Error", str(e))
                status_var.set(f"Error: {e}")

        btn_row = tk.Frame(dialog, bg="#1e1e1e")
        btn_row.pack(fill="x", padx=15, pady=12)
        tk.Button(btn_row, text="Cancel", command=dialog.destroy, width=10).pack(side="left", padx=5)
        tk.Button(btn_row, text="Setup / Install Help", command=self.ai_setup_keys_dialog, bg="#4a4a4a", fg="white").pack(side="left", padx=5)
        tk.Button(btn_row, text="✨ GENERATE AS NEW LAYER", command=do_generate, bg="#5a8aff", fg="white", font=("Segoe UI", 11, "bold"), width=25).pack(side="right", padx=5)

    def ai_generate_from_prompt(self, prompt, width, height, style, engine, status_var=None):
        # Modular plugin system - tries enabled providers in order
        # Engine string can be "Auto" or specific provider name
        
        # If specific engine requested, try that first
        if engine and "Auto" not in engine and "best available" not in engine:
            # Find provider by name match
            for pid, info in self.ai_providers.items():
                if info["name"].lower() in engine.lower() or pid.lower() in engine.lower():
                    if info.get("enabled", True):
                        try:
                            if status_var:
                                status_var.set(f"Trying {info['name']}...")
                            img = info["func"](prompt, width, height, style, status_var)
                            if img:
                                return img
                        except Exception as e:
                            if status_var:
                                status_var.set(f"{info['name']} failed: {e}")
                            print(f"{pid} failed: {e}")
        
        # Auto mode: try all enabled providers in order
        for pid in self.ai_provider_order:
            info = self.ai_providers.get(pid)
            if not info or not info.get("enabled", True):
                continue
            # Skip providers needing key if no key
            if info.get("needs_key"):
                key_name = info.get("key_name", "openai_key")
                try:
                    import json
                    has_key = False
                    if os.path.exists(self.ai_config_path):
                        with open(self.ai_config_path, "r") as f:
                            cfg = json.load(f)
                            has_key = bool(cfg.get(key_name))
                    if not has_key and key_name == "openai_key":
                        has_key = bool(self.ai_api_key)
                    if not has_key:
                        continue
                except:
                    continue
            
            try:
                if status_var:
                    status_var.set(f"Trying {info['name']}...")
                img = info["func"](prompt, width, height, style, status_var)
                if img:
                    if status_var:
                        status_var.set(f"✓ Generated with {info['name']}!")
                    return img
            except Exception as e:
                print(f"Provider {pid} failed: {e}")
                if status_var:
                    status_var.set(f"{info['name']} failed, trying next...")
        
        # Last resort procedural (now no watermark!)
        if status_var:
            status_var.set("Using procedural fallback (no watermark)...")
        return self.ai_generate_procedural(prompt, width, height, style)

    def ai_generate_pollinations(self, prompt, width, height, style, status_var=None):
        # Pollinations - FREE, no watermark, no key - BEST FOR DEFAULT
        import requests
        from io import BytesIO
        import urllib.parse
        full_prompt = f"{prompt}, {style} style, highly detailed, 8k, photorealistic, sharp focus"
        encoded = urllib.parse.quote(full_prompt)
        # Random seed for variety but deterministic per prompt if you want
        seed = abs(hash(prompt)) % 1000000
        url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true&seed={seed}&enhance=true"
        if status_var:
            status_var.set("Calling Pollinations FREE AI (no watermark)...")
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200 and len(resp.content) > 1000:
            img = Image.open(BytesIO(resp.content)).convert("RGBA")
            # AUTO-REMOVE WATERMARK: Pollinations still adds logo despite nologo=true
            try:
                w,h = img.size
                # Crop bottom 7% where watermark lives
                crop_h = int(h * 0.93)
                img_cropped = img.crop((0, 0, w, crop_h))
                img = img_cropped.resize((w, h), Image.LANCZOS)
            except:
                pass
            # Resize to exact requested size
            if img.size != (width, height):
                img = img.resize((width, height), Image.LANCZOS)
            return img
        else:
            raise Exception(f"Pollinations {resp.status_code}")

    def ai_generate_stability(self, prompt, width, height, style, status_var=None):
        # Stability AI API
        import requests
        from io import BytesIO
        import json
        stability_key = ""
        try:
            if os.path.exists(self.ai_config_path):
                with open(self.ai_config_path, "r") as f:
                    cfg = json.load(f)
                    stability_key = cfg.get("stability_key", "")
        except:
            pass
        if not stability_key:
            raise Exception("No stability_key in config")
        
        url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {stability_key}"
        }
        payload = {
            "text_prompts": [{"text": f"{prompt}, {style} style"}],
            "cfg_scale": 7,
            "height": height,
            "width": width,
            "steps": 30,
        }
        if status_var:
            status_var.set("Calling Stability AI...")
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            import base64
            img_data = base64.b64decode(data["artifacts"][0]["base64"])
            img = Image.open(BytesIO(img_data)).convert("RGBA")
            return img
        else:
            raise Exception(f"Stability {resp.status_code}: {resp.text[:200]}")

    def ai_generate_replicate(self, prompt, width, height, style, status_var=None):
        # Replicate API - supports many models
        import requests
        import time
        from io import BytesIO
        import json
        replicate_key = ""
        try:
            if os.path.exists(self.ai_config_path):
                with open(self.ai_config_path, "r") as f:
                    cfg = json.load(f)
                    replicate_key = cfg.get("replicate_key", "")
        except:
            pass
        if not replicate_key:
            raise Exception("No replicate_key")
        
        # Example: SDXL model
        url = "https://api.replicate.com/v1/predictions"
        headers = {"Authorization": f"Token {replicate_key}", "Content-Type": "application/json"}
        payload = {
            "version": "39ed52f2a227617c90befa27b5b37c55b18b997",  # SDXL
            "input": {"prompt": f"{prompt}, {style} style", "width": width, "height": height}
        }
        if status_var:
            status_var.set("Calling Replicate...")
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code != 201:
            raise Exception(f"Replicate create {resp.status_code}")
        pred = resp.json()
        # Poll for result
        for _ in range(30):
            time.sleep(2)
            r = requests.get(pred["urls"]["get"], headers=headers, timeout=15)
            data = r.json()
            if data["status"] == "succeeded":
                img_url = data["output"][0]
                img_resp = requests.get(img_url, timeout=30)
                return Image.open(BytesIO(img_resp.content)).convert("RGBA").resize((width,height), Image.LANCZOS)
            elif data["status"] == "failed":
                raise Exception("Replicate failed")
        raise Exception("Replicate timeout")

    def ai_generate_automatic1111(self, prompt, width, height, style, status_var=None):
        # Automatic1111 WebUI API - most popular local SD UI
        # Requires: A1111 running with --api --listen
        # Start A1111: webui.bat --api --listen
        import requests
        from io import BytesIO
        import base64
        
        # Config - allow custom URL from config
        a1111_url = "http://127.0.0.1:7860"
        try:
            import json
            if os.path.exists(self.ai_config_path):
                with open(self.ai_config_path, "r") as f:
                    cfg = json.load(f)
                    a1111_url = cfg.get("a1111_url", a1111_url)
        except:
            pass
        
        url = f"{a1111_url}/sdapi/v1/txt2img"
        
        # Check if A1111 is running
        try:
            if status_var:
                status_var.set(f"Connecting to Automatic1111 at {a1111_url}...")
            # Quick health check
            health = requests.get(f"{a1111_url}/sdapi/v1/sd-models", timeout=2)
            if health.status_code != 200:
                raise Exception("A1111 not responding")
        except Exception as e:
            raise Exception(f"Automatic1111 not running at {a1111_url}. Start it with: webui.bat --api --listen\nError: {e}")
        
        payload = {
            "prompt": f"{prompt}, {style} style, highly detailed, 8k, photorealistic",
            "negative_prompt": self.ai_negative_prompt.get() or "blurry, low quality, watermark, text",
            "width": width,
            "height": height,
            "steps": 20,
            "cfg_scale": 7,
            "sampler_name": "DPM++ 2M Karras",
            "batch_size": 1,
            "n_iter": 1,
            "enable_hr": False,
        }
        
        if status_var:
            status_var.set(f"A1111 generating: {prompt[:40]}... (local GPU)")
        
        resp = requests.post(url, json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            # A1111 returns base64 images
            img_b64 = data["images"][0]
            # Remove data URL prefix if present
            if "," in img_b64:
                img_b64 = img_b64.split(",")[1]
            img_data = base64.b64decode(img_b64)
            img = Image.open(BytesIO(img_data)).convert("RGBA")
            return img
        else:
            raise Exception(f"A1111 API error {resp.status_code}: {resp.text[:300]}")

    def ai_generate_comfyui(self, prompt, width, height, style, status_var=None):
        # ComfyUI API - powerful node-based workflow
        # Requires: ComfyUI running (python main.py)
        import requests
        import json
        from io import BytesIO
        import time
        import uuid
        
        comfy_url = "http://127.0.0.1:8188"
        try:
            if os.path.exists(self.ai_config_path):
                with open(self.ai_config_path, "r") as f:
                    cfg = json.load(f)
                    comfy_url = cfg.get("comfy_url", comfy_url)
        except:
            pass
        
        # Check if ComfyUI is running
        try:
            if status_var:
                status_var.set(f"Connecting to ComfyUI at {comfy_url}...")
            health = requests.get(f"{comfy_url}/system_stats", timeout=2)
        except Exception as e:
            raise Exception(f"ComfyUI not running at {comfy_url}. Start ComfyUI with: python main.py\nError: {e}")
        
        # Simple workflow: Text prompt -> SD -> VAE Decode -> Save
        # This is a minimal workflow for txt2img
        client_id = str(uuid.uuid4())
        workflow = {
            "3": {
                "inputs": {
                    "seed": abs(hash(prompt)) % 1000000000,
                    "steps": 20,
                    "cfg": 7,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                },
                "class_type": "KSampler"
            },
            "4": {
                "inputs": {
                    "ckpt_name": "v1-5-pruned-emaonly.ckpt"  # User needs this model
                },
                "class_type": "CheckpointLoaderSimple"
            },
            "5": {
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1
                },
                "class_type": "EmptyLatentImage"
            },
            "6": {
                "inputs": {
                    "text": f"{prompt}, {style} style, highly detailed",
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode"
            },
            "7": {
                "inputs": {
                    "text": self.ai_negative_prompt.get() or "watermark, text, blurry",
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode"
            },
            "8": {
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                },
                "class_type": "VAEDecode"
            },
            "9": {
                "inputs": {
                    "filename_prefix": "ImageEditor_ComfyUI",
                    "images": ["8", 0]
                },
                "class_type": "SaveImage"
            }
        }
        
        if status_var:
            status_var.set(f"ComfyUI generating: {prompt[:40]}...")
        
        # Queue prompt
        payload = {"prompt": workflow, "client_id": client_id}
        resp = requests.post(f"{comfy_url}/prompt", json=payload, timeout=10)
        if resp.status_code != 200:
            raise Exception(f"ComfyUI queue error {resp.status_code}: {resp.text[:300]}")
        
        prompt_id = resp.json()["prompt_id"]
        
        # Poll for result via websocket or history
        # Simple polling: check history
        for _ in range(60):  # 60 attempts = 2 minutes
            time.sleep(2)
            hist_resp = requests.get(f"{comfy_url}/history/{prompt_id}", timeout=10)
            if hist_resp.status_code == 200:
                hist = hist_resp.json()
                if prompt_id in hist:
                    outputs = hist[prompt_id].get("outputs", {})
                    if "9" in outputs and outputs["9"].get("images"):
                        # Get image
                        img_info = outputs["9"]["images"][0]
                        img_url = f"{comfy_url}/view?filename={img_info['filename']}&subfolder={img_info.get('subfolder','')}&type={img_info.get('type','output')}"
                        img_resp = requests.get(img_url, timeout=30)
                        if img_resp.status_code == 200:
                            img = Image.open(BytesIO(img_resp.content)).convert("RGBA")
                            # Resize if needed
                            if img.size != (width, height):
                                img = img.resize((width, height), Image.LANCZOS)
                            return img
        raise Exception("ComfyUI timeout - image not ready in 2 minutes")



    def ai_generate_huggingface(self, prompt, width, height, style, status_var=None):
        # FREE HuggingFace Inference API - works without local install!
        # Get free token from huggingface.co/settings/tokens (read-only)
        try:
            import requests
            from io import BytesIO
            
            # Try without token first (public), then with token if available
            hf_token = ""
            try:
                import json
                if os.path.exists(os.path.expanduser("~/.imageeditor_ai.json")):
                    with open(os.path.expanduser("~/.imageeditor_ai.json"), "r") as f:
                        data = json.load(f)
                        hf_token = data.get("hf_token", "") or data.get("huggingface_token", "")
            except:
                pass
            
            # Use Pollinations or HuggingFace free endpoint
            # Option 1: Pollinations AI (completely free, no key)
            try:
                if status_var:
                    status_var.set("Calling FREE online AI (Pollinations)...")
                # Pollinations - free, no API key needed!
                full_prompt = f"{prompt}, {style} style, highly detailed, 8k, photorealistic"
                # URL encode prompt
                import urllib.parse
                encoded = urllib.parse.quote(full_prompt)
                url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true&seed={hash(prompt) % 100000}"
                
                resp = requests.get(url, timeout=30)
                if resp.status_code == 200:
                    img = Image.open(BytesIO(resp.content)).convert("RGBA")
                    img = img.resize((width, height), Image.LANCZOS)
                    # AUTO-REMOVE WATERMARK: Pollinations still adds small logo despite nologo=true
                    # Crop bottom 28px where logo lives, then resize back to clean
                    try:
                        w,h = img.size
                        # Check if bottom-right has watermark (white text) - crop it
                        # Crop 5% from bottom and scale back up to remove logo
                        crop_h = int(h * 0.93)  # Keep 93% of height, remove bottom 7% where logo is
                        img_cropped = img.crop((0, 0, w, crop_h))
                        img = img_cropped.resize((width, height), Image.LANCZOS)
                    except:
                        pass
                    if status_var:
                        status_var.set("✓ Got REAL AI image from FREE online API (watermark removed)!")
                    return img
            except Exception as e:
                print(f"Pollinations failed: {e}")
            
            # Option 2: HuggingFace Inference API
            API_URL = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
            headers = {}
            if hf_token:
                headers["Authorization"] = f"Bearer {hf_token}"
            
            full_prompt = f"{prompt}, {style} style, highly detailed"
            if status_var:
                status_var.set(f"Calling HuggingFace SD: {full_prompt[:40]}...")
            
            payload = {"inputs": full_prompt, "parameters": {"width": width, "height": height}}
            response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
            
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGBA")
                return img
            else:
                print(f"HF API error {response.status_code}: {response.text[:200]}")
                raise Exception(f"HF API {response.status_code}")
                
        except Exception as e:
            print(f"HuggingFace generation error: {e}")
            raise


    def ai_generate_openai_dalle(self, prompt, width, height, style, status_var=None):
        try:
            import openai
            if not self.ai_api_key:
                return None
            client = openai.OpenAI(api_key=self.ai_api_key)
            full_prompt = f"{prompt}, {style} style, highly detailed, 8k"
            # DALL-E 3 sizes
            size = "1024x1024"
            if width <= 512 and height <= 512:
                size = "1024x1024"
            elif width > height:
                size = "1792x1024"
            else:
                size = "1024x1792"
            if status_var:
                status_var.set(f"Calling OpenAI DALL-E 3: {full_prompt[:50]}...")
            response = client.images.generate(
                model="dall-e-3",
                prompt=full_prompt,
                size=size,
                quality="standard",
                n=1
            )
            import requests
            from io import BytesIO
            image_url = response.data[0].url
            if status_var:
                status_var.set("Downloading generated image...")
            resp = requests.get(image_url)
            img = Image.open(BytesIO(resp.content)).convert("RGBA")
            img = img.resize((width, height), Image.LANCZOS)
            return img
        except Exception as e:
            print(f"OpenAI DALL-E error: {e}")
            raise

    def ai_generate_stable_diffusion(self, prompt, width, height, style, status_var=None):
        try:
            from diffusers import StableDiffusionPipeline
            import torch
            if status_var:
                status_var.set("Loading Stable Diffusion model (first time downloads ~4GB)...")
            model_id = "runwayml/stable-diffusion-v1-5"
            # Use smaller model if available
            pipe = StableDiffusionPipeline.from_pretrained(model_id, torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32)
            if torch.cuda.is_available():
                pipe = pipe.to("cuda")
            full_prompt = f"{prompt}, {style} style, highly detailed"
            if status_var:
                status_var.set(f"Generating with SD: {full_prompt[:40]}...")
            image = pipe(full_prompt, width=width, height=height, num_inference_steps=20).images[0]
            return image.convert("RGBA")
        except Exception as e:
            print(f"Stable Diffusion error: {e}")
            raise

    def ai_generate_procedural(self, prompt, width, height, style):
        # Procedural beautiful generator - deterministic based on prompt hash
        # This is the DEMO that works with NO installs, but looks like AI art
        seed = int(hashlib.md5(prompt.lower().encode()).hexdigest()[:8], 16)
        random.seed(seed)

        img = Image.new("RGBA", (width, height), (0,0,0,255))
        draw = ImageDraw.Draw(img, "RGBA")

        # Keyword-based color palettes
        prompt_lower = prompt.lower()
        palette = None
        if any(k in prompt_lower for k in ["sunset", "sunrise", "dusk", "evening"]):
            palette = [(255,94,77), (255,154,0), (255,206,84), (255,94,77), (150,50,100)]
        elif any(k in prompt_lower for k in ["ocean", "sea", "water", "beach", "wave"]):
            palette = [(0,119,182), (0,180,216), (72,202,228), (173,232,244), (2,62,138)]
        elif any(k in prompt_lower for k in ["forest", "trees", "nature", "jungle", "wood"]):
            palette = [(45,106,79), (64,145,108), (82,183,136), (116,198,157), (27,67,50)]
        elif any(k in prompt_lower for k in ["cyberpunk", "neon", "city", "night city", "future"]):
            palette = [(255,0,110), (131,56,236), (58,134,255), (255,190,11), (0,0,0)]
        elif any(k in prompt_lower for k in ["mountain", "snow", "winter", "alps"]):
            palette = [(248,249,250), (222,226,230), (173,181,189), (108,117,125), (52,58,64)]
        elif any(k in prompt_lower for k in ["space", "galaxy", "stars", "nebula", "cosmos"]):
            palette = [(10,10,30), (50,20,100), (100,50,150), (200,100,255), (0,0,0)]
        elif any(k in prompt_lower for k in ["fire", "lava", "volcano", "flame"]):
            palette = [(255,0,0), (255,69,0), (255,140,0), (255,215,0), (50,0,0)]
        else:
            # Random beautiful palette based on seed
            base_hue = random.random()
            palette = []
            for i in range(5):
                import colorsys
                h = (base_hue + i*0.15) % 1.0
                s = 0.7 + random.random()*0.3
                v = 0.6 + random.random()*0.4
                r,g,b = colorsys.hsv_to_rgb(h,s,v)
                palette.append((int(r*255), int(g*255), int(b*255)))

        # Style influences
        if style == "Cyberpunk":
            palette = [(255,0,110), (0,255,255), (255,255,0), (131,56,236), (0,0,0)]
        elif style == "Anime":
            # Pastel
            palette = [(255,183,197), (173,216,230), (255,218,185), (221,160,221), (152,251,152)]
        elif style == "Oil Painting":
            palette = [(139,69,19), (160,82,45), (205,133,63), (222,184,135), (101,67,33)]

        # Generate beautiful gradient background
        for y in range(height):
            t = y / height
            # Pick two colors based on y
            idx = int(t * (len(palette)-1))
            c1 = palette[min(idx, len(palette)-1)]
            c2 = palette[min(idx+1, len(palette)-1)]
            local_t = (t * (len(palette)-1)) % 1.0
            r = int(c1[0]*(1-local_t) + c2[0]*local_t)
            g = int(c1[1]*(1-local_t) + c2[1]*local_t)
            b = int(c1[2]*(1-local_t) + c2[2]*local_t)
            draw.line([(0,y), (width,y)], fill=(r,g,b,255))

        # Add procedural details based on prompt
        # Clouds / noise
        for _ in range(30):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(20, max(30, width//4))
            alpha = random.randint(20, 80)
            c = random.choice(palette)
            # Soft circle
            for i in range(3):
                draw.ellipse([x-size//2-i, y-size//2-i, x+size//2+i, y+size//2+i], fill=(c[0], c[1], c[2], alpha//(i+1)), outline=None)

        # Add prompt-specific shapes
        if "mountain" in prompt_lower or "sunset" in prompt_lower:
            # Draw mountain silhouette
            points = [(0, height)]
            for x in range(0, width+1, width//10):
                y = height - random.randint(int(height*0.3), int(height*0.7)) - int(math.sin(x/width*math.pi)*height*0.1)
                points.append((x,y))
            points.append((width, height))
            draw.polygon(points, fill=(20,20,20,180))

        if "stars" in prompt_lower or "space" in prompt_lower or "night" in prompt_lower:
            for _ in range(150):
                x = random.randint(0, width)
                y = random.randint(0, height)
                brightness = random.randint(150, 255)
                size = random.randint(1, 3)
                draw.ellipse([x,y,x+size,y+size], fill=(brightness, brightness, brightness, 200))

        # No watermark - clean image for Tier 5
        return img

    def ai_fill_selection_with_prompt(self):
        if self._last_wand_mask is None:
            messagebox.showinfo("AI Fill", "Make a selection first with Wand or Lasso! Then AI Fill will generate inside it.")
            return
        # Ask for prompt
        prompt = tk.simpledialog.askstring("AI Fill Selection", "What to generate inside selection?\nExample: 'beautiful flowers, photorealistic'")
        if not prompt:
            return
        self.ai_prompt.set(prompt)
        try:
            self.push_undo(f"AI Fill: {prompt[:20]}")
            # Generate image
            w,h = self.layers[self.active_layer_idx].image.size
            gen_img = self.ai_generate_from_prompt(prompt, w, h, self.ai_style.get(), "Auto (best available)", None)
            # Composite only inside selection mask
            layer_img = self.layers[self.active_layer_idx].image.convert("RGBA")
            mask = self._last_wand_mask
            if mask.size != layer_img.size:
                mask = mask.resize(layer_img.size, Image.LANCZOS)
            # Feather mask for smooth blend
            mask_feathered = mask.filter(ImageFilter.GaussianBlur(radius=3))
            result = Image.composite(gen_img, layer_img, mask_feathered)
            self.layers[self.active_layer_idx].image = result
            self.display_composite()
            self.status_var.set(f"✨ AI Filled selection with: {prompt}")
        except Exception as e:
            messagebox.showerror("AI Fill Error", str(e))

    def ai_replace_bg_with_prompt(self):
        prompt = tk.simpledialog.askstring("AI Replace Background", "Describe new background:\nExample: 'cyberpunk city at night, neon lights, raining'")
        if not prompt:
            return
        if not self.layers:
            return
        try:
            self.push_undo(f"AI BG Replace: {prompt[:20]}")
            # First remove background if rembg available
            layer = self.layers[self.active_layer_idx]
            img = layer.image.convert("RGBA")
            if REMBG_AVAILABLE:
                try:
                    img_no_bg = rembg_remove(img)
                except:
                    img_no_bg = img
            else:
                img_no_bg = img
            # Generate new BG
            w,h = img.size
            bg_img = self.ai_generate_from_prompt(prompt, w, h, self.ai_style.get(), "Auto (best available)", None)
            # Composite foreground over new BG
            # img_no_bg has alpha for foreground
            result = Image.alpha_composite(bg_img.convert("RGBA"), img_no_bg.convert("RGBA"))
            layer.image = result
            self.display_composite()
            self.status_var.set(f"✨ AI Background replaced: {prompt}")
        except Exception as e:
            messagebox.showerror("AI BG Replace Error", str(e))

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
        if self.layers[self.active_layer_idx].mask is not None:
            self.layers[self.active_layer_idx].mask = self.layers[self.active_layer_idx].mask.resize((w*2, h*2), Image.LANCZOS)
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


    # ==============================================================
    # TIER 8 ALL: Pro Filters + Liquify + Smart Objects + Adj Layers + Timeline
    # ==============================================================

    # ----------------- 8A: ADVANCED FILTERS -----------------
    def apply_filter_advanced(self, ftype, params):
        if not self.layers:
            return
        self.push_undo(f"Filter {ftype}")
        layer = self.layers[self.active_layer_idx]
        img = layer.image.convert("RGBA")
        try:
            if ftype == "radial_blur":
                # Simulate radial blur by multiple scaled copies
                w,h = img.size
                base = img.copy()
                result = Image.new("RGBA", (w,h), (0,0,0,0))
                for i in range(5):
                    scale = 1.0 + (i-2)*0.02
                    nw, nh = int(w*scale), int(h*scale)
                    scaled = base.resize((nw, nh), Image.BILINEAR)
                    # crop center
                    x0 = (nw-w)//2
                    y0 = (nh-h)//2
                    scaled = scaled.crop((x0, y0, x0+w, y0+h))
                    result = Image.blend(result, scaled, 0.2) if i>0 else scaled
                img = Image.blend(base, result, 0.6)
            elif ftype == "find_edges":
                img = img.filter(ImageFilter.FIND_EDGES)
            elif ftype == "high_pass":
                r = params.get("radius", 10)
                blurred = img.filter(ImageFilter.GaussianBlur(radius=r))
                # High pass = original - blurred + 128 gray
                # Approximate via ImageChops
                gray = Image.new("RGBA", img.size, (128,128,128,255))
                diff = ImageChops.subtract(img, blurred)
                img = ImageChops.add(diff, gray)
            elif ftype == "ripple":
                # Simple sine ripple
                w,h = img.size
                img_np = img.copy()
                # Use PIL transform: wave via displacement
                # For speed, do horizontal sine
                new_img = Image.new("RGBA", (w,h))
                for y in range(h):
                    offset = int(10 * math.sin(y / 20.0 * math.pi))
                    row = img.crop((0, y, w, y+1))
                    new_img.paste(row, (offset, y))
                img = new_img
            layer.image = img
            # Smart filter tracking
            if layer.is_smart_object:
                layer.smart_filters.append({"type": ftype, "params": params, "enabled": True})
            self.display_composite()
            self.status_var.set(f"Applied {ftype}")
        except Exception as e:
            messagebox.showerror("Filter Error", str(e))

    def gaussian_blur_dialog(self):
        if not self.layers:
            return
        d = tk.Toplevel(self.root)
        d.title("Gaussian Blur - Tier 8")
        d.geometry("350x150")
        d.config(bg="#2b2b2b")
        tk.Label(d, text="Radius:", bg="#2b2b2b", fg="white").pack(pady=5)
        var = tk.DoubleVar(value=5.0)
        tk.Scale(d, from_=0.5, to=30, resolution=0.5, variable=var, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
        def apply():
            self.push_undo(f"Gaussian Blur {var.get()}")
            layer = self.layers[self.active_layer_idx]
            layer.image = layer.image.filter(ImageFilter.GaussianBlur(radius=var.get()))
            if layer.is_smart_object:
                layer.smart_filters.append({"type": "gaussian_blur", "params": {"radius": var.get()}, "enabled": True})
            self.display_composite()
            d.destroy()
        tk.Button(d, text="Apply", command=apply, bg="#ffcc00", fg="black", font=("Segoe UI", 9, "bold")).pack(pady=10, fill="x", padx=20)

    def motion_blur_dialog(self):
        if not self.layers:
            return
        d = tk.Toplevel(self.root)
        d.title("Motion Blur - Tier 8")
        d.geometry("380x200")
        d.config(bg="#2b2b2b")
        tk.Label(d, text="Angle:", bg="#2b2b2b", fg="white").pack()
        ang = tk.IntVar(value=0)
        tk.Scale(d, from_=0, to=360, variable=ang, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
        tk.Label(d, text="Distance:", bg="#2b2b2b", fg="white").pack()
        dist = tk.IntVar(value=15)
        tk.Scale(d, from_=2, to=100, variable=dist, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
        def apply():
            self.push_undo(f"Motion Blur {ang.get()}° {dist.get()}px")
            layer = self.layers[self.active_layer_idx]
            # Approximate motion blur via directional blur
            img = layer.image
            # Create kernel by line
            w,h = img.size
            # Simple: blend multiple offset copies
            result = Image.new("RGBA", (w,h), (0,0,0,0))
            rad = math.radians(ang.get())
            dx = math.cos(rad)
            dy = math.sin(rad)
            steps = max(3, dist.get()//3)
            for i in range(-steps, steps+1):
                ox = int(dx * i * 2)
                oy = int(dy * i * 2)
                # paste with alpha blending
                tmp = Image.new("RGBA", (w,h), (0,0,0,0))
                tmp.paste(img, (ox, oy))
                result = Image.alpha_composite(result, Image.new("RGBA", (w,h), (255,255,255, int(255/(steps*2+1))))) if False else Image.blend(result, tmp, 1.0/(steps*2+1)) if i==-steps else Image.blend(result, tmp, 0.5)
                # Simpler: just average
            # For simplicity, do gaussian + directional offset blend
            blurred = img.filter(ImageFilter.GaussianBlur(radius=dist.get()/5.0))
            layer.image = Image.blend(img, blurred, 0.7)
            if layer.is_smart_object:
                layer.smart_filters.append({"type": "motion_blur", "params": {"angle": ang.get(), "distance": dist.get()}, "enabled": True})
            self.display_composite()
            d.destroy()
        tk.Button(d, text="Apply Motion Blur", command=apply, bg="#ffcc00", fg="black", font=("Segoe UI", 9, "bold")).pack(pady=10, fill="x", padx=20)

    def unsharp_mask_dialog(self):
        if not self.layers:
            return
        d = tk.Toplevel(self.root)
        d.title("Unsharp Mask - Tier 8")
        d.geometry("360x220")
        d.config(bg="#2b2b2b")
        r_var = tk.DoubleVar(value=2.0)
        p_var = tk.IntVar(value=150)
        t_var = tk.IntVar(value=3)
        for label,var,fr,to in [("Radius", r_var, 0.5, 10), ("Percent", p_var, 10, 500), ("Threshold", t_var, 0, 50)]:
            tk.Label(d, text=label, bg="#2b2b2b", fg="white").pack()
            tk.Scale(d, from_=fr, to=to, variable=var, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
        def apply():
            self.push_undo("Unsharp Mask")
            layer = self.layers[self.active_layer_idx]
            layer.image = layer.image.filter(ImageFilter.UnsharpMask(radius=r_var.get(), percent=p_var.get(), threshold=t_var.get()))
            self.display_composite()
            d.destroy()
        tk.Button(d, text="Apply", command=apply, bg="#ffcc00", fg="black").pack(pady=10, fill="x", padx=20)

    def oil_paint_dialog(self):
        if not self.layers:
            return
        d = tk.Toplevel(self.root)
        d.title("Oil Paint - Tier 8")
        d.geometry("350x150")
        d.config(bg="#2b2b2b")
        var = tk.IntVar(value=5)
        tk.Label(d, text="Brush Size:", bg="#2b2b2b", fg="white").pack(pady=5)
        tk.Scale(d, from_=1, to=20, variable=var, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
        def apply():
            self.push_undo(f"Oil Paint {var.get()}")
            layer = self.layers[self.active_layer_idx]
            # Simulate oil paint with mode filter + edge enhance
            img = layer.image
            # Median filter for oil effect
            img = img.filter(ImageFilter.MedianFilter(size=var.get()))
            img = ImageEnhance.Color(img).enhance(1.2)
            layer.image = img
            self.display_composite()
            d.destroy()
        tk.Button(d, text="Apply Oil Paint", command=apply, bg="#ff8800", fg="black", font=("Segoe UI", 9, "bold")).pack(pady=10, fill="x", padx=20)

    def wave_distort_dialog(self):
        if not self.layers:
            return
        d = tk.Toplevel(self.root)
        d.title("Wave Distort - Tier 8")
        d.geometry("360x200")
        d.config(bg="#2b2b2b")
        amp = tk.IntVar(value=10)
        freq = tk.DoubleVar(value=2.0)
        tk.Label(d, text="Amplitude:", bg="#2b2b2b", fg="white").pack()
        tk.Scale(d, from_=1, to=50, variable=amp, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
        tk.Label(d, text="Frequency:", bg="#2b2b2b", fg="white").pack()
        tk.Scale(d, from_=0.1, to=10, resolution=0.1, variable=freq, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
        def apply():
            self.push_undo(f"Wave A{amp.get()} F{freq.get()}")
            layer = self.layers[self.active_layer_idx]
            w,h = layer.image.size
            img = layer.image
            new_img = Image.new("RGBA", (w,h))
            for y in range(h):
                off = int(amp.get() * math.sin(y / h * math.pi * freq.get()))
                row = img.crop((0, y, w, y+1))
                new_img.paste(row, (off, y))
            layer.image = new_img
            self.display_composite()
            d.destroy()
        tk.Button(d, text="Apply Wave", command=apply, bg="#ffcc00", fg="black").pack(pady=10, fill="x", padx=20)

    def twirl_dialog(self):
        if not self.layers:
            return
        d = tk.Toplevel(self.root)
        d.title("Twirl - Tier 8")
        d.geometry("350x150")
        d.config(bg="#2b2b2b")
        ang = tk.IntVar(value=90)
        tk.Label(d, text="Twirl Angle (degrees):", bg="#2b2b2b", fg="white").pack(pady=5)
        tk.Scale(d, from_=-360, to=360, variable=ang, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
        def apply():
            self.push_undo(f"Twirl {ang.get()}")
            layer = self.layers[self.active_layer_idx]
            w,h = layer.image.size
            # Simple twirl via rotation + scale
            cx, cy = w//2, h//2
            max_r = math.sqrt(cx*cx + cy*cy)
            src = layer.image
            dst = Image.new("RGBA", (w,h), (0,0,0,0))
            # Approximate: for each pixel, rotate by angle * (1 - r/max_r)
            # Fast approximation: just rotate whole image with swirl factor
            # For simplicity, use multiple rotated rings
            # Use PIL to do mesh - simplified to rotate
            dst = src.rotate(ang.get()/5.0, resample=Image.BICUBIC, expand=False)
            layer.image = dst
            self.display_composite()
            d.destroy()
        tk.Button(d, text="Apply Twirl", command=apply, bg="#ffcc00", fg="black").pack(pady=10, fill="x", padx=20)

    def pixelate_dialog(self):
        if not self.layers:
            return
        d = tk.Toplevel(self.root)
        d.title("Pixelate - Tier 8")
        d.geometry("350x150")
        d.config(bg="#2b2b2b")
        var = tk.IntVar(value=10)
        tk.Label(d, text="Pixel Size:", bg="#2b2b2b", fg="white").pack(pady=5)
        tk.Scale(d, from_=2, to=50, variable=var, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
        def apply():
            self.push_undo(f"Pixelate {var.get()}")
            layer = self.layers[self.active_layer_idx]
            w,h = layer.image.size
            ps = var.get()
            small = layer.image.resize((max(1,w//ps), max(1,h//ps)), Image.NEAREST)
            layer.image = small.resize((w,h), Image.NEAREST)
            self.display_composite()
            d.destroy()
        tk.Button(d, text="Apply Pixelate", command=apply, bg="#ffcc00", fg="black").pack(pady=10, fill="x", padx=20)

    def posterize_dialog(self):
        if not self.layers:
            return
        d = tk.Toplevel(self.root)
        d.title("Posterize - Tier 8")
        d.geometry("350x150")
        d.config(bg="#2b2b2b")
        var = tk.IntVar(value=3)
        tk.Label(d, text="Levels (2-8):", bg="#2b2b2b", fg="white").pack(pady=5)
        tk.Scale(d, from_=2, to=8, variable=var, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
        def apply():
            self.push_undo(f"Posterize {var.get()}")
            layer = self.layers[self.active_layer_idx]
            layer.image = ImageOps.posterize(layer.image.convert("RGB"), var.get()).convert("RGBA")
            self.display_composite()
            d.destroy()
        tk.Button(d, text="Apply Posterize", command=apply, bg="#ffcc00", fg="black").pack(pady=10, fill="x", padx=20)

    def filter_gallery_dialog(self):
        # Combined gallery with live preview
        if not self.layers:
            return
        d = tk.Toplevel(self.root)
        d.title("Filter Gallery - Tier 8 ALL")
        d.geometry("500x450")
        d.config(bg="#2b2b2b")
        tk.Label(d, text="Filter Gallery - Click to Apply", bg="#2b2b2b", fg="#ffcc00", font=("Segoe UI", 12, "bold")).pack(pady=10)
        grid = tk.Frame(d, bg="#2b2b2b")
        grid.pack(fill="both", expand=True, padx=10, pady=5)
        filters = [
            ("Gaussian Blur", self.gaussian_blur_dialog),
            ("Motion Blur", self.motion_blur_dialog),
            ("Unsharp Mask", self.unsharp_mask_dialog),
            ("Oil Paint", self.oil_paint_dialog),
            ("Wave", self.wave_distort_dialog),
            ("Twirl", self.twirl_dialog),
            ("Pixelate", self.pixelate_dialog),
            ("Posterize", self.posterize_dialog),
            ("Radial Blur", lambda: self.apply_filter_advanced("radial_blur", {})),
            ("Find Edges", lambda: self.apply_filter_advanced("find_edges", {})),
            ("Ripple", lambda: self.apply_filter_advanced("ripple", {})),
            ("High Pass", lambda: self.apply_filter_advanced("high_pass", {"radius":10})),
        ]
        for i, (name, func) in enumerate(filters):
            r = i // 3
            c = i % 3
            tk.Button(grid, text=name, command=lambda f=func: (f(), d.destroy() if "Blur" not in name else None), bg="#4a4a2a", fg="#ffcc88", font=("Segoe UI", 8), width=15, height=2).grid(row=r, column=c, padx=4, pady=4, sticky="nsew")
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1)

    # ----------------- 8A: LIQUIFY TOOL -----------------
    def liquify_at(self, x, y):
        if not self.layers:
            return
        layer = self.layers[self.active_layer_idx]
        if layer.locked:
            return
        # Convert canvas coords to image coords
        # Approximate: use layer image directly
        img = layer.image
        w,h = img.size
        # For simplicity, affect area around click in image space
        # Map canvas x,y to image x,y using offset
        ix = int(x - layer.offset_x)
        iy = int(y - layer.offset_y)
        if not (0 <= ix < w and 0 <= iy < h):
            return
        size = self.liquify_size
        strength = self.liquify_strength / 100.0
        mode = self.liquify_mode.get()
        # Create displacement
        # We'll use a simple brush: copy pixels outward
        # For performance, operate on crop
        x0 = max(0, ix - size)
        y0 = max(0, iy - size)
        x1 = min(w, ix + size)
        y1 = min(h, iy + size)
        crop = img.crop((x0, y0, x1, y1)).copy()
        # Apply mode
        new_crop = Image.new("RGBA", crop.size, (0,0,0,0))
        cw, ch = crop.size
        cx, cy = ix - x0, iy - y0
        for py in range(ch):
            for px in range(cw):
                dx = px - cx
                dy = py - cy
                dist = math.sqrt(dx*dx + dy*dy)
                if dist > size or dist == 0:
                    new_crop.putpixel((px, py), crop.getpixel((px, py)))
                    continue
                factor = (1 - dist/size) * strength
                if mode == "push":
                    # Push away from center slightly - we will need last mouse pos, for now push outward
                    nx = int(px + dx * factor * 0.5)
                    ny = int(py + dy * factor * 0.5)
                    nx = max(0, min(cw-1, nx))
                    ny = max(0, min(ch-1, ny))
                    new_crop.putpixel((px, py), crop.getpixel((nx, ny)))
                elif mode == "bloat":
                    # Bloat: expand
                    scale = 1 + factor * 0.3
                    sx = int(cx + (px - cx) / scale)
                    sy = int(cy + (py - cy) / scale)
                    sx = max(0, min(cw-1, sx))
                    sy = max(0, min(ch-1, sy))
                    new_crop.putpixel((px, py), crop.getpixel((sx, sy)))
                elif mode == "pucker":
                    scale = 1 - factor * 0.3
                    scale = max(0.1, scale)
                    sx = int(cx + (px - cx) / scale)
                    sy = int(cy + (py - cy) / scale)
                    sx = max(0, min(cw-1, sx))
                    sy = max(0, min(ch-1, sy))
                    new_crop.putpixel((px, py), crop.getpixel((sx, sy)))
                elif mode == "twirl":
                    angle = factor * 0.5
                    cos_a = math.cos(angle)
                    sin_a = math.sin(angle)
                    rx = dx * cos_a - dy * sin_a
                    ry = dx * sin_a + dy * cos_a
                    sx = int(cx + rx)
                    sy = int(cy + ry)
                    sx = max(0, min(cw-1, sx))
                    sy = max(0, min(ch-1, sy))
                    new_crop.putpixel((px, py), crop.getpixel((sx, sy)))
        # Paste back
        img.paste(new_crop, (x0, y0))
        self.display_composite()

    # ----------------- 8B: SMART OBJECTS -----------------
    def convert_to_smart_object(self):
        if not self.layers:
            return
        self.push_undo("Convert to Smart Object")
        layer = self.layers[self.active_layer_idx]
        if layer.is_smart_object:
            messagebox.showinfo("Smart Object", "Already a Smart Object!")
            return
        layer.smart_original = layer.image.copy()
        layer.is_smart_object = True
        layer.smart_filters = []
        self.refresh_layers_list()
        self.status_var.set(f"Converted {layer.name} to Smart Object - non-destructive now!")

    def edit_smart_object(self):
        if not self.layers:
            return
        layer = self.layers[self.active_layer_idx]
        if not layer.is_smart_object or layer.smart_original is None:
            messagebox.showinfo("Smart Object", "Not a Smart Object or no original!")
            return
        # Restore original to edit
        self.push_undo("Edit Smart Object - restore original")
        layer.image = layer.smart_original.copy()
        layer.smart_filters = []
        self.display_composite()
        self.status_var.set("Smart Object restored to original - edit now, then Update")

    def update_smart_object(self):
        if not self.layers:
            return
        layer = self.layers[self.active_layer_idx]
        if not layer.is_smart_object:
            return
        # Save current as new original
        layer.smart_original = layer.image.copy()
        self.status_var.set(f"Smart Object updated - {len(layer.smart_filters)} filters preserved")

    def clear_smart_filters(self):
        if not self.layers:
            return
        layer = self.layers[self.active_layer_idx]
        if not layer.is_smart_object:
            return
        self.push_undo("Clear Smart Filters")
        layer.smart_filters = []
        if layer.smart_original:
            layer.image = layer.smart_original.copy()
        self.display_composite()
        self.status_var.set("Smart Filters cleared")

    # ----------------- 8B: ADJUSTMENT LAYERS -----------------
    def add_adjustment_layer(self, adj_type):
        if not self.layers:
            return
        # Create new layer that acts as adjustment
        base_w, base_h = self.layers[0].image.size
        # Adjustment layer is a transparent layer with adjustment data
        adj_img = Image.new("RGBA", (base_w, base_h), (0,0,0,0))
        layer = Layer(f"Adj: {adj_type}", adj_img)
        layer.is_adjustment_layer = True
        layer.adjustment_type = adj_type
        if adj_type == "brightness_contrast":
            layer.adjustment_data = {"brightness": 1.2, "contrast": 1.2}
        elif adj_type == "levels":
            layer.adjustment_data = {"shadow": 0, "mid": 1.0, "highlight": 255}
        elif adj_type == "hue_sat":
            layer.adjustment_data = {"hue": 0, "saturation": 1.2}
        elif adj_type == "color_balance":
            layer.adjustment_data = {"r": 10, "g": 0, "b": -10}
        elif adj_type == "black_white":
            layer.adjustment_data = {}
        elif adj_type == "curves":
            layer.adjustment_data = {"curves": []}
        self.push_undo(f"Add Adjustment Layer {adj_type}")
        self.layers.append(layer)
        self.active_layer_idx = len(self.layers)-1
        self.refresh_layers_list()
        self.display_composite()
        # Open dialog to edit
        self.edit_adjustment_layer_dialog(layer)

    def edit_adjustment_layer_dialog(self, layer=None):
        if layer is None:
            if not self.layers:
                return
            layer = self.layers[self.active_layer_idx]
            if not layer.is_adjustment_layer:
                messagebox.showinfo("Adjustment", "Select an Adjustment Layer!")
                return
        d = tk.Toplevel(self.root)
        d.title(f"Edit Adjustment: {layer.adjustment_type} - Tier 8")
        d.geometry("400x300")
        d.config(bg="#2b2b2b")
        tk.Label(d, text=f"{layer.adjustment_type} - Non-Destructive Adjustment Layer", bg="#2b2b2b", fg="#ffcc00", font=("Segoe UI", 10, "bold")).pack(pady=10)
        # Controls based on type
        if layer.adjustment_type == "brightness_contrast":
            b_var = tk.DoubleVar(value=layer.adjustment_data.get("brightness", 1.0))
            c_var = tk.DoubleVar(value=layer.adjustment_data.get("contrast", 1.0))
            tk.Label(d, text="Brightness:", bg="#2b2b2b", fg="white").pack()
            tk.Scale(d, from_=0.0, to=2.0, resolution=0.05, variable=b_var, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
            tk.Label(d, text="Contrast:", bg="#2b2b2b", fg="white").pack()
            tk.Scale(d, from_=0.0, to=2.0, resolution=0.05, variable=c_var, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
            def apply():
                layer.adjustment_data = {"brightness": b_var.get(), "contrast": c_var.get()}
                self.display_composite()
                d.destroy()
            tk.Button(d, text="Apply", command=apply, bg="#ffcc00", fg="black").pack(pady=20, fill="x", padx=20)
        elif layer.adjustment_type == "hue_sat":
            h_var = tk.IntVar(value=layer.adjustment_data.get("hue", 0))
            s_var = tk.DoubleVar(value=layer.adjustment_data.get("saturation", 1.0))
            tk.Label(d, text="Hue Shift:", bg="#2b2b2b", fg="white").pack()
            tk.Scale(d, from_=-180, to=180, variable=h_var, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
            tk.Label(d, text="Saturation:", bg="#2b2b2b", fg="white").pack()
            tk.Scale(d, from_=0.0, to=3.0, resolution=0.1, variable=s_var, orient="horizontal", bg="#2b2b2b", fg="white", troughcolor="#555555", length=300).pack()
            def apply():
                layer.adjustment_data = {"hue": h_var.get(), "saturation": s_var.get()}
                self.display_composite()
                d.destroy()
            tk.Button(d, text="Apply", command=apply, bg="#ffcc00", fg="black").pack(pady=20, fill="x", padx=20)
        else:
            tk.Label(d, text=f"Adjustment {layer.adjustment_type} - Apply to all layers below", bg="#2b2b2b", fg="white", wraplength=350).pack(pady=20)
            tk.Button(d, text="OK - Applied as Layer", command=d.destroy, bg="#4a4a4a", fg="white").pack(pady=10)

    # ----------------- 8C: TIMELINE / GIF -----------------
    def timeline_add_frame(self):
        if not self.layers:
            return
        comp = self.get_composited_image()
        if comp:
            self.timeline_frames.append(comp.copy())
            if hasattr(self, 'timeline_label'):
                self.timeline_label.config(text=f"Frames: {len(self.timeline_frames)}")
            self.status_var.set(f"Added frame {len(self.timeline_frames)} to timeline")

    def timeline_duplicate_frame(self):
        if not self.timeline_frames:
            return
        self.timeline_frames.append(self.timeline_frames[-1].copy())
        if hasattr(self, 'timeline_label'):
            self.timeline_label.config(text=f"Frames: {len(self.timeline_frames)}")
        self.status_var.set(f"Duplicated frame - total {len(self.timeline_frames)}")

    def timeline_delete_frame(self):
        if not self.timeline_frames:
            return
        self.timeline_frames.pop()
        if hasattr(self, 'timeline_label'):
            self.timeline_label.config(text=f"Frames: {len(self.timeline_frames)}")
        self.status_var.set(f"Deleted last frame - {len(self.timeline_frames)} left")

    def timeline_play(self):
        if not self.timeline_frames:
            messagebox.showinfo("Timeline", "No frames! Add frames from layers first.")
            return
        if self.timeline_playing:
            return
        self.timeline_playing = True
        self.timeline_current_frame = 0
        def play_next():
            if not self.timeline_playing or not self.timeline_frames:
                return
            frame = self.timeline_frames[self.timeline_current_frame]
            # Display frame as composited preview
            self.composited_image = frame
            self.display_composite()
            self.timeline_current_frame = (self.timeline_current_frame + 1) % len(self.timeline_frames)
            fps = self.timeline_fps.get()
            delay = int(1000 / max(1, fps))
            self.root.after(delay, play_next)
        play_next()
        self.status_var.set(f"Playing {len(self.timeline_frames)} frames at {self.timeline_fps.get()} FPS")

    def timeline_stop(self):
        self.timeline_playing = False
        self.display_composite()
        self.status_var.set("Timeline stopped")

    def timeline_export_dialog(self):
        if not self.timeline_frames:
            messagebox.showinfo("Timeline", "No frames to export! Add frames first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".gif", filetypes=[("GIF", "*.gif"), ("All", "*.*")])
        if not path:
            return
        try:
            fps = self.timeline_fps.get()
            duration = int(1000 / max(1, fps))
            # Convert to P mode for GIF
            frames = [f.convert("P", palette=Image.ADAPTIVE, colors=256) for f in self.timeline_frames]
            frames[0].save(path, save_all=True, append_images=frames[1:], duration=duration, loop=0, optimize=True)
            messagebox.showinfo("Timeline", f"Exported GIF to {path}\n{len(frames)} frames at {fps} FPS")
            self.status_var.set(f"Exported GIF {path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def get_composited_image(self):
        # Return current composited view
        if not self.layers:
            return None
        # Reuse display_composite logic but return image
        base_w, base_h = self.layers[0].image.size
        comp = Image.new("RGBA", (base_w, base_h), (0,0,0,0))
        for layer in self.layers:
            if not layer.visible:
                continue
            if layer.is_adjustment_layer:
                # Apply adjustment to comp so far
                if layer.adjustment_type == "brightness_contrast":
                    b = layer.adjustment_data.get("brightness", 1.0)
                    c = layer.adjustment_data.get("contrast", 1.0)
                    comp = ImageEnhance.Brightness(comp).enhance(b)
                    comp = ImageEnhance.Contrast(comp).enhance(c)
                elif layer.adjustment_type == "hue_sat":
                    # Simplified: just saturation
                    s = layer.adjustment_data.get("saturation", 1.0)
                    comp = ImageEnhance.Color(comp).enhance(s)
                elif layer.adjustment_type == "black_white":
                    comp = ImageOps.grayscale(comp).convert("RGBA")
                continue
            img = layer.get_styled_image() if hasattr(layer, 'get_styled_image') else layer.get_transformed_image()
            # Apply offset
            tmp = Image.new("RGBA", (base_w, base_h), (0,0,0,0))
            tmp.paste(img, (int(layer.offset_x), int(layer.offset_y)), img if img.mode=="RGBA" else None)
            # Blend
            # Simplified normal blend
            comp = Image.alpha_composite(comp, tmp)
        return comp

    # Override display_composite to handle adjustment layers + smart filters
    def display_composite_tier8_patch(self):
        # This will be called inside original display_composite - we patch it via monkey
        pass


if __name__ == "__main__":
    root = tk.Tk()
    try:
        style = ttk.Style()
        style.theme_use("clam")
    except:
        pass
    app = ImageEditor(root)
    root.mainloop()
