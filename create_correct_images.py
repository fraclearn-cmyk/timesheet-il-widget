#!/usr/bin/env python3
"""Create correct size images for amoCRM widget"""

from PIL import Image, ImageDraw, ImageFont

def create_logo_medium():
    """Create logo_medium.png 240x84px"""
    img = Image.new('RGB', (240, 84), color='#4A90E2')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    text = "Табель IL"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (240 - text_width) // 2
    y = (84 - text_height) // 2
    
    draw.text((x, y), text, fill='white', font=font)
    
    img.save('widget/images/logo_medium.png')
    print(f"✅ Created logo_medium.png (240x84)")

def create_logo_min():
    """Create logo_min.png 84x84px"""
    img = Image.new('RGB', (84, 84), color='#4A90E2')
    draw = ImageDraw.Draw(img)
    
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except:
        font = ImageFont.load_default()
    
    text = "TL"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (84 - text_width) // 2
    y = (84 - text_height) // 2
    
    draw.text((x, y), text, fill='white', font=font)
    
    img.save('widget/images/logo_min.png')
    print(f"✅ Created logo_min.png (84x84)")

if __name__ == "__main__":
    print("Creating correct size images...")
    print("-" * 40)
    
    create_logo_medium()
    create_logo_min()
    
    print("-" * 40)
    print("✅ Done!")
