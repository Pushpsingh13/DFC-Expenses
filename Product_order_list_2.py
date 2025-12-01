import os
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------
# FOLDER FOR AUTO-GENERATED IMAGES
# ---------------------------------------------------------
IMAGE_FOLDER = "generated_images"

if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)


# ---------------------------------------------------------
# FIX: REPLACEMENT FOR DEPRECATED textsize()
# ---------------------------------------------------------
def get_text_size(draw, text, font):
    """Get text width and height using textbbox() (Pillow 10 compatible)."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


# ---------------------------------------------------------
# PLACEHOLDER IMAGE GENERATOR
# ---------------------------------------------------------
def generate_placeholder(product_name: str) -> str:

    # Clean special chars → safe filename
    safe_name = "".join(
        c if c.isalnum() or c in " _-" else "_"
        for c in str(product_name)
    ).strip()

    if safe_name == "":
        safe_name = "product"

    file_name = f"{safe_name}.png"
    img_path = os.path.join(IMAGE_FOLDER, file_name)

    # If file already generated → return it
    if os.path.exists(img_path):
        return img_path

    # Create placeholder 360x240
    width, height = 360, 240
    img = Image.new("RGB", (width, height), color=(245, 245, 245))
    draw = ImageDraw.Draw(img)

    # Load font
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except:
        font = ImageFont.load_default()

    text = str(product_name)

    # Measure text
    w, h = get_text_size(draw, text, font)

    # If too long → split in two lines
    if w > width - 40:
        parts = text.split()
        mid = len(parts) // 2
        line1 = " ".join(parts[:mid])
        line2 = " ".join(parts[mid:])

        w1, h1 = get_text_size(draw, line1, font)
        w2, h2 = get_text_size(draw, line2, font)

        draw.text(((width - w1) / 2, height / 2 - 20), line1, fill="black", font=font)
        draw.text(((width - w2) / 2, height / 2 + 5), line2, fill="black", font=font)

    else:
        draw.text(((width - w) / 2, (height - h) / 2), text, fill="black", font=font)

    # Border box
    draw.rectangle([1, 1, width - 2, height - 2], outline=(200, 200, 200))

    img.save(img_path, format="PNG")

    return img_path


# ---------------------------------------------------------
# LOAD PRODUCT LIST WITH WEIGHT SUPPORT
# ---------------------------------------------------------
def load_products():
    df = pd.read_excel("product_list.xlsx")

    # Ensure columns exist
    if "Product" not in df.columns:
        raise KeyError("Your Excel file must contain a 'Product' column!")

    if "Weight" not in df.columns:
        df["Weight"] = ""    # Auto-add empty weight column

    # Create placeholder image per product
    df["Image"] = df["Product"].astype(str).apply(generate_placeholder)

    return df


# ---------------------------------------------------------
# TEST ONLY — REMOVE WHEN RUNNING IN STREAMLIT
# ---------------------------------------------------------
if __name__ == "__main__":
    df = load_products()
    print(df.head())
