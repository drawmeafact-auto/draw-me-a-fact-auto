# QA — EP 11 mountains-10km-limit

| Check | Result | Detail |
|---|---|---|
| 1. Duration ≤ 45 s | **PASS** | 44.10 s |
| 2a. Video 1080x1920 | **PASS** | 1080x1920 h264 |
| 2b. 30 fps | **PASS** | 30.000 fps |
| 2c. Audio aac mono 44.1 kHz | **PASS** | aac 44100 Hz ch=1 |
| 3. Contact sheet frames | **PASS** | 6/6 frames captured |
| 4. Voice at every cue | **PASS** | min RMS 0.338 > 0.1 · cues [0.3431, 0.3383, 0.3477, 0.3415, 0.3451] |
| 5. Digits in spoken script | **PASS** | all numbers spoken as words |
| 6. Safe area contract | **PASS** | x 132–948, y 176–1692 (bottom 220 px / top 160 px clear) |
| 7. Shorts UI overlays clear | **PASS** | bottom 220 px and top 160 px kept empty by layout |
