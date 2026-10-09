# Example custom AI generator plugin
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
