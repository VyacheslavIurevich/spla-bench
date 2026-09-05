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
        self.flamegraph_folded_files: List[Path] = []

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

        # Disable GPU profiling for Gunrock and GraphBLAST
        disable_gpu_profiling = str(tool) in ["gunrock", "graphblast"]

        if (
            self.config.cpu_profiling
            and self.cpu_profiler
        ):
            print(f"Running CPU profiling for {tool} {algo}")
            cpu_result = self.cpu_profiler.profile(command, metadata)
            profiling_result.cpu_callgraph = cpu_result.cpu_callgraph
            profiling_result.cpu_hardware_counters = cpu_result.cpu_hardware_counters
            profiling_result.raw_output = cpu_result.raw_output
            profiling_result.merge_metrics_from(cpu_result)

            if (
                self.config.flamegraph
                and self.flamegraph_generator
                and profiling_result.cpu_callgraph
            ):
                print(f"Generating flamegraph for {tool} {algo}")
                flamegraph_file = (
                    self.output_dir
                    / "flamegraphs"
                    / f"{tool}_{algo}_{dataset.name}.html"
                )
                flamegraph_file.parent.mkdir(parents=True, exist_ok=True)

                if self.flamegraph_generator.generate_interactive_flamegraph(
                    profiling_result.cpu_callgraph, flamegraph_file
                ):
                    profiling_result.flamegraph_html = flamegraph_file
                    profiling_result.flamegraph_svg = flamegraph_file.with_suffix(".svg")
                    folded_file = profiling_result.cpu_callgraph.with_suffix(".folded")
                    if folded_file.exists():
                        self.flamegraph_folded_files.append(folded_file)

        if (
            self.config.gpu_profiling
            and self.gpu_profiler
            and not disable_gpu_profiling
        ):
            print(f"Running GPU profiling for {tool} {algo}")
            gpu_result = self.gpu_profiler.profile(command, metadata)
            profiling_result.gpu_timeline = gpu_result.gpu_timeline
            profiling_result.gpu_memory = gpu_result.gpu_memory
            profiling_result.raw_output = gpu_result.raw_output or profiling_result.raw_output
            profiling_result.merge_metrics_from(gpu_result)
            profiling_result.metadata.update(gpu_result.metadata)

        self._write_profile_summary(profiling_result)
        return profiling_result

    def cleanup(self):
        """Cleanup profiling resources"""
        if (
            self.flamegraph_generator
            and len(self.flamegraph_folded_files) > 1
        ):
            folded_file = self.output_dir / "flamegraphs" / "aggregate.folded"
            html_file = self.output_dir / "flamegraphs" / "aggregate.html"
            if self.flamegraph_generator.aggregate_folded_files(
                self.flamegraph_folded_files, folded_file
            ):
                self.flamegraph_generator.generate_interactive_flamegraph_from_folded(
                    folded_file, html_file
                )

        if self.cpu_profiler:
            self.cpu_profiler.cleanup()
        if self.gpu_profiler:
            self.gpu_profiler.cleanup()
        if self.flamegraph_generator:
            self.flamegraph_generator.cleanup()

    def _write_profile_summary(self, profiling_result: ProfileResult) -> None:
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
        with open(output_file, "w") as f:
            json.dump(profiling_result.to_dict(), f, indent=2)

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
) -> ProfilerManager:
    """Create profiler manager with specified configuration"""
    config_obj = ProfilingConfig(
        cpu_profiling=cpu,
        gpu_profiling=gpu,
        flamegraph=flamegraph,
        hardware_counters=True,
    )

    # Use custom output directory if provided, otherwise default
    if output_dir is None:
        return ProfilerManager(config_obj)
    else:
        return ProfilerManager(config_obj, output_dir=output_dir)
