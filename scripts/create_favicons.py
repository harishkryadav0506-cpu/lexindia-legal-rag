"""Generate LexIndia favicon.ico and icon.svg based on navbar logo."""
import os
from PIL import Image, ImageDraw

def create_favicon():
    # 64x64 icon
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer gradient approximation (amber border with rounded corners)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=14, fill=(245, 158, 11, 255))
    # Inner dark slate (slate-950: #020617)
    draw.rounded_rectangle([3, 3, size - 4, size - 4], radius=11, fill=(2, 6, 23, 255))

    # Draw gold scale/balance icon in amber-400 (#fbbf24 = 251, 191, 36)
    color = (251, 191, 36, 255)
    w = 3

    # Scale transform from 24x24 lucide coords to 64x64 coords
    # Center 24x24 box scaled by ~1.8 in center of 64x64 (offset ~10.4)
    # Center pillar: (32, 14) to (32, 50)
    draw.line([(32, 14), (32, 50)], fill=color, width=w)
    # Base: (22, 50) to (42, 50)
    draw.line([(22, 50), (42, 50)], fill=color, width=w)
    # Beam: top beam
    draw.line([(14, 22), (50, 22)], fill=color, width=w)

    # Left pan: triangle-ish
    draw.polygon([(14, 22), (8, 38), (20, 38)], outline=color, width=w)
    # Right pan: triangle-ish
    draw.polygon([(50, 22), (44, 38), (56, 38)], outline=color, width=w)

    # Save as ICO (multiple sizes: 16, 32, 48, 64)
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    
    app_ico = "frontend/app/favicon.ico"
    public_ico = "frontend/public/favicon.ico"
    
    img.save(app_ico, format="ICO", sizes=sizes)
    img.save(public_ico, format="ICO", sizes=sizes)
    print(f"Saved {app_ico} and {public_ico}")

    # Also save frontend/app/icon.svg
    svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" width="32" height="32">
  <defs>
    <linearGradient id="amberGrad" x1="0%" y1="100%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#d97706" />
      <stop offset="100%" stop-color="#fbbf24" />
    </linearGradient>
  </defs>
  <rect width="32" height="32" rx="8" fill="url(#amberGrad)" />
  <rect x="1.5" y="1.5" width="29" height="29" rx="6.5" fill="#020617" />
  <g transform="translate(4, 4)" stroke="#fbbf24" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
    <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/>
    <path d="M7 21h10"/>
    <path d="M12 3v18"/>
    <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>
  </g>
</svg>'''
    with open("frontend/app/icon.svg", "w", encoding="utf-8") as f:
        f.write(svg_content)
    with open("frontend/public/icon.svg", "w", encoding="utf-8") as f:
        f.write(svg_content)
    print("Saved frontend/app/icon.svg and frontend/public/icon.svg")

if __name__ == "__main__":
    create_favicon()
