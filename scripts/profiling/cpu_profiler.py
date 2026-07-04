"""
CPU profiler implementation using perf
"""

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

    def profile_callgraph(
        self, command: List[str], metadata: Dict[str, Any]
    ) -> ProfileResult:
        """Profile with CPU callgraph"""
        output_file = self.get_output_file(
            f"callgraph_{metadata.get('tool')}_{metadata.get('algo')}"
        )
        perf_file = output_file.with_suffix(".perf")

        print(f"Running callgraph profiling: {' '.join(command)}")

        try:
            subprocess.run(
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

            result = ProfileResult(cpu_callgraph=perf_file, metadata=metadata)
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
            output_file = self.get_output_file(
                f"counters_{metadata.get('tool')}_{metadata.get('algo')}"
            )

            with open(output_file.with_suffix(".txt"), "w") as f:
                process = subprocess.run(
                    [self.perf_path, "stat", "-e", ",".join(counters), "-r", str(runs)]
                    + command,
                    capture_output=True,
                    text=True,
                )
                f.write(process.stderr)

            counters_data = self.parse_perf_stat(process.stderr)

            result = ProfileResult(
                cpu_hardware_counters=counters_data, metadata=metadata
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
            metadata=metadata,
        )
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

        patterns = {
            "cycles": r"(\d+(?:,\d+)*)\s+cycles",
            "instructions": r"(\d+(?:,\d+)*)\s+instructions",
            "cache_references": r"(\d+(?:,\d+)*)\s+cache-references",
            "cache_misses": r"(\d+(?:,\d+)*)\s+cache-misses",
            "llc_loads": r"(\d+(?:,\d+)*)\s+LLC-loads",
            "llc_load_misses": r"(\d+(?:,\d+)*)\s+LLC-load-misses",
            "branch_misses": r"(\d+(?:,\d+)*)\s+branch-misses",
            "branch_instructions": r"(\d+(?:,\d+)*)\s+branch-instructions",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, output)
            if match:
                value = match.group(1).replace(",", "")
                try:
                    counters[key] = int(value)
                except ValueError:
                    counters[key] = value

        return counters

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
