"""Optimize avatar GLB: resize 4K PNGs, drop unused leftover clips optional."""
import io
import json
import struct
from pathlib import Path

from PIL import Image

SRC = Path(r"e:\desctop\00myProjects\Matrics\3d\avatar_try_f.glb")
DST = Path(r"e:\desctop\00myProjects\Matrics\frontend\src\assets\models\avatar_f.glb")

KEEP_ANIMS = {
    "cool_dance",
    "happy_idle",
    "jump_cool",
    "neutral_idle",
    "roll_down",
    "run",
    "sad_idle",
}

# В части экспортов клипы перепутаны (run = jump_cool по длительности).
DURATION_NAMES = (
    (0.767, "run"),
    (1.133, "jump_cool"),
    (1.433, "roll_down"),
    (2.633, "jump"),
    (2.833, "sad_idle"),
    (2.967, "happy_idle"),
    (8.800, "neutral_idle"),
    (23.333, "cool_dance"),
)

MAX_TEX = 2048
JPEG_QUALITY = 86


def parse_glb(data: bytes):
    offset = 12
    gltf = None
    bin_chunk = b""
    while offset < len(data):
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        offset += 8
        chunk = data[offset : offset + chunk_len]
        offset += chunk_len
        if chunk_type == 0x4E4F534A:
            gltf = json.loads(chunk)
        elif chunk_type == 0x004E4942:
            bin_chunk = chunk
    return gltf, bin_chunk


def view_bytes(gltf, bin_chunk, idx):
    bv = gltf["bufferViews"][idx]
    start = bv.get("byteOffset", 0)
    return bin_chunk[start : start + bv["byteLength"]]


def recompress_image(raw: bytes, name: str) -> tuple[bytes, str]:
    img = Image.open(io.BytesIO(raw))
    img = img.convert("RGBA") if img.mode in ("P", "LA") else img
    w, h = img.size
    scale = min(1.0, MAX_TEX / max(w, h))
    if scale < 1:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    is_normal = "normal" in (name or "").lower()
    out = io.BytesIO()
    if is_normal:
        img = img.convert("RGB")
        img.save(out, format="JPEG", quality=88, optimize=True)
        return out.getvalue(), "image/jpeg"
    img = img.convert("RGB")
    img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue(), "image/jpeg"


def rebuild(gltf, blobs: list[bytes]) -> bytes:
    """blobs[i] is the new payload for bufferView i (already padded)."""
    aligned = []
    offset = 0
    for blob in blobs:
        pad = (4 - (len(blob) % 4)) % 4
        payload = blob + b"\x00" * pad
        aligned.append(payload)
        offset += len(payload)
    bin_chunk = b"".join(aligned)
    offset = 0
    for i, payload in enumerate(aligned):
        gltf["bufferViews"][i]["byteOffset"] = offset
        gltf["bufferViews"][i]["byteLength"] = len(blobs[i])  # original unpadded length
        offset += len(payload)
    gltf["buffers"] = [{"byteLength": len(bin_chunk)}]
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes = json_bytes + b" " * json_pad
    bin_pad = (4 - (len(bin_chunk) % 4)) % 4
    bin_chunk = bin_chunk + b"\x00" * bin_pad
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_chunk)
    header = struct.pack("<III", 0x46546C67, 2, total)
    json_header = struct.pack("<II", len(json_bytes), 0x4E4F534A)
    bin_header = struct.pack("<II", len(bin_chunk), 0x004E4942)
    return header + json_header + json_bytes + bin_header + bin_chunk


def _clip_duration(gltf, anim) -> float:
    accessors = gltf.get("accessors") or []
    times = []
    for sampler in anim.get("samplers") or []:
        mx = accessors[sampler["input"]].get("max")
        if mx:
            times.append(mx[0] if isinstance(mx, list) else mx)
    return max(times) if times else 0.0


def _name_by_duration(duration: float) -> str | None:
    for target, name in DURATION_NAMES:
        if abs(duration - target) < 0.08:
            return name
    return None


def _select_animations(gltf, original_anims):
    """Оставляет канонические клипы; чинит перепутанные имена по длительности."""
    chosen = {}
    for anim in original_anims:
        name = anim.get("name")
        if name in KEEP_ANIMS:
            chosen[name] = anim

    run = chosen.get("run")
    if run and _name_by_duration(_clip_duration(gltf, run)) == "jump_cool" and "jump_cool" not in chosen:
        run["name"] = "jump_cool"
        chosen["jump_cool"] = run
        del chosen["run"]

    for anim in original_anims:
        inferred = _name_by_duration(_clip_duration(gltf, anim))
        if inferred in KEEP_ANIMS and inferred not in chosen:
            anim["name"] = inferred
            chosen[inferred] = anim

    return [chosen[name] for name in KEEP_ANIMS if name in chosen]


def main():
    import sys

    src = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else DST
    gltf, bin_chunk = parse_glb(src.read_bytes())
    views = gltf["bufferViews"]
    blobs = [view_bytes(gltf, bin_chunk, i) for i in range(len(views))]

    original_anims = gltf.get("animations") or []
    gltf["animations"] = _select_animations(gltf, original_anims)
    print("kept animations:", [a.get("name") for a in gltf["animations"]])

    for img in gltf.get("images") or []:
        idx = img["bufferView"]
        name = img.get("name") or ""
        new_bytes, mime = recompress_image(blobs[idx], name)
        print(f"image {name}: {len(blobs[idx])} -> {len(new_bytes)} {mime}")
        blobs[idx] = new_bytes
        img["mimeType"] = mime

    dst.parent.mkdir(parents=True, exist_ok=True)
    out = rebuild(gltf, blobs)
    dst.write_bytes(out)
    print(f"wrote {dst} ({len(out)} bytes, was {src.stat().st_size})")


if __name__ == "__main__":
    main()
