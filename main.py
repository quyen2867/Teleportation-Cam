"""Launch AnimeCam FX. No model downloads, camera access or network at import."""
import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="AnimeCam FX — offline anime webcam effects")
    parser.add_argument("--ui-smoke", action="store_true", help="Open UI briefly without accessing webcam")
    parser.add_argument("--screenshot", type=Path, help="Save UI screenshot during --ui-smoke")
    parser.add_argument("--pipeline-smoke", action="store_true", help="Run real webcam/AI/output diagnostic without saving frames")
    parser.add_argument("--sound-smoke", action="store_true", help="Play the short return cue through the default audio output")
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--virtual", action="store_true", help="Include OBS output in --pipeline-smoke")
    parser.add_argument("--seconds", type=float, default=8)
    parser.add_argument("--report", type=Path, default=Path("artifacts/live-smoke.json"))
    args, app_args = parser.parse_known_args()
    if args.sound_smoke:
        from tools.verify_sound import run as verify_sound
        return verify_sound(args.report)
    if args.pipeline_smoke:
        from tools.live_smoke import main as live_smoke
        smoke_args = ["--camera", str(args.camera), "--seconds", str(args.seconds), "--report", str(args.report)]
        if args.virtual:
            smoke_args.append("--virtual")
        return live_smoke(smoke_args)
    from animecam.app import main as launch
    return launch(app_args, ui_smoke=args.ui_smoke, screenshot=args.screenshot)


if __name__ == "__main__":
    sys.exit(main())
