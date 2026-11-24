"""
Generates multi-resolution brand assets from gemini-svg.svg:
- assets/app_icon.ico (256, 128, 64, 48, 32, 16)
- assets/app_logo.png (512x512)
- assets/app_logo.svg
- Android companion launcher mipmaps (mdpi, hdpi, xhdpi, xxhdpi, xxxhdpi)
"""
import os
import shutil
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QImage, QPainter, QPainterPath
from PyQt6.QtSvg import QSvgRenderer
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SVG_PATH = os.path.join(BASE_DIR, "gemini-svg.svg")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
ANDROID_RES_DIR = os.path.join(BASE_DIR, "android_companion", "app", "src", "main", "res")


def render_svg_to_qimage(svg_path: str, size: int) -> QImage:
    renderer = QSvgRenderer(svg_path)
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return img


def qimage_to_pil(qimg: QImage) -> Image.Image:
    ptr = qimg.bits()
    ptr.setsize(qimg.sizeInBytes())
    return Image.frombuffer('RGBA', (qimg.width(), qimg.height()), bytes(ptr), 'raw', 'BGRA', 0, 1)


def create_circular_icon(pil_img: Image.Image) -> Image.Image:
    from PIL import ImageDraw
    size = pil_img.size
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size[0], size[1]), fill=255)
    
    out = Image.new('RGBA', size, (0, 0, 0, 0))
    out.paste(pil_img, (0, 0), mask=mask)
    return out


def main():
    print(f"Reading SVG from: {SVG_PATH}")
    assert os.path.exists(SVG_PATH), f"Missing {SVG_PATH}"

    # 1. Copy SVG to assets/app_logo.svg
    os.makedirs(ASSETS_DIR, exist_ok=True)
    dest_svg = os.path.join(ASSETS_DIR, "app_logo.svg")
    shutil.copyfile(SVG_PATH, dest_svg)
    print(f"Saved: {dest_svg}")

    # 2. Render 512x512 master PNG
    img_512 = render_svg_to_qimage(SVG_PATH, 512)
    png_512_path = os.path.join(ASSETS_DIR, "app_logo.png")
    img_512.save(png_512_path, "PNG")
    print(f"Saved: {png_512_path}")

    # 3. Generate multi-resolution ICO for Windows
    ico_sizes = [256, 128, 64, 48, 32, 16]
    pil_images = []
    for s in ico_sizes:
        qimg = render_svg_to_qimage(SVG_PATH, s)
        pil_images.append(qimage_to_pil(qimg))

    ico_path = os.path.join(ASSETS_DIR, "app_icon.ico")
    pil_images[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in ico_sizes],
        append_images=pil_images[1:]
    )
    print(f"Saved: {ico_path} with sizes {ico_sizes}")

    # 4. Generate Android companion launcher icons
    android_densities = {
        "mipmap-mdpi": 48,
        "mipmap-hdpi": 72,
        "mipmap-xhdpi": 96,
        "mipmap-xxhdpi": 144,
        "mipmap-xxxhdpi": 192,
    }

    for folder, size in android_densities.items():
        dir_path = os.path.join(ANDROID_RES_DIR, folder)
        os.makedirs(dir_path, exist_ok=True)

        qimg = render_svg_to_qimage(SVG_PATH, size)
        pil_img = qimage_to_pil(qimg)

        # Standard launcher icon
        launcher_path = os.path.join(dir_path, "ic_launcher.png")
        pil_img.save(launcher_path, "PNG")

        # Round launcher icon
        round_img = create_circular_icon(pil_img)
        round_path = os.path.join(dir_path, "ic_launcher_round.png")
        round_img.save(round_path, "PNG")

        print(f"Saved Android {folder} ({size}x{size}): {launcher_path} and {round_path}")

    # Clean up any test render
    test_file = os.path.join(BASE_DIR, "test_render.png")
    if os.path.exists(test_file):
        os.remove(test_file)

    print("All brand assets generated successfully!")


if __name__ == "__main__":
    main()
