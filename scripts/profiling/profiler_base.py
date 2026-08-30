"""
Base classes for profiling in spla-bench
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, Field
from pathlib import Path
from typing import Optional, Dict, List, Any


@dataclass
class ProfileResult:
    """Results from profiling execution"""

    cpu_callgraph: Optional[Path] = None
    cpu_hardware_counters: Optional[Dict[str, Any]] = None
    gpu_timeline: Optional[Path] = None
    gpu_memory: Optional[Path] = None
    flamegraph_svg: Optional[Path] = None
    flamegraph_html: Optional[Path] = None
    raw_output: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def has_cpu_data(self) -> bool:
        """Check if CPU profiling data is available"""
        return self.cpu_callgraph is not None or self.cpu_hardware_counters is not None

    def has_gpu_data(self) -> bool:
        """Check if GPU profiling data is available"""
        return self.gpu_timeline is not None or self.gpu_memory is not None

    def has_flamegraph(self) -> bool:
        """Check if flamegraph is available"""
        return self.flamegraph_svg is not None or self.flamegraph_html is not None


class Profiler(ABC):
    """Base class for all profilers"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def setup(self) -> bool:
        """Setup profiler, returns True if successful"""
        pass

    @abstractmethod
    def profile(self, command: List[str], metadata: Dict[str, Any]) -> ProfileResult:
        """Run profiling on command"""
        pass

    @abstractmethod
    def parse_results(self, raw_output: bytes) -> Dict[str, Any]:
        """Parse profiling results"""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup profiler resources"""
        pass

    def get_output_file(self, filename: str) -> Path:
        """Get output file path in profiler directory"""
        return self.output_dir / filename

    def is_available(self) -> bool:
        """Check if profiler is available on system"""
        return True
