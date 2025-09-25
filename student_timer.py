"""Student study/break timer planner and runner."""
import argparse
import datetime as _dt
import sys
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional


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


class TimerApp:
    """Simple Tkinter UI for planning and running the study timer."""

    def __init__(self, root, tk, ttk, messagebox) -> None:  # pragma: no cover - GUI wiring
        self.root = root
        self._tk = tk
        self._ttk = ttk
        self._messagebox = messagebox
        self.engine = RecommendationEngine()
        self.schedule: List[ScheduleBlock] = []
        self._timer_id: Optional[str] = None
        self._current_index = 0
        self._minutes_left = 0
        self._block_total = 0
        self._time_scale = 60
        self._active_block: Optional[ScheduleBlock] = None

        self._build_ui()

    def _build_ui(self) -> None:
        root = self.root
        root.title("Study Timer Planner")
        root.geometry("620x520")
        root.minsize(520, 420)

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        main = self._ttk.Frame(root, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(1, weight=1)
        main.rowconfigure(6, weight=1)

        # Inputs
        self.total_minutes_var = self._tk.StringVar(value="180")
        self.energy_var = self._tk.IntVar(value=3)
        self.focus_var = self._tk.IntVar(value=3)
        self.urgency_var = self._tk.IntVar(value=3)
        self.start_var = self._tk.StringVar(value="")
        self.time_scale_var = self._tk.IntVar(value=60)

        self._ttk.Label(main, text="Total minutes:").grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.total_entry = self._ttk.Spinbox(main, from_=15, to=480, increment=5, textvariable=self.total_minutes_var, width=8)
        self.total_entry.grid(row=0, column=1, sticky="w", pady=(0, 4))

        self._ttk.Label(main, text="Energy (1-5):").grid(row=1, column=0, sticky="w", pady=(0, 4))
        self.energy_spin = self._ttk.Spinbox(main, from_=1, to=5, textvariable=self.energy_var, width=8)
        self.energy_spin.grid(row=1, column=1, sticky="w", pady=(0, 4))

        self._ttk.Label(main, text="Focus (1-5):").grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.focus_spin = self._ttk.Spinbox(main, from_=1, to=5, textvariable=self.focus_var, width=8)
        self.focus_spin.grid(row=2, column=1, sticky="w", pady=(0, 4))

        self._ttk.Label(main, text="Urgency (1-5):").grid(row=3, column=0, sticky="w", pady=(0, 4))
        self.urgency_spin = self._ttk.Spinbox(main, from_=1, to=5, textvariable=self.urgency_var, width=8)
        self.urgency_spin.grid(row=3, column=1, sticky="w", pady=(0, 4))

        self._ttk.Label(main, text="Start time (HH:MM, optional):").grid(row=4, column=0, sticky="w", pady=(0, 4))
        self.start_entry = self._ttk.Entry(main, textvariable=self.start_var, width=12)
        self.start_entry.grid(row=4, column=1, sticky="w", pady=(0, 4))

        self._ttk.Label(main, text="Seconds per minute (timer speed):").grid(row=5, column=0, sticky="w", pady=(0, 4))
        self.time_scale_spin = self._ttk.Spinbox(main, from_=1, to=120, textvariable=self.time_scale_var, width=8)
        self.time_scale_spin.grid(row=5, column=1, sticky="w", pady=(0, 8))

        button_frame = self._ttk.Frame(main)
        button_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)

        self.generate_button = self._ttk.Button(button_frame, text="Generate Plan", command=self.generate_plan)
        self.generate_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.run_button = self._ttk.Button(button_frame, text="Run Timer", command=self.start_timer, state="disabled")
        self.run_button.grid(row=0, column=1, sticky="ew", padx=4)

        self.stop_button = self._ttk.Button(button_frame, text="Stop", command=self.stop_timer, state="disabled")
        self.stop_button.grid(row=0, column=2, sticky="ew", padx=(4, 0))

        # Output
        output_frame = self._ttk.LabelFrame(main, text="Plan")
        output_frame.grid(row=7, column=0, columnspan=2, sticky="nsew")
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)

        self.output = self._tk.Text(output_frame, height=14, wrap="word", state="disabled")
        self.output.grid(row=0, column=0, sticky="nsew")

        scroll = self._ttk.Scrollbar(output_frame, command=self.output.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.output.configure(yscrollcommand=scroll.set)

        self.status_var = self._tk.StringVar(value="Fill in your details and click Generate Plan.")
        self.status_label = self._ttk.Label(main, textvariable=self.status_var, wraplength=560)
        self.status_label.grid(row=8, column=0, columnspan=2, sticky="we", pady=(8, 0))

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        self.stop_timer()
        self.root.destroy()

    def _parse_start_time(self) -> _dt.datetime:
        text = self.start_var.get().strip()
        if not text:
            return _dt.datetime.now()
        try:
            parsed = _dt.datetime.strptime(text, "%H:%M").time()
        except ValueError as exc:  # pragma: no cover - GUI validation
            self._messagebox.showerror("Invalid time", f"Could not parse start time: {exc}")
            raise
        return _dt.datetime.combine(_dt.date.today(), parsed)

    def generate_plan(self) -> None:  # pragma: no cover - GUI wiring
        try:
            total_minutes = int(self.total_minutes_var.get())
        except ValueError:
            self._messagebox.showerror("Invalid input", "Total minutes must be a number.")
            return
        if total_minutes <= 0:
            self._messagebox.showerror("Invalid input", "Total minutes must be positive.")
            return

        try:
            start_time = self._parse_start_time()
        except ValueError:
            return

        try:
            energy = int(self.energy_var.get())
            focus = int(self.focus_var.get())
            urgency = int(self.urgency_var.get())
        except ValueError:
            self._messagebox.showerror("Invalid input", "Energy, focus, and urgency must be numbers between 1 and 5.")
            return

        if not all(1 <= value <= 5 for value in (energy, focus, urgency)):
            self._messagebox.showerror("Invalid input", "Energy, focus, and urgency must be between 1 and 5.")
            return

        durations = self.engine.recommend_durations(energy, focus, urgency, total_minutes)
        self.schedule = build_schedule(start_time, total_minutes, durations)
        self._display_plan(durations)

        self.status_var.set("Plan ready! Click Run Timer to start the countdown or adjust the inputs.")
        self.run_button.configure(state="normal")

    def _display_plan(self, durations: dict) -> None:
        output_lines = [
            "Input summary:",
            f" - Total minutes: {sum(block.duration_minutes for block in self.schedule):.0f}",
            f" - Energy: {self.energy_var.get()}",
            f" - Focus: {self.focus_var.get()}",
            f" - Urgency: {self.urgency_var.get()}",
            "",
            "Recommended durations:",
            f" - Study blocks: {durations['study']} minutes",
            f" - Short breaks: {durations['short_break']} minutes",
            f" - Long breaks: {durations['long_break']} minutes (every {durations['long_break_interval']} cycle(s))",
            "",
            "Plan:",
        ]

        for block in self.schedule:
            block_type = "Study" if block.kind == "study" else ("Long break" if block.kind == "long_break" else "Break")
            output_lines.append(f" - {block.summary} [{block_type}]")

        total_study = sum(block.duration_minutes for block in self.schedule if block.kind == "study")
        total_break = sum(block.duration_minutes for block in self.schedule if block.kind != "study")
        output_lines.extend(
            [
                "",
                "Totals:",
                f" * Study time: {total_study:.0f} minutes",
                f" * Break time: {total_break:.0f} minutes",
            ]
        )

        self.output.configure(state="normal")
        self.output.delete("1.0", self._tk.END)
        self.output.insert(self._tk.END, "\n".join(output_lines))
        self.output.configure(state="disabled")

    def start_timer(self) -> None:  # pragma: no cover - GUI wiring
        if not self.schedule:
            self._messagebox.showwarning("No plan", "Generate a plan before running the timer.")
            return

        try:
            self._time_scale = max(1, int(self.time_scale_var.get()))
        except ValueError:
            self._messagebox.showerror("Invalid input", "Time scale must be a whole number of seconds.")
            return

        self.run_button.configure(state="disabled")
        self.generate_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self._current_index = 0
        self._run_next_block()

    def stop_timer(self, *, message: Optional[str] = None) -> None:  # pragma: no cover - GUI wiring
        if self._timer_id is not None:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None
        if message is None:
            message = "Timer stopped. Adjust inputs or run again when ready."
        self.status_var.set(message)
        self._active_block = None
        self.generate_button.configure(state="normal")
        self.run_button.configure(state="normal" if self.schedule else "disabled")
        self.stop_button.configure(state="disabled")

    def _run_next_block(self) -> None:
        if self._timer_id is not None:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None

        while self._current_index < len(self.schedule):
            block = self.schedule[self._current_index]
            minutes = int(round(block.duration_minutes))
            if minutes <= 0:
                self._current_index += 1
                continue

            self._active_block = block
            self._minutes_left = minutes
            self._block_total = minutes
            self.status_var.set(f"{block.label} — starting")
            self._timer_id = self.root.after(10, self._tick)
            return

        self.stop_timer(message="All scheduled blocks are complete! Great job.")

    def _tick(self) -> None:
        if self._active_block is None:
            return

        if self._minutes_left <= 0:
            self.status_var.set(f"{self._active_block.label} — done!")
            self._current_index += 1
            self._timer_id = self.root.after(600, self._run_next_block)
            return

        remaining = self._minutes_left
        status = "Starting" if remaining == self._block_total else "Remaining"
        self.status_var.set(f"{self._active_block.label} — {status}: {remaining} minute(s)")
        self._minutes_left -= 1
        self._timer_id = self.root.after(self._time_scale * 1000, self._tick)


def launch_gui() -> None:  # pragma: no cover - GUI wiring
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise SystemExit("Tkinter is required for the GUI but is not available in this environment.") from exc

    root = tk.Tk()
    TimerApp(root, tk, ttk, messagebox)
    root.mainloop()


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
    parser.add_argument("--gui", action="store_true", help="Launch the graphical timer planner.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.gui:
        launch_gui()
        return 0

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
