"""
Base classes for profiling in spla-bench
"""

import statistics

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, List, Any


@dataclass
class NumericMetric:
    """Numeric metric with raw samples and aggregate statistics."""

    samples: List[float] = field(default_factory=list)
    unit: str = ""

    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    def median(self) -> float:
        return statistics.median(self.samples) if self.samples else 0.0

    def stdev(self) -> float:
        return statistics.stdev(self.samples) if len(self.samples) >= 2 else 0.0

    def min(self) -> float:
        return min(self.samples) if self.samples else 0.0

    def max(self) -> float:
        return max(self.samples) if self.samples else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "samples": self.samples,
            "unit": self.unit,
            "mean": self.mean(),
            "median": self.median(),
            "stdev": self.stdev(),
            "min": self.min(),
            "max": self.max(),
        }


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
    numeric_metrics: Dict[str, NumericMetric] = field(default_factory=dict)
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

    def add_metric(self, name: str, samples: List[float], unit: str = "") -> None:
        clean_samples = [float(sample) for sample in samples if sample is not None]
        if clean_samples:
            self.numeric_metrics[name] = NumericMetric(clean_samples, unit)

    def merge_metrics_from(self, other: "ProfileResult") -> None:
        self.numeric_metrics.update(other.numeric_metrics)

    def metrics_brief_str(self) -> str:
        parts = []
        for name, metric in sorted(self.numeric_metrics.items()):
            unit = metric.unit
            parts.append(f"{name}_mean={metric.mean():.2f}{unit}")
        return ", ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata,
            "files": {
                "cpu_callgraph": str(self.cpu_callgraph) if self.cpu_callgraph else None,
                "gpu_timeline": str(self.gpu_timeline) if self.gpu_timeline else None,
                "gpu_memory": str(self.gpu_memory) if self.gpu_memory else None,
                "flamegraph_svg": str(self.flamegraph_svg) if self.flamegraph_svg else None,
                "flamegraph_html": str(self.flamegraph_html) if self.flamegraph_html else None,
            },
            "metrics": {
                name: metric.to_dict()
                for name, metric in sorted(self.numeric_metrics.items())
            },
        }


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
