# Third-party components

AnimeCam FX's visual effects are generated procedurally; no anime images, logos or film clips are bundled.
Version 0.1.3 removes the previously generated sound and uses the short Goku Instant Transmission recording downloaded from https://soundsverse.com/dragon-ball-z/goku/goku-instant-transmission .
The source publisher describes that download as free and royalty free. This records the publisher's statement, not an independent verification of ownership or a transfer of original franchise/audio rights. See assets/sound-source.json for the exact source, download URL and SHA256. No audio was extracted from the user's reference video. Review original rights before public redistribution; users can select a replacement audio file in the app.

Dependencies retain their own licenses. Consult the actual LICENSE/COPYING files shipped with each installed wheel before redistribution:

| Component | Upstream |
|---|---|
| MediaPipe code/models | https://github.com/google-ai-edge/mediapipe (Apache-2.0 code; consult each model card/metadata for model terms) |
| Hand model | https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker#models |
| Face model | https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker#models |
| Selfie segmentation model | https://developers.google.com/edge/mediapipe/solutions/vision/image_segmenter#models |
| OpenCV | https://opencv.org/license/ |
| NumPy | https://numpy.org/doc/stable/license.html |
| PySide6/Qt | https://doc.qt.io/qtforpython-6/licenses.html (LGPL/GPL/commercial options) |
| PyVirtualCam | https://github.com/letmaik/pyvirtualcam (GPL-2.0) |
| syphon-python (macOS) | https://github.com/cansik/syphon-python (MIT); bundles Syphon.framework (BSD-style) |
| python-sounddevice / PortAudio | https://python-sounddevice.readthedocs.io/ and https://www.portaudio.com/ |
| SoundFile / libsndfile | https://python-soundfile.readthedocs.io/ and https://libsndfile.github.io/libsndfile/ |
| OBS Studio, installed separately | https://github.com/obsproject/obs-studio |
| NSIS installer compiler, build tool only | https://nsis.sourceforge.io/ |

The PyInstaller folder is a technical build artifact, not a complete license-compliance distribution. Include applicable license texts/source obligations when distributing a release. No OBS driver is bundled or installed automatically.
