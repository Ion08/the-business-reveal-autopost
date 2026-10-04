#!/usr/bin/env python3
"""Package the verified 30-post campaign as small, public JPEG assets."""

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "campaign"
DEST = ROOT / "assets"


def main() -> None:
    posts = json.loads((SOURCE / "content_manifest.json").read_text(encoding="utf-8"))
    captions = json.loads((SOURCE / "captions.json").read_text(encoding="utf-8"))
    if len(posts) != 30 or len(captions) != 30:
        raise ValueError("Expected 30 posts and 30 captions")

    output = []
    for index, (post, caption) in enumerate(zip(posts, captions), 1):
        day = (index - 1) // 3 + 1
        slot = (9, 14, 19)[(index - 1) % 3]
        date = caption["date"]
        directory = DEST / date / f"{slot:02d}-00"
        directory.mkdir(parents=True, exist_ok=True)
        images = []
        for slide in range(1, 6):
            source = SOURCE / "images" / f"day-{day:02d}" / f"post-{index:02d}-{post['slug']}" / f"slide-{slide:02d}.png"
            destination = directory / f"slide-{slide:02d}.jpg"
            with Image.open(source) as image:
                if image.size != (1122, 1402):
                    raise ValueError(f"Unexpected image dimensions: {source}: {image.size}")
                image.convert("RGB").save(destination, "JPEG", quality=92, optimize=True, subsampling=0)
            images.append(destination.relative_to(ROOT).as_posix())
        output.append({
            "id": f"post-{index:02d}",
            "date": date,
            "slot": slot,
            "brand": post["brand"],
            "caption": caption["caption"],
            "images": images,
        })

    (ROOT / "data" / "posts.json").write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Prepared {len(output)} posts and {len(output) * 5} JPEG assets")


if __name__ == "__main__":
    main()
