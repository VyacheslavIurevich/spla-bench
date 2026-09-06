"""
CPU profiler implementation using perf
"""

import os
import subprocess
import re
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional

from profiler_base import Profiler, ProfileResult


class CPUProfiler(Profiler):
    """CPU profiler using perf tool"""

    def __init__(self, output_dir: Path, perf_path: str = "perf"):
        super().__init__(output_dir)
        self.perf_path = shutil.which(perf_path) if perf_path == "perf" else perf_path
        self.is_available_flag = self.check_availability()

    def check_availability(self) -> bool:
        """Check if perf is available"""
        return self.perf_path is not None

    def is_available(self) -> bool:
        return self.is_available_flag

    def setup(self) -> bool:
        """Setup profiler"""
        if not self.is_available():
            print(f"CPU profiler (perf) not found at {self.perf_path}")
            return False
        return True

    def _output_base(self, prefix: str, metadata: Dict[str, Any]) -> Path:
        parts = [
            prefix,
            metadata.get("tool"),
            metadata.get("algo"),
            metadata.get("dataset"),
        ]
        if metadata.get("run_index") is not None:
            parts.append(f"run{metadata['run_index']}")
        filename = "_".join(str(part).replace("/", "_") for part in parts if part)
        return self.get_output_file(filename)

    def profile_callgraph(
        self, command: List[str], metadata: Dict[str, Any]
    ) -> ProfileResult:
        """Profile with CPU callgraph"""
        output_file = self._output_base("callgraph", metadata)
        perf_file = output_file.with_suffix(".perf")

        print(f"Running callgraph profiling: {' '.join(command)}")

        try:
            process = subprocess.run(
                [
                    self.perf_path,
                    "record",
                    "-g",
                    "--call-graph=dwarf",
                    "-F",
                    "999",
                    "-o",
                    str(perf_file),
                ]
                + command,
                check=True,
                capture_output=True,
                text=True,
            )

            result = ProfileResult(
                cpu_callgraph=perf_file,
                raw_output=(
                    (process.stdout or "")
                    + "\n"
                    + (process.stderr or "")
                ),
                metadata=metadata,
            )
            return result

        except subprocess.CalledProcessError as e:
            print(f"Callgraph profiling failed: {e}")
            print(f"STDOUT: {e.stdout}")
            print(f"STDERR: {e.stderr}")
            return ProfileResult(metadata=metadata)

    def profile_hardware_counters(
        self, command: List[str], runs: int, metadata: Dict[str, Any]
    ) -> ProfileResult:
        """Profile with hardware counters"""
        print(f"Running hardware counters profiling: {' '.join(command)}")

        counters = [
            "cycles",
            "instructions",
            "cache-references",
            "cache-misses",
            "LLC-loads",
            "LLC-load-misses",
            "branch-misses",
            "branch-instructions",
        ]

        try:
            output_file = self._output_base("counters", metadata)
            env = os.environ.copy()
            env["LC_ALL"] = "C"

            with open(output_file.with_suffix(".txt"), "w") as f:
                process = subprocess.run(
                    [
                        self.perf_path,
                        "stat",
                        "-x",
                        ",",
                        "-e",
                        ",".join(counters),
                        "-r",
                        "1",
                    ]
                    + command,
                    capture_output=True,
                    text=True,
                    env=env,
                )
                f.write(process.stderr)

            counters_data = self.parse_perf_stat(process.stderr)

            result = ProfileResult(
                cpu_hardware_counters=counters_data, metadata=metadata
            )
            result.add_metric("cpu.benchmark_iterations", [runs], "runs")
            for counter, value in counters_data.items():
                if isinstance(value, (int, float)):
                    result.add_metric(f"cpu.{counter}.process", [value], "events")
                    if runs > 0:
                        result.add_metric(
                            f"cpu.{counter}.per_iteration", [value / runs], "events"
                        )
            return result

        except subprocess.CalledProcessError as e:
            print(f"Hardware counters profiling failed: {e}")
            return ProfileResult(metadata=metadata)

    def profile(self, command: List[str], metadata: Dict[str, Any]) -> ProfileResult:
        """Run CPU profiling"""
        callgraph_result = self.profile_callgraph(command, metadata)

        runs = metadata.get("runs", 5)
        counters_result = self.profile_hardware_counters(command, runs, metadata)

        result = ProfileResult(
            cpu_callgraph=callgraph_result.cpu_callgraph,
            cpu_hardware_counters=counters_result.cpu_hardware_counters,
            raw_output=callgraph_result.raw_output,
            metadata=metadata,
        )
        result.merge_metrics_from(counters_result)
        return result

    def parse_results(self, raw_output: bytes) -> Dict[str, Any]:
        """Parse profiling results"""
        return {}

    def cleanup(self) -> None:
        """Cleanup profiler resources"""
        pass

    def parse_perf_stat(self, output: str) -> Dict[str, Any]:
        """Parse perf stat output"""
        counters = {}

        event_names = {
            "cycles": "cycles",
            "instructions": "instructions",
            "cache-references": "cache_references",
            "cache-misses": "cache_misses",
            "LLC-loads": "llc_loads",
            "LLC-load-misses": "llc_load_misses",
            "branch-misses": "branch_misses",
            "branch-instructions": "branch_instructions",
        }

        for line in output.splitlines():
            parts = line.split(",")
            if len(parts) >= 3:
                value = self._parse_number(parts[0])
                event = parts[2].strip()
                if value is not None and event in event_names:
                    counters[event_names[event]] = value

        if counters:
            return counters

        for event, key in event_names.items():
            pattern = rf"([\d\s,\.\u202f\xa0]+)\s+{re.escape(event)}"
            match = re.search(pattern, output)
            if match:
                value = self._parse_number(match.group(1))
                if value is not None:
                    counters[key] = value

        return counters

    def _parse_number(self, value: str) -> Optional[float]:
        normalized = (
            value.strip()
            .replace("\u202f", "")
            .replace("\xa0", "")
            .replace(" ", "")
        )
        if not normalized or normalized.startswith("<not"):
            return None
        if normalized.count(",") == 1 and "." not in normalized:
            normalized = normalized.replace(",", ".")
        else:
            normalized = normalized.replace(",", "")
        try:
            parsed = float(normalized)
        except ValueError:
            return None
        return int(parsed) if parsed.is_integer() else parsed

    def generate_report(self, perf_file: Path) -> str:
        """Generate human-readable report from perf data"""
        try:
            result = subprocess.run(
                [
                    self.perf_path,
                    "report",
                    "--stdio",
                    "--no-children",
                    "-i",
                    str(perf_file),
                ],
                capture_output=True,
                text=True,
            )
            return result.stdout
        except subprocess.CalledProcessError:
            return ""
