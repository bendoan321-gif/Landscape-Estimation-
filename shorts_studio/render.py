"""Build and run ffmpeg commands that turn clips into a vertical 1080x1920 MP4."""
import json
import os
import subprocess
import tempfile

WIDTH, HEIGHT, FPS = 1080, 1920, 30
MAX_CLIPS = 20
MAX_SECONDS = 180


def has_audio(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
         "stream=index", "-of", "json", path],
        capture_output=True, text=True, check=True).stdout
    return bool(json.loads(out).get("streams"))


def validate(clips):
    if not isinstance(clips, list) or not 1 <= len(clips) <= MAX_CLIPS:
        raise ValueError("choose between 1 and %d clips" % MAX_CLIPS)
    clean = []
    total = 0.0
    for c in clips:
        name = os.path.basename(str(c.get("name", "")))
        start = float(c.get("start", 0))
        duration = float(c.get("duration", 0))
        if not name or start < 0 or duration <= 0:
            raise ValueError("invalid clip settings")
        total += duration
        clean.append({"name": name, "start": start, "duration": duration})
    if total > MAX_SECONDS:
        raise ValueError("video too long (max %d seconds)" % MAX_SECONDS)
    return clean


def build_command(clips, paths, audio_flags, output, caption_file=None):
    """clips: validated clips; paths: input file per clip; audio_flags: bool per clip."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for p in paths:
        cmd += ["-i", p]
    parts, labels = [], []
    for i, c in enumerate(clips):
        s, d = c["start"], c["duration"]
        parts.append(
            f"[{i}:v]trim=start={s}:duration={d},setpts=PTS-STARTPTS,"
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS}[v{i}]")
        if audio_flags[i]:
            parts.append(
                f"[{i}:a]atrim=start={s}:duration={d},asetpts=PTS-STARTPTS,"
                f"aresample=44100,aformat=channel_layouts=stereo[a{i}]")
        else:
            parts.append(
                f"anullsrc=r=44100:cl=stereo,atrim=duration={d},"
                f"asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[v{i}][a{i}]")
    n = len(clips)
    last_v = "vout"
    parts.append("".join(labels) + f"concat=n={n}:v=1:a=1[vcat][aout]")
    if caption_file:
        parts.append(
            f"[vcat]drawtext=textfile={caption_file}:fontcolor=white:fontsize=72:"
            f"borderw=4:bordercolor=black:x=(w-text_w)/2:y=h*0.75[{last_v}]")
    else:
        parts.append(f"[vcat]null[{last_v}]")
    cmd += ["-filter_complex", ";".join(parts), "-map", f"[{last_v}]",
            "-map", "[aout]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-movflags", "+faststart", output]
    return cmd


def render(clips, media_dir, output, caption=""):
    clips = validate(clips)
    paths = []
    for c in clips:
        p = os.path.join(media_dir, c["name"])
        if not os.path.isfile(p):
            raise ValueError("clip not found: " + c["name"])
        paths.append(p)
    flags = [has_audio(p) for p in paths]
    caption = (caption or "").strip()[:100]
    if caption:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as f:
            f.write(caption)
            cap = f.name
        # ffmpeg filter option values: escape path characters
        cap_arg = cap.replace("\\", "/").replace(":", "\\:")
    else:
        cap = cap_arg = None
    try:
        subprocess.run(build_command(clips, paths, flags, output, cap_arg),
                       check=True, capture_output=True, text=True)
    finally:
        if cap:
            os.unlink(cap)
