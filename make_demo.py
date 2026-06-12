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

generate.IMAGE_PROMPT = (
    "Professional AI researcher and software developer, front-facing headshot portrait, "
    "confident expression, modern tech aesthetic, photorealistic, clean neutral background"
)

generate.BEATS = [
    "Give it a photo,\na script, and a voice.",
    "It generates the voiceover,\nanimates your face,\nand renders the background.",
    "One command.\nOne MP4.",
    "Built with Python\n+ ElevenLabs + D-ID",
]

generate.SPOKEN_TEXT = """\
This tool generates short talking-head videos from a photo and a script.
Drop in your image, write what you want to say, and it handles the voiceover,
lip sync, and animated background automatically.
One command. One output file.\
"""

if __name__ == "__main__":
    generate.main()
