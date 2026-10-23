"""Encode captured frames only. Pillow is a development dependency."""
import json
import argparse
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--frames',default='outputs/stage62_motion_frames')
parser.add_argument('--output',default='outputs/stage62_theme.gif')
args=parser.parse_args()
source = root / args.frames
records = json.loads((source / 'frames.json').read_text(encoding='utf-8'))
frames, durations = [], []
for i, record in enumerate(records):
    with Image.open(source / record['file']) as image:
        resized = image.convert('RGB').resize((960, 645), Image.Resampling.LANCZOS)
        frames.append(resized.quantize(colors=192))
    duration = records[i+1]['atMs'] - record['atMs'] if i+1 < len(records) else 600
    durations.append(max(20, round(duration / 10) * 10))
target = root / args.output
frames[0].save(target, save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=2)
print(json.dumps({'frames': len(frames), 'durationMs': sum(durations), 'bytes': target.stat().st_size}))
