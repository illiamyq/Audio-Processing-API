import asyncio
import json
import os
import tempfile

import anthropic
import librosa

from app.models.audio import AudioFile
from app.services import storage
from app.setup.config import settings
from app.tasks.processing import _compute_snr, _ext, _transcode_to_mp3

SYSTEM = (
    "You advise on MP3 compression for one audio file. Use the tools to measure "
    "candidate bitrates instead of guessing. Test at most 4 bitrates, then recommend "
    "one and justify it with the measured size and SNR."
)

TOOLS = [
    {
        "name": "get_metadata",
        "description": "Duration, sample rate, BPM and original size of the file.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_existing_results",
        "description": "Compression results already computed (128k and 64k).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "transcode_and_measure",
        "description": "Transcode the original to MP3 at a bitrate and return size and SNR in dB.",
        "input_schema": {
            "type": "object",
            "properties": {"bitrate_kbps": {"type": "integer", "minimum": 32, "maximum": 320}},
            "required": ["bitrate_kbps"],
        },
    },
]


def _transcode_and_measure(record: AudioFile, bitrate_kbps: int) -> dict:
    raw = storage.download_bytes(record.original_key)
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src" + _ext(record.filename))
        out = os.path.join(tmp, "out.mp3")
        with open(src, "wb") as f:
            f.write(raw)
        _transcode_to_mp3(src, out, f"{bitrate_kbps}k")
        y, sr = librosa.load(src, sr=None, mono=True)
        y_c, _ = librosa.load(out, sr=sr, mono=True)
        return {
            "bitrate_kbps": bitrate_kbps,
            "size_bytes": os.path.getsize(out),
            "snr_db": round(_compute_snr(y, y_c), 2),
        }


def _run_tool(record: AudioFile, name: str, args: dict) -> dict:
    if name == "get_metadata":
        return {
            "duration_seconds": record.duration_seconds,
            "sample_rate": record.sample_rate,
            "bpm": record.bpm,
            "original_size_bytes": record.size_bytes,
        }
    if name == "get_existing_results":
        return record.compression_results or {}
    if name == "transcode_and_measure":
        bitrate = max(32, min(320, int(args["bitrate_kbps"])))
        return _transcode_and_measure(record, bitrate)
    return {"error": f"unknown tool {name}"}


async def advise(record: AudioFile, goal: str, max_steps: int = 6) -> dict:
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    messages = [{"role": "user", "content": goal}]
    trace = []
    for _ in range(max_steps):
        resp = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1024,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return {"recommendation": text, "trace": trace}
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = await asyncio.to_thread(_run_tool, record, block.name, block.input)
                trace.append({"tool": block.name, "input": block.input, "output": out})
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out)}
                )
        messages.append({"role": "user", "content": results})
    return {"recommendation": "Step limit reached without a conclusion.", "trace": trace}