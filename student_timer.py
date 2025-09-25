"""Student study/break timer planner and runner."""
import argparse
import datetime as _dt
import sys
import time
from dataclasses import dataclass
from typing import Iterable, List


@dataclass
class ScheduleBlock:
    """Represents a single block in a study schedule."""

    label: str
    duration_minutes: float
    kind: str  # "study", "break", or "long_break"
    start: _dt.datetime
    end: _dt.datetime

    @property
    def summary(self) -> str:
        return f"{self.label}: {self.duration_minutes:.0f} min ({self.start:%H:%M} - {self.end:%H:%M})"


class RecommendationEngine:
    """Determine study/break durations given qualitative inputs."""

    def __init__(self) -> None:
        # Baseline durations in minutes based on common Pomodoro-style guidance.
        self._base_study = 25
        self._base_break = 5

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    def recommend_durations(
        self,
        energy: int,
        focus: int,
        urgency: int,
        session_length: int,
    ) -> dict:
        """Return a dictionary with recommended durations.

        Parameters are provided on a 1-5 scale (low-high). The heuristics combine
        energy (stamina), focus (mental clarity) and urgency (deadline pressure)
        to balance deep work with rest.
        """

        # Adjustments in minutes relative to the baseline values.
        study_adjust = (focus - 3) * 4 + (energy - 3) * 3 + (urgency - 3) * 2
        study_length = self._base_study + study_adjust
        study_length = self._clamp(round(study_length / 5) * 5, 15, 60)

        break_adjust = (3 - focus) * 2 + (3 - energy) * 2 - (urgency - 3) * 1
        break_length = self._base_break + break_adjust
        break_length = self._clamp(round(break_length), 3, 15)

        # Long breaks offer a reset; higher urgency and higher energy reduce the
        # need for very long breaks while lower energy increases it.
        long_break = 15 + (2 - min(energy, 3)) * 5
        long_break = self._clamp(long_break - (urgency - 3) * 2, 10, 30)

        # Determine how often a long break should appear.
        long_break_interval = 4
        if energy <= 2:
            long_break_interval = 3
        elif focus >= 4 and urgency >= 4:
            long_break_interval = 5

        cycle_length = study_length + break_length
        cycles = max(1, round(session_length / cycle_length))
        cycles = int(self._clamp(cycles, 1, 8))

        return {
            "study": int(study_length),
            "short_break": int(break_length),
            "long_break": int(long_break),
            "long_break_interval": long_break_interval,
            "cycles": cycles,
        }


def build_schedule(
    start_time: _dt.datetime,
    total_minutes: int,
    durations: dict,
) -> List[ScheduleBlock]:
    """Build a schedule of study/break blocks that fits within the total time."""

    schedule: List[ScheduleBlock] = []
    current = start_time
    study_duration = durations["study"]
    short_break = durations["short_break"]
    long_break = durations["long_break"]
    long_interval = durations["long_break_interval"]

    total_used = 0
    cycle = 0

    while total_used < total_minutes:
        cycle += 1
        study_minutes = min(study_duration, total_minutes - total_used)
        study_end = current + _dt.timedelta(minutes=study_minutes)
        schedule.append(
            ScheduleBlock(
                label=f"Cycle {cycle} — Study",
                duration_minutes=study_minutes,
                kind="study",
                start=current,
                end=study_end,
            )
        )
        current = study_end
        total_used += study_minutes

        if total_used >= total_minutes:
            break

        # Decide on break type.
        if cycle % long_interval == 0:
            break_minutes = min(long_break, total_minutes - total_used)
            break_kind = "long_break"
            break_label = "Long break"
        else:
            break_minutes = min(short_break, total_minutes - total_used)
            break_kind = "break"
            break_label = "Short break"

        break_end = current + _dt.timedelta(minutes=break_minutes)
        schedule.append(
            ScheduleBlock(
                label=f"Cycle {cycle} — {break_label}",
                duration_minutes=break_minutes,
                kind=break_kind,
                start=current,
                end=break_end,
            )
        )
        current = break_end
        total_used += break_minutes

    return schedule


def print_schedule(schedule: Iterable[ScheduleBlock]) -> None:
    total_study = sum(block.duration_minutes for block in schedule if block.kind == "study")
    total_break = sum(block.duration_minutes for block in schedule if block.kind != "study")

    print("\nRecommended plan:")
    for block in schedule:
        block_type = "Study" if block.kind == "study" else ("Long break" if block.kind == "long_break" else "Break")
        print(f" - {block.summary} [{block_type}]")

    print("\nTotals:")
    print(f" * Study time: {total_study:.0f} minutes")
    print(f" * Break time: {total_break:.0f} minutes")


def run_timer(schedule: Iterable[ScheduleBlock], time_scale: int) -> None:
    print("\nStarting timer. Press Ctrl+C to stop.\n")
    try:
        for block in schedule:
            if block.duration_minutes <= 0:
                continue
            minutes_remaining = int(round(block.duration_minutes))
            block_label = block.label
            print(f"{block_label}")
            for minute in range(minutes_remaining, 0, -1):
                if minute == minutes_remaining:
                    status = "Starting"
                else:
                    status = "Remaining"
                print(f"  {status}: {minute} minute(s)")
                time.sleep(time_scale)
            print("  Done!\n")
    except KeyboardInterrupt:
        print("\nTimer interrupted by user.\n")


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan and run an optimized study/break timer for students.",
    )
    parser.add_argument("--total-minutes", type=int, default=180, help="Total session length in minutes (default: 180).")
    parser.add_argument("--energy", type=int, choices=range(1, 6), default=3, help="Energy level (1-5).")
    parser.add_argument("--focus", type=int, choices=range(1, 6), default=3, help="Focus level (1-5).")
    parser.add_argument("--urgency", type=int, choices=range(1, 6), default=3, help="Deadline urgency (1-5).")
    parser.add_argument("--start", type=str, default=None, help="Optional start time HH:MM (24h). Defaults to now.")
    parser.add_argument("--time-scale", type=int, default=60, help="Seconds that represent one scheduled minute when running the timer (default: 60).")
    parser.add_argument("--run", action="store_true", help="Run the live timer after displaying the plan.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.total_minutes <= 0:
        raise SystemExit("total-minutes must be positive")

    if args.start:
        try:
            start_time = _dt.datetime.combine(
                _dt.date.today(),
                _dt.datetime.strptime(args.start, "%H:%M").time(),
            )
        except ValueError as exc:
            raise SystemExit(f"Invalid --start time: {exc}") from exc
    else:
        start_time = _dt.datetime.now()

    engine = RecommendationEngine()
    durations = engine.recommend_durations(
        energy=args.energy,
        focus=args.focus,
        urgency=args.urgency,
        session_length=args.total_minutes,
    )

    schedule = build_schedule(start_time, args.total_minutes, durations)

    print("Input summary:")
    print(f" - Total minutes: {args.total_minutes}")
    print(f" - Energy: {args.energy}")
    print(f" - Focus: {args.focus}")
    print(f" - Urgency: {args.urgency}")
    print("\nRecommended durations:")
    print(f" - Study blocks: {durations['study']} minutes")
    print(f" - Short breaks: {durations['short_break']} minutes")
    print(f" - Long breaks: {durations['long_break']} minutes (every {durations['long_break_interval']} cycle(s))")

    print_schedule(schedule)

    if args.run:
        run_timer(schedule, max(1, args.time_scale))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
