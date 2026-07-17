# Demo recording pack

Generated from a **real** `kp demo` run on this machine.

## Video

- [`known-path-demo.mp4`](known-path-demo.mp4) — ~37s slide + live capture (1280×720, H.264)

## What the video shows

1. Problem (wrong table / thrash)
2. Baseline metrics (trap `finance.revenue_old`)
3. Known-path shortlist (canonical + dim.region)
4. Fail-closed BLOCKED_TRUST
5. Metrics table
6. **Live capture HTML** from real run JSON/SQL/write-back
7. What judges need / repo link

## Raw evidence

| File | Content |
|------|---------|
| `00-doctor.txt` | `kp doctor` |
| `01-cli-demo-full.txt` | Full `kp demo` transcript |
| `02-artifacts.txt` | examples/ listing |
| `baseline_wrong.sql` | Wrong-table SQL |
| `revenue_by_region.sql` | Correct SQL |
| `writeback_route_note.md` | Route note |
| `live-capture.html` | HTML report of the same run |
| `frames/` | PNG slides + screenshot |

## How to re-record

```bash
cd known-path
export PYTHONPATH=src
python -m known_path.cli demo | tee docs/demo-recording/01-cli-demo-full.txt
# rebuild slides/video with scripts or the commands used in CI notes
```

## YouTube / Devpost

Upload `known-path-demo.mp4` to YouTube or Vimeo (public), then paste the link on the Devpost submission form.  
Optional: re-record with face/voice on top of this cut for a more personal 3-minute video.
