"""
AI Talking-Head Video Generator
Renders a short video with an animated code background, fading text beats,
a D-ID talking head synced to an ElevenLabs voiceover, and a composited output.
"""

import os, sys, math, time, random, json, requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pydub import AudioSegment
from moviepy.editor import ImageSequenceClip, VideoFileClip, CompositeVideoClip, AudioFileClip

# ── API keys (accepts UPPER_CASE or lower_case env var names) ─────────────────
ELEVENLABS_KEY = (os.environ.get("ELEVENLABS_API_KEY")
                  or os.environ.get("elevenlabs_api_key")
                  or "")
D_ID_KEY       = (os.environ.get("D_ID_API_KEY")
                  or os.environ.get("d_id_api_key")
                  or "")
OPENAI_KEY     = (os.environ.get("OPENAI_API_KEY")
                  or os.environ.get("openai_api_key")
                  or "")

if not ELEVENLABS_KEY:
    sys.exit("Error: set ELEVENLABS_API_KEY environment variable")
if not D_ID_KEY:
    sys.exit("Error: set D_ID_API_KEY environment variable")

# ── output ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR = "./output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

AUDIO_PATH = f"{OUTPUT_DIR}/voice.mp3"
WAV_PATH   = f"{OUTPUT_DIR}/voice.wav"
IMG_PATH   = f"{OUTPUT_DIR}/narrator.png"
ANIM_PATH  = f"{OUTPUT_DIR}/talking_head.mp4"
OUT_PATH   = f"{OUTPUT_DIR}/final.mp4"

# ── video settings ─────────────────────────────────────────────────────────────
W, H = 1280, 720
FPS  = 30

# ── content ────────────────────────────────────────────────────────────────────
# Set TOPIC to auto-generate the script, or leave blank and fill BEATS/SPOKEN_TEXT manually
TOPIC = ""

# On-screen text cards, one per beat (supports \n for line breaks)
BEATS = [
    "Jonathan — thanks for\nthe time today.",
    "Your point about curiosity\nreally stuck with me.",
    "Learning fast, building things that matter,\nturning ideas into useful judgment —\nthat's the work I want to keep doing.",
    "Hope we get to talk again.\n— Nick",
]

# Narrated voiceover (read aloud by ElevenLabs)
SPOKEN_TEXT = """\
Hi Jonathan — I really wanted to thank you for the time today.
The way you talked about curiosity resonated with me more than you might expect.
Learning fast, building things that matter, turning ideas into useful judgment —
that's the work I want to keep doing. Hope we get to talk again soon.\
"""

# Prompt used to generate the narrator image via DALL-E 3 (if no photo is provided)
IMAGE_PROMPT = (
    "Professional headshot portrait of a thoughtful, confident person, "
    "front-facing, soft neutral background, photorealistic, suitable for a video presenter"
)

# ── voice settings ─────────────────────────────────────────────────────────────
ELEVENLABS_VOICE_ID = "nPczCjzI2devNBz1zQrb"  # Brian — deep, resonant
VOICE_SETTINGS = {"stability": 0.55, "similarity_boost": 0.75}

# ── background visuals ─────────────────────────────────────────────────────────
BG_COLOR        = (8,   8,  16)
ACCENT_COLOR    = (0,  180, 220)
GRID_COLOR      = (18,  20,  34)
SCREEN_INTERVAL = 5.0   # seconds between code-screen swaps
SCREEN_FADE     = 1.0   # crossfade duration (seconds)

CODE_POOL = [
    "response = llm.chat(messages, stream=True)",
    "embeddings = model.embed(text, normalize=True)",
    "const reply = await llm.complete({ prompt, max_tokens });",
    "agent = Agent(tools=[search, code, browser])",
    "chain = prompt_template | llm | output_parser",
    "async for chunk in llm.stream(messages):",
    "    yield chunk.content",
    "ctx = retrieve(query, top_k=5, threshold=0.8)",
    "history.append({'role': 'user', 'content': msg})",
    "vector_store.upsert(id, embedding, metadata)",
    "if finish_reason == 'tool_call': dispatch(tool_call)",
    "tokens = tokenizer.encode(text, add_special=True)",
    "result = await agent.run(task, max_iterations=12)",
    "memory.summarize(window=10, keep_last=3)",
    "// stream tokens as they arrive",
    "score = eval_pipeline(expected, actual, rubric)",
    "router.dispatch(intent, agents[intent])",
    "reranked = cross_encoder.rank(query, docs)",
    "const { text, usage } = await generate(prompt);",
    "db.store(session_id, messages, ttl=3600)",
    "trace = instrument(llm, callbacks=[logger, tracer])",
    "fallback = llm_b if llm_a.latency > threshold else llm_a",
    "plan = planner.decompose(goal, available_tools)",
    "output = structured_output(schema=ResponseSchema)",
    "cache.set(hash(prompt), response, ttl=300)",
    "// retry with exponential backoff on rate limit",
    "batch = await llm.embed_many(chunks, batch_size=32)",
    "guardrail.check(output, rules=['no_pii', 'on_topic'])",
]

# Pre-build 8 static screen layouts (each shows 10 randomly placed lines)
random.seed(42)
SCREENS = []
for _s in range(8):
    rng = random.Random(_s * 31 + 7)
    chosen = rng.sample(CODE_POOL, 10)
    y_step = H // 11
    positions = [
        (30 + rng.choice([0, 24, 48, 96]) + rng.randint(0, 60),
         y_step * (i + 1) + rng.randint(-18, 18))
        for i in range(10)
    ]
    SCREENS.append(list(zip(chosen, positions)))


# ── fonts ──────────────────────────────────────────────────────────────────────
def load_font(size, mono=False):
    paths = (
        ["/System/Library/Fonts/Helvetica.ttc",
         "/System/Library/Fonts/SFNSDisplay.ttf",
         "/Library/Fonts/Arial.ttf"]
        if not mono else
        ["/System/Library/Fonts/Menlo.ttc",
         "/System/Library/Fonts/Courier New.ttf"]
    )
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

font_main  = load_font(50)
font_small = load_font(15, mono=True)


# ── rendering ──────────────────────────────────────────────────────────────────
def ease(t):
    return t * t * (3 - 2 * t)


def draw_code_screen(draw, screen, alpha_scale, t):
    for i, (line, (x, y)) in enumerate(screen):
        drift   = math.sin(t * 0.15 + i * 1.1) * 5
        opacity = (0.32 + 0.10 * math.sin(t * 0.5 + i)) * alpha_scale
        c = tuple(max(0, min(255, int(ACCENT_COLOR[j] * opacity))) for j in range(3))
        draw.text((x, y + drift), line, font=font_small, fill=c)


def render_frame(t, beat_text, text_alpha):
    img  = Image.new("RGB", (W, H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    for y in range(0, H, 60):
        draw.line([(0, y), (W, y)], fill=GRID_COLOR, width=1)

    screen_f   = t / SCREEN_INTERVAL
    screen_idx = int(screen_f) % len(SCREENS)
    frac       = screen_f - int(screen_f)

    if frac < SCREEN_FADE / SCREEN_INTERVAL:
        blend    = ease(frac / (SCREEN_FADE / SCREEN_INTERVAL))
        prev_idx = (screen_idx - 1) % len(SCREENS)
        draw_code_screen(draw, SCREENS[prev_idx],    1.0 - blend, t)
        draw_code_screen(draw, SCREENS[screen_idx],  blend,       t)
    else:
        draw_code_screen(draw, SCREENS[screen_idx], 1.0, t)

    pulse = int(25 + 12 * math.sin(t * 0.8))
    lc = tuple(int(ACCENT_COLOR[j] * pulse / 255) for j in range(3))
    draw.line([(80, H // 2 + 150), (W - 80, H // 2 + 150)], fill=lc, width=1)

    for cx, cy in [(55, 35), (W - 55, 35), (55, H - 35), (W - 55, H - 35)]:
        p = int(35 + 20 * math.sin(t * 1.1 + cx * 0.01))
        draw.ellipse([(cx-2, cy-2), (cx+2, cy+2)],
                     fill=tuple(int(ACCENT_COLOR[j] * p / 100) for j in range(3)))

    if text_alpha > 0:
        lines = beat_text.split("\n")
        lh = 66
        ty = (H - len(lines) * lh) // 2 - 30
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_main)
            tw   = bbox[2] - bbox[0]
            x    = (W - tw) // 2
            y    = ty + i * lh
            a    = text_alpha
            for dx, dy in [(-1,-1),(1,-1),(-1,1),(1,1)]:
                draw.text((x+dx, y+dy), line, font=font_main,
                          fill=tuple(int(ACCENT_COLOR[j] * 0.4 * a) for j in range(3)))
            draw.text((x, y), line, font=font_main,
                      fill=(int(232*a), int(232*a), int(235*a)))

    return np.array(img)


# ── LLM script generation ──────────────────────────────────────────────────────
def generate_script(topic):
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": (
                f"Write content for a short talking-head video about: {topic}\n\n"
                "Return a JSON object with two keys:\n"
                "- \"beats\": list of 4 short on-screen text cards (each under 60 chars, \\n for line breaks)\n"
                "- \"spoken_text\": a natural 15-20 second voiceover script (3-4 sentences)\n\n"
                "Return only valid JSON."
            )}],
            "response_format": {"type": "json_object"},
        },
    )
    r.raise_for_status()
    result = json.loads(r.json()["choices"][0]["message"]["content"])
    return result["beats"], result["spoken_text"]


# ── ElevenLabs TTS ─────────────────────────────────────────────────────────────
def generate_speech(text, out_path):
    words, current, parts = text.split(), [], []
    for word in words:
        current.append(word)
        if len(" ".join(current).encode()) > 2500:
            current.pop()
            parts.append(" ".join(current))
            current = [word]
    if current:
        parts.append(" ".join(current))

    chunks = []
    for chunk in parts:
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}",
            headers={"xi-api-key": ELEVENLABS_KEY, "Content-Type": "application/json"},
            json={"text": chunk, "voice_settings": VOICE_SETTINGS},
        )
        r.raise_for_status()
        chunks.append(r.content)

    with open(out_path, "wb") as f:
        f.write(b"".join(chunks))


# ── DALL-E narrator image ──────────────────────────────────────────────────────
def generate_narrator_image(prompt, out_path):
    import base64
    r = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
        json={"model": "gpt-image-1", "prompt": prompt, "size": "1024x1024", "n": 1},
    )
    r.raise_for_status()
    entry = r.json()["data"][0]
    if "b64_json" in entry:
        img_data = base64.b64decode(entry["b64_json"])
    else:
        img_data = requests.get(entry["url"]).content
    with open(out_path, "wb") as f:
        f.write(img_data)


# ── D-ID talking head ──────────────────────────────────────────────────────────
def generate_talking_head(img_path, wav_path, out_path):
    auth = f"Basic {D_ID_KEY}"

    print("  uploading photo...")
    with open(img_path, "rb") as f:
        r = requests.post("https://api.d-id.com/images",
                          files={"image": (os.path.basename(img_path), f, "image/png")},
                          headers={"Authorization": auth})
    r.raise_for_status()
    img_url = r.json()["url"]

    print("  uploading audio...")
    with open(wav_path, "rb") as f:
        r = requests.post("https://api.d-id.com/audios",
                          files={"audio": (os.path.basename(wav_path), f, "audio/wav")},
                          headers={"Authorization": auth})
    r.raise_for_status()
    audio_url = r.json()["url"]

    print("  creating talk...")
    r = requests.post(
        "https://api.d-id.com/talks",
        headers={"Authorization": auth, "Content-Type": "application/json"},
        json={
            "source_url": img_url,
            "script": {"type": "audio", "audio_url": audio_url, "ssml": False},
            "config": {"fluent": True, "pad_audio": 0.5, "stitch": True, "result_format": "mp4"},
        },
    )
    r.raise_for_status()
    talk_id = r.json()["id"]

    print(f"  polling (id: {talk_id})...")
    for attempt in range(72):
        poll   = requests.get(f"https://api.d-id.com/talks/{talk_id}",
                              headers={"Authorization": auth}).json()
        status = poll.get("status")
        print(f"  [{attempt+1}] {status}")
        if status == "done" and poll.get("result_url"):
            data = requests.get(poll["result_url"]).content
            with open(out_path, "wb") as f:
                f.write(data)
            return
        if status == "error":
            print(f"  D-ID error: {poll}")
            sys.exit(1)
        time.sleep(5)

    print("Timed out waiting for D-ID animation.")
    sys.exit(1)


# ── pipeline ───────────────────────────────────────────────────────────────────
def main():
    global BEATS, SPOKEN_TEXT

    # ── step 0: generate script ────────────────────────────────────────────────
    if TOPIC:
        if not OPENAI_KEY:
            sys.exit("Error: set OPENAI_API_KEY to generate a script from TOPIC")
        print("Step 0: Generating script from topic...")
        BEATS, SPOKEN_TEXT = generate_script(TOPIC)
        print(f"  {len(BEATS)} beats generated")

    # ── step 1: voiceover ──────────────────────────────────────────────────────
    if not os.path.exists(AUDIO_PATH):
        print("Step 1: Generating voiceover...")
        generate_speech(SPOKEN_TEXT, AUDIO_PATH)
        print(f"  saved {AUDIO_PATH}")
    else:
        print("Step 1: Voiceover exists, skipping.")

    sound = AudioSegment.from_mp3(AUDIO_PATH)
    sound.export(WAV_PATH, format="wav")
    audio_duration = len(sound) / 1000
    print(f"  duration: {audio_duration:.1f}s")

    # ── step 2: narrator image + talking head ─────────────────────────────────
    if not os.path.exists(ANIM_PATH):
        if not os.path.exists(IMG_PATH):
            if not OPENAI_KEY:
                print(f"\nError: no narrator photo at {IMG_PATH} and OPENAI_API_KEY not set.")
                print("Place a square PNG there, or set OPENAI_API_KEY to auto-generate one.")
                sys.exit(1)
            print("Step 2: Generating narrator image...")
            generate_narrator_image(IMAGE_PROMPT, IMG_PATH)
            print(f"  saved {IMG_PATH}")
        print("Step 2: Generating talking head...")
        generate_talking_head(IMG_PATH, WAV_PATH, ANIM_PATH)
        print(f"  saved {ANIM_PATH}")
    else:
        print("Step 2: Talking head exists, skipping.")

    # ── step 3: render background frames ──────────────────────────────────────
    print("Step 3: Rendering background frames...")
    FADE_IN, FADE_OUT = 0.5, 1.0
    beat_dur = audio_duration / len(BEATS)
    frames   = []

    for fi in range(int(audio_duration * FPS)):
        t        = fi / FPS
        beat_idx = min(int(t / beat_dur), len(BEATS) - 1)
        t_local  = t - beat_idx * beat_dur

        if t_local < FADE_IN:
            raw = t_local / FADE_IN
        elif t_local > beat_dur - FADE_OUT:
            raw = (beat_dur - t_local) / FADE_OUT
        else:
            raw = 1.0

        frames.append(render_frame(t, BEATS[beat_idx], ease(max(0.0, min(1.0, raw)))))

        if fi % (FPS * 5) == 0:
            print(f"  {t:.0f}s / {audio_duration:.0f}s")

    # ── step 3: composite ──────────────────────────────────────────────────────
    print("Step 4: Compositing...")
    bg_clip   = ImageSequenceClip(frames, fps=FPS)
    talk_clip = VideoFileClip(ANIM_PATH)

    thumb_w      = int(W * 0.28)
    thumb_h      = int(thumb_w * talk_clip.h / talk_clip.w)
    talk_resized = (
        talk_clip
        .resize(width=thumb_w)
        .set_position((W - thumb_w - 30, H - thumb_h - 30))
        .set_duration(bg_clip.duration)
        .crossfadein(0.5)
    )

    audio = AudioFileClip(AUDIO_PATH).set_duration(bg_clip.duration)
    final = CompositeVideoClip([bg_clip, talk_resized], size=(W, H)).set_audio(audio)
    final.write_videofile(OUT_PATH, codec="libx264", audio_codec="aac", fps=FPS,
                          ffmpeg_params=["-crf", "18", "-preset", "fast"])

    print(f"\nDone → {OUT_PATH}")


if __name__ == "__main__":
    main()
