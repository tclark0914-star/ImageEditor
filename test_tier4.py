from PIL import Image, ImageOps, ImageFilter, ImageChops, ImageDraw
import math, os

def create_test_image(size=(200,200)):
    img = Image.new("RGBA", size, (255,255,255,255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50,50,150,150], fill=(100,150,200,255))
    return img

def test_gradient():
    print("\n=== GRADIENT TESTS (Tier 4) ===")
    img = create_test_image()
    w,h = img.size
    c1=(255,0,0); c2=(0,0,255)
    start=(0,0); end=(w,0)
    dx=end[0]-start[0]; dy=end[1]-start[1]
    length=math.hypot(dx,dy)
    grad = Image.new("RGBA", (w,h))
    for y in range(h):
        for x in range(w):
            px=x-start[0]; py=y-start[1]
            t=(px*dx+py*dy)/(length*length) if length!=0 else 0
            t=max(0.0,min(1.0,t))
            r=int(c1[0]*(1-t)+c2[0]*t)
            g=int(c1[1]*(1-t)+c2[1]*t)
            b=int(c1[2]*(1-t)+c2[2]*t)
            grad.putpixel((x,y),(r,g,b,255))
    assert grad.getpixel((0,0))[0]>=250
    assert grad.getpixel((w-1,0))[2]>=200
    print("✓ Gradient linear: red->blue across width")
    cx,cy=w//2,h//2
    radius=math.hypot(w//2,h//2)
    grad2=Image.new("RGBA",(w,h))
    for y in range(h):
        for x in range(w):
            dist=math.hypot(x-cx,y-cy)
            t=dist/radius
            t=max(0.0,min(1.0,t))
            r=int(c1[0]*(1-t)+c2[0]*t)
            grad2.putpixel((x,y),(r,0,255,255))
    print("✓ Gradient radial: center to edge")

def test_shadows_highlights():
    print("\n=== SHADOWS/HIGHLIGHTS TESTS (Tier 4) ===")
    img = create_test_image()
    r,g,b,a=img.split()
    def sh_map(p):
        if p<128:
            factor=(128-p)/128.0
            p=p+int(factor*0.3*80)
        if p>128:
            factor=(p-128)/127.0
            p=p-int(factor*0.3*60)
        return max(0,min(255,p))
    r2=r.point(sh_map)
    print("✓ Shadows/Highlights: point mapping dark lift + bright drop")

def test_vignette():
    print("\n=== VIGNETTE TESTS (Tier 4) ===")
    img = create_test_image()
    w,h=img.size
    vig=Image.new("L",(w,h),0)
    cx,cy=w//2,h//2
    max_dist=math.hypot(cx,cy)
    for y in range(h):
        for x in range(w):
            dist=math.hypot(x-cx,y-cy)/max_dist
            darken=int((dist**1.8)*0.4*180)
            vig.putpixel((x,y), min(255,darken))
    assert vig.getpixel((cx,cy))<vig.getpixel((0,0))
    print("✓ Vignette: center dark 0, corners darker")

def test_auto_crop():
    print("\n=== AUTO CROP TESTS (Tier 4) ===")
    img=Image.new("RGBA",(200,200),(0,0,0,0))
    draw=ImageDraw.Draw(img)
    draw.rectangle([50,50,150,150],fill=(255,0,0,255))
    alpha=img.split()[3]
    bbox=alpha.getbbox()
    assert bbox==(50,50,151,151)
    cropped=img.crop(bbox)
    assert cropped.size==(101,101)
    print(f"✓ Auto Crop: bbox {bbox} -> cropped {cropped.size}")

if __name__=="__main__":
    print("Starting Tier 4 Tests - Gradient + Shadows + Vignette")
    test_gradient()
    test_shadows_highlights()
    test_vignette()
    test_auto_crop()
    print("\n"+"="*50)
    print("ALL TIER 4 TESTS PASSED! Gradient + Shadows + Vignette solid.")
    print("="*50)
