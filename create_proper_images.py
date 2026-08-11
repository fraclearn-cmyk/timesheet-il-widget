#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Create properly sized images for amoCRM widget
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_image(width, height, text, filename):
    """Create a simple colored image with text"""
    # Create image with gradient background
    img = Image.new('RGB', (width, height), color='#3498db')
    draw = ImageDraw.Draw(img)
    
    # Add border
    draw.rectangle([(0, 0), (width-1, height-1)], outline='#2c3e50', width=2)
    
    # Add text
    try:
        # Try to use a nice font
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        # Fallback to default font
        font = ImageFont.load_default()
    
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Center text
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    # Draw text with shadow
    draw.text((x+2, y+2), text, fill='#000000', font=font)
    draw.text((x, y), text, fill='#ffffff', font=font)
    
    # Save image
    img.save(filename, 'PNG')
    print(f"[OK] Created: {filename} ({width}x{height}px)")

if __name__ == "__main__":
    print("=" * 60)
    print(" Creating properly sized images for amoCRM widget")
    print("=" * 60)
    print("")
    
    # Create directories
    os.makedirs("widget/images", exist_ok=True)
    os.makedirs("widget_minimal/images", exist_ok=True)
    
    # Create images with correct sizes for amoCRM
    # Logo: 130x100px
    create_image(130, 100, "Logo", "widget/images/logo.png")
    create_image(130, 100, "Logo", "widget_minimal/images/logo.png")
    
    # Logo Main: 400x272px (required for widget_main)
    create_image(400, 272, "Main Logo", "widget/images/logo_main.png")
    create_image(400, 272, "Main Logo", "widget_minimal/images/logo_main.png")
    
    # Logo Small: 108x108px (required for widget_small)
    create_image(108, 108, "Small", "widget/images/logo_small.png")
    create_image(108, 108, "Small", "widget_minimal/images/logo_small.png")
    
    # Icon: assuming 16x16 or 32x32 (common sizes)
    create_image(32, 32, "IC", "widget/images/icon.png")
    create_image(32, 32, "IC", "widget_minimal/images/icon.png")
    
    # Tour images: 600x400px (standard tutorial size)
    create_image(600, 400, "Tour RU", "widget/images/tour_ru.png")
    create_image(600, 400, "Tour EN", "widget/images/tour_en.png")
    create_image(600, 400, "Tour RU", "widget_minimal/images/tour_ru.png")
    
    print("")
    print("SUCCESS! All images created with proper sizes!")
    print("")
    print("Image sizes:")
    print("  logo.png      130x100px  (required by amoCRM)")
    print("  icon.png      32x32px    (standard icon size)")
    print("  tour_*.png    600x400px  (tutorial images)")
    print("")
    input("Press Enter to exit...")
