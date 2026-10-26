from PIL import Image, ImageDraw
from pathlib import Path


size = 512
scale = 2
image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)

# Soft periwinkle app tile with a simple caption card mark.
draw.rounded_rectangle((24, 24, 488, 488), radius=112, fill="#526FE4")
draw.rounded_rectangle((92, 82, 420, 322), radius=44, fill="#FFFFFF")
draw.polygon(((124, 292), (120, 370), (200, 307)), fill="#FFFFFF")
draw.rounded_rectangle((148, 142, 364, 174), radius=16, fill="#526FE4")
draw.rounded_rectangle((148, 211, 318, 243), radius=16, fill="#94A6F6")
draw.rounded_rectangle((299, 354, 404, 386), radius=16, fill="#CFEDE4")

image.resize((256, 256), Image.Resampling.LANCZOS).save(
    Path(__file__).resolve().parents[1] / "assets" / "subtitle_organizer.ico",
    format="ICO",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
