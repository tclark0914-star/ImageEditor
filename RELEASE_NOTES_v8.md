# ImageEditor v8.0 - Tier 8 ALL

**5626 lines - The Complete Photoshop Alternative**

## Tier 8A: Pro Filters Gallery
- Gaussian Blur dialog with radius 0.5-30
- Motion Blur with angle + distance
- Unsharp Mask (radius/percent/threshold)
- Oil Paint (median filter simulation)
- Wave Distort (amplitude/frequency)
- Twirl, Pixelate, Posterize dialogs
- Radial Blur, Find Edges, Ripple, High Pass
- Filter Gallery dialog (all filters in one place)

## Tier 8A: Liquify Brush Tool
- New tool: 💧 Liquify
- Modes: Push, Bloat, Pucker, Twirl
- Size 10-200px, Strength 1-100%
- Non-destructive with undo
- Canvas to image coords mapping

## Tier 8B: Smart Objects
- Convert any layer to Smart Object (preserves original)
- Edit Smart Object (restore original)
- Update Smart Object (save new original)
- Clear Smart Filters
- Smart Filters tracking (gaussian, motion, etc)
- Non-destructive workflow

## Tier 8B: Adjustment Layers
- Brightness/Contrast adjustment layer
- Levels, Curves (stub), Hue/Saturation
- Color Balance, Black & White
- Non-destructive - affects all layers below
- Edit dialog per adjustment type
- Display composite handles adj layers

## Tier 8C: Timeline / GIF Animation
- New Timeline menu + UI panel
- Add Frame from current layers
- Duplicate / Delete frames
- Play / Stop preview at 1-30 FPS
- Export GIF with FPS control (Pillow)
- FPS slider + frame counter
- Uses imageio optional for better export

## Technical
- Layer class extended: is_smart_object, smart_original, smart_filters, is_adjustment_layer, adjustment_type/data, is_frame
- Copy method updated for Tier 8 fields
- New methods: 20+ dialogs + filters
- Tools: liquify + timeline added to toolbar
- Canvas press/drag patched for liquify
- display_composite patched for adjustment layers

Install: pip install -r requirements.txt
Run: python main.py
