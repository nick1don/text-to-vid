"""
Generates the repo demo video using the same pipeline as generate.py.
Run once, upload output/demo.mp4 to a GitHub Release, paste the URL in README.md.
"""

import generate

# ── override config for the demo ───────────────────────────────────────────────
generate.OUTPUT_DIR = "./output"
generate.AUDIO_PATH = "./output/demo_voice.mp3"
generate.WAV_PATH   = "./output/demo_voice.wav"
generate.IMG_PATH   = "./output/demo_narrator.png"
generate.ANIM_PATH  = "./output/demo_head.mp4"
generate.OUT_PATH   = "./output/demo.mp4"

generate.TOPIC = (
    "An open-source Python tool that generates talking-head videos "
    "from just a photo and a prompt, using AI for voice, animation, and visuals"
)

generate.IMAGE_PROMPT = (
    "Professional AI researcher and software developer, front-facing headshot portrait, "
    "confident expression, modern tech aesthetic, photorealistic, clean neutral background"
)

if __name__ == "__main__":
    generate.main()
