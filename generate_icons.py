from pathlib import Path

from PIL import Image, ImageDraw


Path("icons").mkdir(exist_ok=True)


def draw_icon(size, dark_mode=False):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if dark_mode:
        bg = (15, 23, 42, 255)
        sky = (30, 58, 95, 255)
        ground = (61, 43, 26, 255)
        horizon = (147, 197, 253, 180)
        wheel_color = (96, 165, 250, 255)
        hub_fill = (15, 23, 42, 255)
        rim = (30, 58, 95, 255)
    else:
        bg = (240, 244, 255, 255)
        sky = (219, 234, 254, 255)
        ground = (224, 213, 200, 255)
        horizon = (255, 255, 255, 220)
        wheel_color = (29, 78, 216, 255)
        hub_fill = (29, 78, 216, 255)
        rim = (191, 219, 254, 255)

    s = size
    cx = s // 2
    cy = s // 2
    r_outer = int(s * 0.42)
    r_wheel = int(s * 0.30)
    r_hub = int(s * 0.06)
    r_dot = int(s * 0.03)
    stroke = max(2, int(s * 0.035))
    spoke_w = max(2, int(s * 0.028))
    corner = int(s * 0.22)

    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=corner, fill=bg)
    d.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=sky)

    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=255)
    ground_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd = ImageDraw.Draw(ground_layer)
    gd.rectangle([cx - r_outer, cy, cx + r_outer, cy + r_outer], fill=ground)
    img.paste(ground_layer, mask=mask)

    d.line(
        [cx - r_outer, cy, cx + r_outer, cy],
        fill=horizon,
        width=max(1, int(s * 0.015)),
    )

    d.ellipse(
        [cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer],
        outline=rim,
        width=max(1, int(s * 0.018)),
    )

    d.ellipse(
        [cx - r_wheel, cy - r_wheel, cx + r_wheel, cy + r_wheel],
        outline=wheel_color,
        width=stroke,
    )

    gap = int(r_hub * 1.1)
    spoke_end = int(r_wheel * 0.92)
    spokes = [
        (cx, cy - gap, cx, cy - spoke_end),
        (cx, cy + gap, cx, cy + spoke_end),
        (cx - gap, cy, cx - spoke_end, cy),
        (cx + gap, cy, cx + spoke_end, cy),
    ]
    for x1, y1, x2, y2 in spokes:
        d.line([x1, y1, x2, y2], fill=wheel_color, width=spoke_w)

    d.ellipse([cx - r_hub, cy - r_hub, cx + r_hub, cy + r_hub], fill=hub_fill)

    dot_color = bg if dark_mode else (255, 255, 255, 255)
    d.ellipse([cx - r_dot, cy - r_dot, cx + r_dot, cy + r_dot], fill=dot_color)

    return img


sizes = [
    (180, "icon-180"),
    (192, "icon-192"),
    (512, "icon-512"),
    (1024, "icon-1024"),
]

for size, name in sizes:
    light = draw_icon(size, dark_mode=False)
    light.save(f"icons/{name}.png", "PNG")
    print(f"✓ icons/{name}.png  ({size}x{size}, light)")

    dark = draw_icon(size, dark_mode=True)
    dark.save(f"icons/{name}-dark.png", "PNG")
    print(f"✓ icons/{name}-dark.png  ({size}x{size}, dark)")

print("\nAlle Icons erstellt.")
