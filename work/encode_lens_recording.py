"""Encode the actual Qt frames. Uses Pillow from the bundled artifact runtime."""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / 'outputs/stage61_motion_frames'
records = json.loads((folder / 'frames.json').read_text(encoding='utf-8'))
frames, durations = [], []
for index, record in enumerate(records):
    with Image.open(folder / record['path']) as source:
        frame = source.convert('RGB').resize((960, 675), Image.Resampling.LANCZOS)
        frames.append(frame.quantize(colors=192))
    elapsed = records[index + 1]['time'] - record['time'] if index + 1 < len(records) else .6
    durations.append(max(40, min(1400, round(elapsed * 1000))))
target = ROOT / 'outputs/stage61_motion.gif'
frames[0].save(target, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True, disposal=2)
print(json.dumps({'path': str(target), 'bytes': target.stat().st_size, 'frames': len(frames), 'durationMs': sum(durations)}))
