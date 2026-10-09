# ImageEditor - Milestone 9 TIER 5.1 (Modular AI + ComfyUI + A1111)

A Photoshop-like image editor built with Python Tkinter - now with modular AI prompt generation!

## 🚀 Features - 3038 Lines, ~80% of Photoshop

### Core Editing (Tier 1-3)
- **Layers + Masks**: Full layer system with blend modes, opacity, masks
- **Tools**: Select, Crop, Brush, Eraser, Text, Clone Stamp, Lasso, Wand
- **Adjustments**: Levels, Curves, Hue/Saturation, Shadows/Highlights, Vignette
- **Filters**: Blur, Sharpen, Grayscale, Sepia, Invert, Edge Enhance, etc.
- **AI**: Remove Background (rembg), Upscale, Auto Enhance, Denoise

### NEW in Tier 5.1 - Modular AI Prompt System ✨
- **Modular AI Provider System**: Add new AI generators without editing main.py!
- **No Watermark**: Clean images from all providers
- **9 Built-in Providers**:
  - 🌐 **Pollinations (FREE)** - No key, no install, no watermark, unlimited
  - 🤗 **HuggingFace Inference (FREE)** - Optional token for higher limits
  - 🎨 **OpenAI DALL-E 3** - Best quality ($)
  - 🖥️ **Automatic1111 WebUI (LOCAL)** - Your GPU, fast, private - BEST FOR LOCAL!
  - 🧩 **ComfyUI (LOCAL)** - Advanced workflows, local GPU
  - 💎 **Stability AI SDXL** - Stability.ai API
  - 🔁 **Replicate** - 100+ models
  - 💻 **Local Diffusers** - `pip install diffusers`
  - 🎭 **Procedural Demo** - Offline fallback, now NO watermark!

### AI Features
- **Generate Image from Prompt (Ctrl+G)**: Text -> New Layer
- **AI Fill Selection**: Select area -> Generate inside it
- **AI Replace Background**: Generate new background, keep foreground
- **Plugin System**: Drop .py files in `ai_generators/` folder to add new AIs!

## 📦 Installation

```powershell
cd "$HOME\Documents\ImageEditor"
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

### For Local AI (Recommended)

**Option A - Automatic1111 (Easiest, Best Quality Local):**
```powershell
# Download from https://github.com/AUTOMATIC1111/stable-diffusion-webui
# Run:
webui.bat --api --listen
# Then in ImageEditor: AI Engine -> Automatic1111 WebUI
```

**Option B - ComfyUI (Advanced):**
```powershell
# Download from https://github.com/comfyanonymous/ComfyUI
# Download model v1-5-pruned-emaonly.ckpt to models/checkpoints/
# Run:
python main.py --listen
# Then in ImageEditor: AI Engine -> ComfyUI
```

**Option C - No Install (FREE Online):**
- Just use Pollinations - works out of the box, no setup!

## 🔌 Adding New AI Generators

### Method 1: No Code - Custom API URL
1. AI Menu -> Manage AI Providers -> Add Custom API Provider
2. Name: `My Generator`
3. URL: `https://api.example.com/generate?prompt={prompt}&width={width}&height={height}`
4. Placeholders: `{prompt}`, `{width}`, `{height}`, `{style}`
5. Click Add -> Auto-saved!

### Method 2: Python Plugin (More Control)
1. AI Menu -> Open ai_generators Folder
2. Create `my_generator.py`:
```python
def register(editor):
    def my_gen(prompt, width, height, style, status_var=None):
        import requests
        from PIL import Image
        from io import BytesIO
        resp = requests.get(f"https://api.example.com?prompt={prompt}")
        return Image.open(BytesIO(resp.content)).convert("RGBA")
    
    editor.register_ai_provider("my_ai", {
        "name": "My Custom AI",
        "description": "My awesome generator",
        "func": my_gen,
        "enabled": True,
        "free": True
    })
```
3. Restart app - appears in provider list!

## 🎮 Usage

```powershell
python main.py
# - File -> Open Image
# - Tools on left
# - Right panels for settings
# - AI -> Generate Image from Prompt (Ctrl+G)
# - Try: "Nigerian soccer player celebrating goal vs Ghana, National Stadium Abuja, stylized"
# - Engine: FREE Online AI or Automatic1111 if running locally
# - Click GENERATE AS NEW LAYER
```

## 📁 Project Structure

```
ImageEditor/
  main.py (3038 lines - Tier 5.1)
  requirements.txt
  README.md
  .gitignore
  ai_generators/ (auto-created)
    _example_plugin.py
    _a1111_howto.txt
    _comfyui_howto.txt
  AI_PROVIDERS_GUIDE.txt
  tests/
    test_tier4.py
    test_ai_prompt.py
```

## 🧪 Tests

```powershell
python test_tier4.py
# ALL TIER 4 TESTS PASSED!

python test_ai_prompt.py
# ALL AI PROMPT TESTS PASSED!
```

## 📝 Milestones

- Milestone 8 Tier 4: 1866 lines - Gradient + Shadows/Highlights + Vignette
- Milestone 9 Tier 5: 2837 lines - Modular AI + No Watermark
- Milestone 9 Tier 5.1: 3038 lines - ComfyUI + Automatic1111 + Plugin System

## 🔧 Config File

`~/.imageeditor_ai.json` stores:
```json
{
  "openai_key": "sk-...",
  "hf_token": "hf_...",
  "stability_key": "...",
  "replicate_key": "...",
  "a1111_url": "http://127.0.0.1:7860",
  "comfy_url": "http://127.0.0.1:8188",
  "providers_enabled": {...},
  "custom_providers": [...]
}
```

## 📄 License

MIT - Free to use, modify, add AI providers!

## 🙏 Credits

Built with Pillow, Tkinter, rembg, diffusers, and love for Nigerian Super Eagles! 🇳🇬⚽
