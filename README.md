# Student Study Timer

This repository contains a command line planner that recommends study and break blocks based on your current energy, focus, and urgency levels. You can also run an optional live countdown timer for each block.

## Requirements

- Python 3.9 or newer (standard library only)

## Quick start

Plan a 2-hour session starting now using mid-level energy/focus/urgency:

```bash
python student_timer.py --total-minutes 120 --energy 3 --focus 3 --urgency 3
```

The script prints a recommended schedule, including when to study and when to take breaks.

## Watching the timer

To see the timer run, add `--run`. You can use `--time-scale 1` so that each planned minute elapses in one real second—handy for a quick demonstration.

```bash
python student_timer.py --total-minutes 30 --energy 4 --focus 4 --urgency 3 --run --time-scale 1
```

This example creates roughly 25-minute study blocks with short breaks and shows a live countdown for each block. Press `Ctrl+C` to stop the timer early.

## Customization tips

- `--start` accepts a `HH:MM` start time (24-hour clock). If omitted, the current time is used.
- Try lower energy/focus values if you need more frequent breaks, or raise urgency to lean into longer study blocks.
- The planner keeps the schedule within your requested total minutes. Long breaks appear every few cycles depending on your inputs.

## Development

Run a quick bytecode compilation check:

```bash
python -m compileall student_timer.py
```

Generate a sample schedule and timer run (scaled down for speed):

```bash
python student_timer.py --total-minutes 45 --energy 3 --focus 4 --urgency 4 --time-scale 1 --run
```
