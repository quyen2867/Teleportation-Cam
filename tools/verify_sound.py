"""Play the bundled Goku cue through a real output; never record a microphone."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from animecam.sound import load_sound, default_sound_path


def run(report_path):
    import sounddevice as sd

    samples, rate = load_sound()
    samples = samples * 0.3
    report = {"scope": "Real audio output only; no microphone capture or call-app verification",
              "duration_seconds": len(samples) / rate, "volume": 0.3,
              "sound_file": str(default_sound_path()),
              "playback_finished": False}
    try:
        report["output_name"] = sd.query_devices(kind="output")["name"]
        sd.play(samples, rate, blocking=False)
        sd.wait()
        report["playback_finished"] = True
        report["status"] = str(sd.get_status())
    except Exception as exc:
        report["error"] = str(exc)
    finally:
        sd.stop()
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return int(not report["playback_finished"])


if __name__ == "__main__":
    raise SystemExit(run("artifacts/sound-smoke-0.1.3.json"))
