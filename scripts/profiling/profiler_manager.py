"""
Profiling manager for coordinating different profiling tools
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, TYPE_CHECKING
import importlib.util

# Add parent directory to path for config import
sys.path.append(str(Path(__file__).parent.parent))

# Explicitly import config from file to avoid package conflicts
if TYPE_CHECKING:
    from config import ProfilingConfig, PROFILING_OUTPUT
else:
    config_spec = importlib.util.spec_from_file_location(
        "spla_bench_config", str(Path(__file__).parent.parent / "config.py")
    )
    config = importlib.util.module_from_spec(config_spec)
    config_spec.loader.exec_module(config)
    ProfilingConfig = config.ProfilingConfig
    PROFILING_OUTPUT = config.PROFILING_OUTPUT

# Add current directory for profiling imports
sys.path.insert(0, str(Path(__file__).parent))

from profiler_base import Profiler, ProfileResult
from cpu_profiler import CPUProfiler
from gpu_profiler import GPUProfiler
from flamegraph import FlamegraphGenerator


class ProfilerManager:
    """Manager for coordinating profiling across different tools and algorithms"""

    def __init__(
        self,
        profiling_config: ProfilingConfig,
        output_dir: Optional[Path] = None,
    ):
        self.config = profiling_config
        self.output_dir = output_dir or config.PROFILING_OUTPUT
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.cpu_profiler: Optional[CPUProfiler] = None
        self.gpu_profiler: Optional[GPUProfiler] = None
        self.flamegraph_generator: Optional[FlamegraphGenerator] = None

        self._setup_profilers()

    def _setup_profilers(self):
        """Setup available profilers based on configuration"""
        if self.config.cpu_profiling:
            self.cpu_profiler = CPUProfiler(self.output_dir / "cpu")
            if not self.cpu_profiler.setup():
                print("CPU profiler setup failed, disabling CPU profiling")
                self.cpu_profiler = None
                self.config.cpu_profiling = False

        if self.config.gpu_profiling:
            # GPU profiler now includes Intel GPU support
            self.gpu_profiler = GPUProfiler(self.output_dir / "gpu")
            if not self.gpu_profiler.setup():
                print("GPU profiler setup failed, disabling GPU profiling")
                self.gpu_profiler = None
                self.config.gpu_profiling = False

        if self.config.flamegraph:
            self.flamegraph_generator = FlamegraphGenerator()
            if not self.flamegraph_generator.is_available():
                print("Flamegraph generator setup failed, disabling flamegraph")
                self.flamegraph_generator = None
                self.config.flamegraph = False

    def run_profiling(
        self,
        command: List[str],
        tool: Any,
        dataset: Any,
        algo: Any,
        runs: int = 1,
    ) -> ProfileResult:
        """Run profiling with appropriate profilers for tool"""

        metadata = {
            "tool": str(tool),
            "algo": str(algo),
            "dataset": dataset.name,
            "runs": runs,
        }

        profiling_result = ProfileResult(metadata=metadata)
        profiled_processes = 0
        profile_passes = []

        if (
            self.config.hardware_counters
            and self.cpu_profiler
        ):
            print(f"Running CPU hardware counters for {tool} {algo}")
            cpu_result = self.cpu_profiler.profile_hardware_counters(
                command, runs, metadata
            )
            profiling_result.cpu_hardware_counters = cpu_result.cpu_hardware_counters
            profiling_result.cpu_hardware_counters_file = (
                cpu_result.cpu_hardware_counters_file
            )
            profiling_result.raw_output = cpu_result.raw_output
            profiling_result.merge_metrics_from(cpu_result)
            profiling_result.metadata["hardware_counters"] = (
                "collected_in_separate_perf_stat_pass"
                if cpu_result.cpu_hardware_counters
                else "separate_perf_stat_pass_failed"
            )
            profiling_result.metadata["hardware_counter_profiled_processes"] = 1
            profiled_processes += 1
            profile_passes.append("cpu_hardware_counters")

        if (
            self.config.gpu_profiling
            and self.gpu_profiler
            and self.supports_gpu_profiling(tool)
        ):
            print(f"Running GPU profiling for {tool} {algo}")
            gpu_result = self.gpu_profiler.profile(command, metadata)
            profiling_result.gpu_timeline = gpu_result.gpu_timeline
            profiling_result.gpu_timing = gpu_result.gpu_timing
            profiling_result.gpu_memory = gpu_result.gpu_memory
            profiling_result.raw_output = (
                profiling_result.raw_output or gpu_result.raw_output
            )
            profiling_result.merge_metrics_from(gpu_result)
            profiling_result.metadata.update(gpu_result.metadata)
            profiling_result.metadata["gpu_profile"] = (
                "collected"
                if gpu_result.gpu_timeline or gpu_result.numeric_metrics
                else "failed"
            )
            profiling_result.metadata["gpu_profiled_processes"] = 1
            profiled_processes += 1
            profile_passes.append("gpu")

        profiling_result.metadata["profiled_processes"] = profiled_processes
        profiling_result.metadata["profile_passes"] = profile_passes
        profiling_result.metadata["profile_pass_count"] = len(profile_passes)

        return profiling_result

    def profiles_individual_flamegraph_runs(self) -> bool:
        """Whether each configured run must get its own callgraph candidate."""
        return bool(
            self.config.flamegraph
            and self.cpu_profiler
            and self.flamegraph_generator
        )

    def collects_hardware_counters(self) -> bool:
        """Whether a separate perf stat pass was explicitly requested."""
        return bool(self.config.hardware_counters and self.cpu_profiler)

    def supports_gpu_profiling(self, tool: Any) -> bool:
        """Whether GPU profiling is implemented for this tool."""
        return str(tool) not in ["gunrock", "graphblast"]

    def collects_gpu_metrics(self, tool: Any) -> bool:
        """Whether a separate GPU profiling pass was requested."""
        return bool(
            self.config.gpu_profiling
            and self.gpu_profiler
            and self.supports_gpu_profiling(tool)
        )

    def run_flamegraph_candidate(
        self,
        command: List[str],
        tool: Any,
        dataset: Any,
        algo: Any,
        run_index: int,
    ) -> ProfileResult:
        """Profile one benchmark run without creating an intermediate flamegraph."""
        metadata = {
            "tool": str(tool),
            "algo": str(algo),
            "dataset": dataset.name,
            "runs": 1,
            "run_index": run_index,
        }
        print(
            f"Profiling flamegraph candidate {run_index}: "
            f"{tool} {algo} {dataset.name}"
        )
        return self.cpu_profiler.profile_callgraph(command, metadata)

    def run_hardware_counters(
        self,
        command: List[str],
        tool: Any,
        dataset: Any,
        algo: Any,
        runs: int,
    ) -> Optional[ProfileResult]:
        """Run a separate perf stat pass when CPU metrics were requested."""
        if (
            not self.config.hardware_counters
            or not self.cpu_profiler
        ):
            return None

        metadata = {
            "tool": str(tool),
            "algo": str(algo),
            "dataset": dataset.name,
            "runs": runs,
            "profile_pass": "hardware_counters",
        }
        print(f"Running separate hardware counters pass for {tool} {algo}")
        return self.cpu_profiler.profile_hardware_counters(
            command, runs, metadata
        )

    def run_gpu_profile(
        self,
        command: List[str],
        tool: Any,
        dataset: Any,
        algo: Any,
        runs: int,
    ) -> Optional[ProfileResult]:
        """Run the explicitly requested GPU profiling pass."""
        if not self.collects_gpu_metrics(tool):
            return None

        metadata = {
            "tool": str(tool),
            "algo": str(algo),
            "dataset": dataset.name,
            "runs": runs,
            "profile_pass": "gpu",
        }
        print(f"Running separate GPU profiling pass for {tool} {algo}")
        return self.gpu_profiler.profile(command, metadata)

    def finalize_flamegraph_candidates(
        self,
        candidates: List[ProfileResult],
        selected_index: Optional[int],
        tool: Any,
        dataset: Any,
        algo: Any,
        configured_runs: int,
    ) -> ProfileResult:
        """Render only the median-nearest candidate, if timing was parsed."""
        selected = candidates[selected_index if selected_index is not None else 0]

        selected.metadata = {
            "tool": str(tool),
            "algo": str(algo),
            "dataset": dataset.name,
            "runs": configured_runs,
            "profiled_processes": len(candidates),
            "callgraph_profiled_processes": len(candidates),
            "hardware_counters": (
                "pending_separate_perf_stat_pass"
                if self.config.hardware_counters
                else "not_requested"
            ),
            "representative_run_index": (
                selected_index + 1 if selected_index is not None else None
            ),
            "flamegraph_selection": (
                "execution_time_closest_to_median"
                if selected_index is not None
                else "failed_no_execution_times"
            ),
        }

        flamegraph_file = (
            self.output_dir
            / "flamegraphs"
            / f"{tool}_{algo}_{dataset.name}.html"
        )
        flamegraph_file.parent.mkdir(parents=True, exist_ok=True)
        if (
            selected_index is not None
            and selected.cpu_callgraph
            and self.flamegraph_generator.generate_interactive_flamegraph(
                selected.cpu_callgraph, flamegraph_file
            )
        ):
            selected.flamegraph_html = flamegraph_file
            selected.flamegraph_svg = flamegraph_file.with_suffix(".svg")
            folded_file = selected.cpu_callgraph.with_suffix(".folded")
            selected.cpu_callgraph_folded = (
                folded_file if folded_file.exists() else None
            )

        for index, candidate in enumerate(candidates):
            if (
                index == selected_index
                or not candidate.cpu_callgraph
            ):
                continue
            candidate.cpu_callgraph.unlink(missing_ok=True)

        if selected_index is None:
            selected.cpu_callgraph = None

        return selected

    def cleanup(self):
        """Cleanup profiling resources"""
        if self.cpu_profiler:
            self.cpu_profiler.cleanup()
        if self.gpu_profiler:
            self.gpu_profiler.cleanup()
        if self.flamegraph_generator:
            self.flamegraph_generator.cleanup()

    def write_profile_summary(self, profiling_result: ProfileResult) -> Path:
        """Write or refresh the JSON summary after metrics are updated."""
        metadata = profiling_result.metadata
        tool = metadata.get("tool", "unknown")
        algo = metadata.get("algo", "unknown")
        dataset = metadata.get("dataset", "unknown")
        output_file = (
            self.output_dir
            / "summary"
            / f"summary_{tool}_{algo}_{dataset}.json"
        )
        output_file.parent.mkdir(parents=True, exist_ok=True)
        profiling_result.metadata["summary_file"] = str(output_file)
        with open(output_file, "w") as f:
            json.dump(profiling_result.to_dict(), f, indent=2)
        print(f"Profiling JSON summary: {output_file}")
        return output_file

    def get_profiling_summary(self) -> Dict[str, Any]:
        """Get summary of profiling capabilities and results"""
        summary = {
            "cpu_profiling_enabled": self.config.cpu_profiling,
            "gpu_profiling_enabled": self.config.gpu_profiling,
            "flamegraph_enabled": self.config.flamegraph,
            "cpu_profiler_available": self.cpu_profiler is not None,
            "gpu_profiler_available": self.gpu_profiler is not None,
            "flamegraph_available": self.flamegraph_generator is not None,
            "output_directory": str(self.output_dir),
        }
        return summary


def create_profiler_manager(
    cpu: bool = False,
    gpu: bool = False,
    flamegraph: bool = False,
    output_dir: Optional[Path] = None,
    hardware_counters: Optional[bool] = None,
) -> ProfilerManager:
    """Create profiler manager with specified configuration"""
    if hardware_counters is None:
        hardware_counters = cpu

    config_obj = ProfilingConfig(
        cpu_profiling=cpu,
        gpu_profiling=gpu,
        flamegraph=flamegraph,
        hardware_counters=hardware_counters,
    )

    # Use custom output directory if provided, otherwise default
    if output_dir is None:
        return ProfilerManager(config_obj)
    else:
        return ProfilerManager(config_obj, output_dir=output_dir)
