"""
Parsers for profiling results
"""

import re
from typing import Dict, Any, List
from pathlib import Path


class PerfStatParser:
    """Parser for perf stat output"""

    @staticmethod
    def parse_perf_stat(output: str) -> Dict[str, Any]:
        """Parse perf stat output"""
        counters = {}

        patterns = {
            "cycles": r"([\d,]+)\s+cycles",
            "instructions": r"([\d,]+)\s+instructions",
            "cache_references": r"([\d,]+)\s+cache-references",
            "cache_misses": r"([\d,]+)\s+cache-misses",
            "llc_loads": r"([\d,]+)\s+LLC-loads",
            "llc_load_misses": r"([\d,]+)\s+LLC-load-misses",
            "branch_misses": r"([\d,]+)\s+branch-misses",
            "branch_instructions": r"([\d,]+)\s+branch-instructions",
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

    @staticmethod
    def calculate_derived_metrics(counters: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate common processor metrics"""
        derived = {}

        if "cycles" in counters and "instructions" in counters:
            if counters["cycles"] > 0:
                derived["ipc"] = counters["instructions"] / counters["cycles"]

        if "cache_references" in counters and "cache_misses" in counters:
            if counters["cache_references"] > 0:
                derived["cache_miss_rate"] = (
                    counters["cache_misses"] / counters["cache_references"]
                )

        if "llc_loads" in counters and "llc_load_misses" in counters:
            if counters["llc_loads"] > 0:
                derived["llc_miss_rate"] = (
                    counters["llc_load_misses"] / counters["llc_loads"]
                )

        if "branch_instructions" in counters and "branch_misses" in counters:
            if counters["branch_instructions"] > 0:
                derived["branch_miss_rate"] = (
                    counters["branch_misses"] / counters["branch_instructions"]
                )

        return derived


class GPUMemoryParser:
    """Parser for GPU memory profiling results"""

    @staticmethod
    def parse_nvprof_memory(output: str) -> Dict[str, Any]:
        """Parse nvprof memory profile output"""
        memory_data = {
            "total_allocations": output.count("Allocate"),
            "total_free": output.count("Free"),
            "raw_output": output,
        }

        # Parse memory sizes
        alloc_pattern = r"Allocate\s+(\d+)\s+(\d+)\s+bytes"
        allocations = re.findall(alloc_pattern, output)

        if allocations:
            memory_data["allocations"] = []
            for addr, size in allocations:
                memory_data["allocations"].append({"address": addr, "size": int(size)})

        # Parse peak memory usage
        peak_pattern = r"Max memory usage:\s+([\d.]+)\s+([KMG]?B)"
        peak_match = re.search(peak_pattern, output)
        if peak_match:
            value = float(peak_match.group(1))
            unit = peak_match.group(2)
            memory_data["peak_memory"] = {"value": value, "unit": unit}

        return memory_data


class NsysStatsParser:
    """Parser for nsys stats output"""

    @staticmethod
    def parse_nsys_stats(output: str) -> Dict[str, Any]:
        """Parse nsys stats output"""
        stats = {"raw_output": output, "kernels": [], "cuda_calls": [], "total_time": 0}

        # Parse kernel execution times
        kernel_pattern = r"([^\s]+)\s+([\d.]+)"
        lines = output.split("\n")

        current_section = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            if "CUDA Kernel" in line:
                current_section = "kernels"
                continue
            elif "CUDA API" in line:
                current_section = "cuda_calls"
                continue

            if current_section == "kernels" and "Busy" in line:
                # Parse kernel execution time
                match = re.search(r"([\d.]+)(ms|us|ns)\s+(.+?)\s+(\d+)", line)
                if match:
                    time_value = float(match.group(1))
                    time_unit = match.group(2)
                    kernel_name = match.group(3)
                    calls = int(match.group(4))

                    stats["kernels"].append(
                        {
                            "name": kernel_name,
                            "time": time_value,
                            "unit": time_unit,
                            "calls": calls,
                        }
                    )

            if "Total" in line:
                total_match = re.search(r"([\d.]+)(ms|us|ns)", line)
                if total_match:
                    total_value = float(total_match.group(1))
                    total_unit = total_match.group(2)
                    stats["total_time"] = {"value": total_value, "unit": total_unit}

        return stats


class ProfilingReportGenerator:
    """Generate comprehensive profiling reports"""

    @staticmethod
    def generate_cpu_report(
        perf_stat_data: Dict[str, Any], derived_metrics: Dict[str, Any]
    ) -> str:
        """Generate CPU profiling report"""
        report = []
        report.append("=== CPU Profiling Report ===\n")

        report.append("Hardware Counters:")
        for key, value in perf_stat_data.items():
            if key != "raw_output":
                report.append(f"  {key}: {value:,}")

        report.append("\nDerived Metrics:")
        for key, value in derived_metrics.items():
            if isinstance(value, float):
                report.append(f"  {key}: {value:.4f}")
            else:
                report.append(f"  {key}: {value}")

        return "\n".join(report)

    @staticmethod
    def generate_gpu_report(gpu_data: Dict[str, Any]) -> str:
        """Generate GPU profiling report"""
        report = []
        report.append("=== GPU Profiling Report ===\n")

        timeline_data = gpu_data.get("timeline", {})
        memory_data = gpu_data.get("memory", {})

        if "kernels" in timeline_data:
            report.append(f"Total Kernels: {len(timeline_data['kernels'])}")
            report.append(
                f"Total Time: {timeline_data.get('total_time', {}).get('value', 0):.2f}"
            )

            if timeline_data["kernels"]:
                report.append("\nTop 10 Kernels by Time:")
                sorted_kernels = sorted(
                    timeline_data["kernels"], key=lambda x: x["time"], reverse=True
                )[:10]

                for i, kernel in enumerate(sorted_kernels, 1):
                    report.append(
                        f"  {i}. {kernel['name']}: {kernel['time']:.3f}{kernel['unit']} "
                        f"({kernel['calls']} calls)"
                    )

        if memory_data.get("allocations"):
            report.append(f"\nTotal Allocations: {len(memory_data['allocations'])}")
            report.append(f"Total Free Operations: {memory_data.get('total_free', 0)}")

            peak = memory_data.get("peak_memory")
            if peak:
                report.append(f"Peak Memory Usage: {peak['value']:.2f} {peak['unit']}")

        return "\n".join(report)
