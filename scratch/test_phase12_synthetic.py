"""
Live verification of LocalHeuristicVisionProvider and VisionAnalyzer on synthetic desktop image.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont
from vision.analyzer import VisionAnalyzer
from vision.models import OCRResult, OCRTextBlock
from vision.ocr import MockOCRProvider
from vision.providers import LocalHeuristicVisionProvider
from vision.screenshot import ScreenshotEngine
from tools.vision import (
    AnalyzeScreenRegionTool,
    AnalyzeScreenTool,
    DescribeScreenTool,
    FindVisualElementTool,
    GetScreenElementsTool,
)

# 1. Create a simulated desktop image (1920x1080)
img = Image.new("RGB", (1920, 1080), color=(240, 240, 240))
draw = ImageDraw.Draw(img)

# Title bar
draw.rectangle([(0, 0), (1920, 40)], fill=(30, 30, 30))
draw.text((20, 10), "Untitled - Notepad", fill=(255, 255, 255))

# Menu items
draw.text((20, 50), "File   Edit   View   Help", fill=(0, 0, 0))

# Content
draw.text((50, 150), "CHARVIS VISION TEST", fill=(0, 0, 0))

# Buttons
draw.rectangle([(100, 300), (180, 335)], fill=(200, 200, 200), outline=(100, 100, 100))
draw.text((120, 310), "Save", fill=(0, 0, 0))

draw.rectangle([(200, 300), (280, 335)], fill=(200, 200, 200), outline=(100, 100, 100))
draw.text((220, 310), "Cancel", fill=(0, 0, 0))

# Settings button
draw.rectangle([(1800, 10), (1880, 35)], fill=(60, 60, 60))
draw.text((1810, 15), "Settings", fill=(255, 255, 255))

# Create OCR result matching image
ocr_res = OCRResult(
    full_text="Untitled - Notepad File Edit View Help CHARVIS VISION TEST Save Cancel Settings",
    blocks=[
        OCRTextBlock("Untitled", 99.0, 20, 10, 70, 20),
        OCRTextBlock("-", 90.0, 95, 10, 10, 20),
        OCRTextBlock("Notepad", 98.0, 110, 10, 70, 20),
        OCRTextBlock("Settings", 95.0, 1810, 15, 60, 20),
        OCRTextBlock("File", 92.0, 20, 50, 30, 18),
        OCRTextBlock("Edit", 92.0, 60, 50, 30, 18),
        OCRTextBlock("View", 92.0, 100, 50, 35, 18),
        OCRTextBlock("Help", 92.0, 145, 50, 35, 18),
        OCRTextBlock("CHARVIS", 97.0, 50, 150, 75, 22),
        OCRTextBlock("VISION", 97.0, 135, 150, 60, 22),
        OCRTextBlock("TEST", 97.0, 205, 150, 45, 22),
        OCRTextBlock("Save", 96.0, 120, 310, 40, 20),
        OCRTextBlock("Cancel", 94.0, 220, 310, 50, 20),
    ],
    image_width=1920,
    image_height=1080,
)

mock_grabber = lambda **k: img if not k.get("bbox") else img.crop(k["bbox"])
engine = ScreenshotEngine(grabber=mock_grabber)
mock_ocr = MockOCRProvider(default_text=ocr_res.full_text, blocks=ocr_res.blocks)
provider = LocalHeuristicVisionProvider()
analyzer = VisionAnalyzer(
    screenshot_engine=engine,
    ocr_provider=mock_ocr,
    vision_provider=provider,
)

print("--- 1. Testing analyze_screen ---")
t_analyze = AnalyzeScreenTool(analyzer=analyzer)
res1 = t_analyze.execute()
print(f"Success: {res1['success']}")
print(f"Application: {res1['application']}")
print(f"Summary: {res1['summary']}")
print(f"Element count: {res1['element_count']}")
assert res1["application"] == "Notepad"
assert res1["element_count"] > 0

print("\n--- 2. Testing describe_screen ---")
t_desc = DescribeScreenTool(analyzer=analyzer)
res2 = t_desc.execute()
print(f"Summary: {res2['summary']}")
assert "Notepad" in res2["summary"]

print("\n--- 3. Testing find_visual_element ('Settings') ---")
t_find = FindVisualElementTool(analyzer=analyzer)
res3 = t_find.execute(description="Settings")
print(f"Found: {res3['found']}")
print(f"Matches: {len(res3['matches'])}")
assert res3["found"] is True
assert res3["matches"][0]["element_type"] == "button"
print(f"Match 0: {res3['matches'][0]}")

print("\n--- 4. Testing find_visual_element ('CHARVIS') ---")
res4 = t_find.execute(description="CHARVIS")
print(f"Found: {res4['found']}")
print(f"Match 0: {res4['matches'][0]}")
assert res4["found"] is True

print("\n--- 5. Testing analyze_screen_region ---")
t_reg = AnalyzeScreenRegionTool(analyzer=analyzer)
res5 = t_reg.execute(x=100, y=250, width=400, height=200)
print(f"Success: {res5['success']}")
print(f"Region elements: {res5['element_count']}")
assert res5["success"] is True

print("\n--- 6. Testing get_screen_elements ---")
t_elem = GetScreenElementsTool(analyzer=analyzer)
res6 = t_elem.execute()
print(f"Element count: {res6['element_count']}")
assert res6["element_count"] > 0

print("\n[ALL SYNTHETIC DESKTOP TESTS PASSED]")
