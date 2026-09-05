"""
GPU profiler implementation for Intel GPU only
"""

import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
import time

from profiler_base import Profiler, ProfileResult


class GPUProfiler(Profiler):
    """Intel GPU profiler for integrated Intel GPUs using OpenCL and system monitoring"""

    def __init__(self, output_dir: Path):
        super().__init__(output_dir)
        self.clinfo_path = shutil.which("clinfo")
        self.time_path = shutil.which("time")
        self.is_intel_gpu = self._detect_intel_gpu()
        self.intel_gpu_info = self._get_intel_gpu_info()

    def _detect_intel_gpu(self) -> bool:
        """Check if Intel GPU is available"""
        if not self.clinfo_path:
            return False

        try:
            result = subprocess.run([self.clinfo_path], capture_output=True, text=True)
            return "Intel" in result.stdout and "GPU" in result.stdout
        except Exception:
            return False

    def _get_intel_gpu_info(self) -> Dict[str, str]:
        """Get Intel GPU device information"""
        if not self.clinfo_path:
            return {}

        try:
            result = subprocess.run([self.clinfo_path], capture_output=True, text=True)

            gpu_info = {}
            for line in result.stdout.split("\n"):
                line_stripped = line.strip()
                if "Device Name" in line_stripped and "Intel" in line_stripped:
                    device_name = line_stripped.split(":")[1].strip()
                    gpu_info["device_name"] = device_name
                    # Parse device name more accurately
                    if "Iris" in device_name:
                        gpu_info["gpu_model"] = "Intel Iris Xe Graphics"
                    elif "Xe" in device_name:
                        gpu_info["gpu_model"] = "Intel Xe Graphics"
                elif "Platform Version" in line_stripped:
                    gpu_info["platform_version"] = line_stripped.split(":")[1].strip()
                elif "Device Version" in line_stripped and "NEO" in line_stripped:
                    gpu_info["opencl_version"] = line_stripped.split(":")[1].strip()
                elif "Device OpenCL C Version" in line_stripped:
                    gpu_info["opencl_c_version"] = line_stripped.split(":")[1].strip()
                elif "Device Global Mem Size" in line_stripped:
                    gpu_info["global_memory"] = line_stripped.split(":")[1].strip()
                elif "Device Max Compute Units" in line_stripped:
                    gpu_info["compute_units"] = int(line_stripped.split(":")[1].strip())
                elif "Device Max Clock Frequency" in line_stripped:
                    gpu_info["clock_frequency"] = line_stripped.split(":")[1].strip()

            return gpu_info
        except Exception as e:
            print(f"Error parsing clinfo: {e}")
            return {}

    def is_available(self) -> bool:
        """Check if Intel GPU profiler is available"""
        return self.is_intel_gpu

    def setup(self) -> bool:
        """Setup Intel GPU profiler"""
        if not self.is_available():
            print("Intel GPU not detected")
            return False

        print(f"Intel GPU detected: {self.intel_gpu_info.get('gpu_model', 'Unknown')}")
        return True

    def _output_base(self, prefix: str, metadata: Dict[str, Any]) -> Path:
        parts = [
            prefix,
            metadata.get("tool"),
            metadata.get("algo"),
            metadata.get("dataset"),
        ]
        filename = "_".join(str(part).replace("/", "_") for part in parts if part)
        return self.get_output_file(filename)

    def _update_gpu_info_from_output(self, stdout: str) -> None:
        for line in stdout.splitlines():
            if not line.startswith("env:") or "device:" not in line:
                continue

            env_part, device_part = line.split("device:", 1)
            device_name = device_part.split("vendor:", 1)[0].strip()
            platform_name = env_part.replace("env:", "", 1).strip()

            if device_name:
                self.intel_gpu_info["device_name"] = device_name
            if platform_name:
                self.intel_gpu_info["platform_name"] = platform_name

    def _parse_timing_samples(self, stdout: str, prefix: str) -> List[float]:
        for line in stdout.splitlines():
            if line.startswith(prefix):
                values = line.replace(prefix, "").strip()
                return [
                    float(value.strip())
                    for value in values.split(",")
                    if value.strip()
                ]
        return []

    def profile(self, command: List[str], metadata: Dict[str, Any]) -> ProfileResult:
        """Run GPU profiling with basic monitoring for Intel GPU"""
        print(
            f"Running Intel GPU profiling for {metadata.get('tool')} {metadata.get('algo')}"
        )

        output_file = self._output_base("intel_gpu", metadata)
        analysis_file = output_file.with_suffix(".txt")
        timing_file = output_file.with_suffix(".timing")

        try:
            # Get system resources before execution
            before_stats = self._get_system_stats()

            # Run command with timing
            if self.time_path:
                command_with_timing = [
                    self.time_path,
                    "-v",
                    "-o",
                    str(timing_file),
                ] + command
                command_result = subprocess.run(
                    command_with_timing,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                )
            else:
                command_result = subprocess.run(
                    command, capture_output=True, text=True, timeout=300
                )

            # Get system resources after execution
            after_stats = self._get_system_stats()

            # Calculate timing
            elapsed_time = after_stats.get("timestamp", 0) - before_stats.get(
                "timestamp", 0
            )
            after_stats["elapsed_time"] = elapsed_time

            # Parse time output if available
            timing_info = (
                self._parse_timing_file(timing_file) if timing_file.exists() else {}
            )
            if not timing_info:
                timing_info["elapsed"] = elapsed_time

            # Analyze GPU impact
            gpu_patterns = self._analyze_gpu_output(
                command_result.stdout, command_result.stderr
            )
            self._update_gpu_info_from_output(command_result.stdout)

            # Save comprehensive GPU analysis
            analysis_file_path = str(analysis_file).replace('"', "")
            result = ProfileResult(
                metadata=metadata,
                raw_output=command_result.stdout,
                gpu_timeline=Path(analysis_file_path),
            )
            result.add_metric(
                "gpu.spla_gpu_time",
                self._parse_timing_samples(command_result.stdout, "gpu(ms):"),
                "ms",
            )
            result.add_metric(
                "gpu.spla_cpu_time",
                self._parse_timing_samples(command_result.stdout, "cpu(ms):"),
                "ms",
            )
            result.add_metric("gpu.process.elapsed", [timing_info.get("elapsed", 0)], "s")
            result.add_metric("gpu.process.user", [timing_info.get("user", 0)], "s")
            result.add_metric("gpu.process.system", [timing_info.get("system", 0)], "s")
            result.add_metric("gpu.system.cpu_before", [before_stats.get("cpu_usage", 0)], "%")
            result.add_metric("gpu.system.cpu_after", [after_stats.get("cpu_usage", 0)], "%")
            result.add_metric(
                "gpu.system.memory_before", [before_stats.get("memory_usage", 0)], "%"
            )
            result.add_metric(
                "gpu.system.memory_after", [after_stats.get("memory_usage", 0)], "%"
            )
            result.add_metric(
                "gpu.system.memory_delta",
                [
                    after_stats.get("memory_usage", 0)
                    - before_stats.get("memory_usage", 0)
                ],
                "%",
            )
            with open(analysis_file_path, "w", encoding="utf-8") as f:
                f.write("=== Intel GPU Profiling Analysis ===\n\n")
                f.write(f"Tool: {metadata.get('tool')}\n")
                f.write(f"Algorithm: {metadata.get('algo')}\n")
                f.write(f"Dataset: {metadata.get('dataset')}\n\n")
                f.write("=== GPU Device Information ===\n")
                f.write(
                    f"Device Name: {self.intel_gpu_info.get('device_name', 'Unknown')}\n"
                )
                f.write(
                    f"Platform Name: {self.intel_gpu_info.get('platform_name', 'Unknown')}\n"
                )
                f.write(
                    f"Platform Version: {self.intel_gpu_info.get('platform_version', 'Unknown')}\n"
                )
                f.write(
                    f"OpenCL Version: {self.intel_gpu_info.get('opencl_version', 'Unknown')}\n"
                )
                f.write(
                    f"OpenCL C Version: {self.intel_gpu_info.get('opencl_c_version', 'Unknown')}\n"
                )
                f.write(
                    f"Global Memory: {self.intel_gpu_info.get('global_memory', 'Unknown')}\n"
                )
                f.write(
                    f"Compute Units: {self.intel_gpu_info.get('compute_units', 0)}\n\n"
                )
                f.write("=== Execution Analysis ===\n")
                f.write(f"Exit Code: {command_result.returncode}\n")
                f.write(f"Execution Time: {timing_info.get('elapsed', 0):.2f}s\n")
                f.write(f"User Time: {timing_info.get('user', 0):.2f}s\n")
                f.write(f"System Time: {timing_info.get('system', 0):.2f}s\n")
                f.write(f"\n=== System Resources ===\n")
                f.write(f"CPU Usage Before: {before_stats.get('cpu_usage', 0):.1f}%\n")
                f.write(f"CPU Usage After: {after_stats.get('cpu_usage', 0):.1f}%\n")
                f.write(
                    f"CPU Delta: {after_stats.get('cpu_usage', 0) - before_stats.get('cpu_usage', 0):.1f}%\n"
                )
                f.write(
                    f"Memory Usage Before: {before_stats.get('memory_usage', 0):.1f}%\n"
                )
                f.write(
                    f"Memory Usage After: {after_stats.get('memory_usage', 0):.1f}%\n"
                )
                f.write(
                    f"Memory Delta: {after_stats.get('memory_usage', 0) - before_stats.get('memory_usage', 0):.1f}%\n"
                )
                f.write(
                    f"Memory Pressure: {'HIGH' if after_stats.get('memory_usage', 0) > 80 else 'NORMAL'}\n"
                )
                f.write(f"\n=== GPU Pattern Analysis ===\n")
                f.write(f"GPU Errors: {gpu_patterns.get('gpu_errors', 0)}\n")
                f.write(f"OpenCL Errors: {gpu_patterns.get('opencl_errors', 0)}\n")
                f.write(
                    f"Kernel/Launch Count: {gpu_patterns.get('kernel_launches', 0)}\n"
                )
                f.write(
                    f"Memory Operations: {gpu_patterns.get('memory_operations', 0)}\n"
                )
                f.write(f"Warnings: {gpu_patterns.get('gpu_warnings', 0)}\n")

                if result.numeric_metrics:
                    f.write(f"\n=== Aggregated Metrics ===\n")
                    for name, metric in sorted(result.numeric_metrics.items()):
                        f.write(
                            f"{name}: mean={metric.mean():.2f}{metric.unit}, "
                            f"median={metric.median():.2f}{metric.unit}, "
                            f"stdev={metric.stdev():.2f}{metric.unit}, "
                            f"samples={metric.samples}\n"
                        )

                if gpu_patterns.get("performance_issues"):
                    f.write(f"\n=== Performance Issues Detected ===\n")
                    for issue in gpu_patterns["performance_issues"]:
                        f.write(f"  - {issue}\n")

                f.write(f"\n=== Command Output ===\n")
                f.write(f"Command: {' '.join(command)}\n\n")
                f.write(f"STDOUT:\n{command_result.stdout}\n")
                f.write(f"\nSTDERR:\n{command_result.stderr}\n")

            # Add GPU analysis to metadata
            result.metadata.update(gpu_patterns)
            result.metadata["system_analysis"] = after_stats
            result.metadata["intel_gpu_info"] = self.intel_gpu_info

            return result

        except subprocess.TimeoutExpired:
            print(f"Intel GPU profiling timed out after 300 seconds")
            timeout_file = output_file.with_suffix(".timeout")
            with open(str(timeout_file), "w") as f:
                f.write(f"Command timed out after 300 seconds\n")
            return ProfileResult(metadata=metadata)

        except Exception as e:
            print(f"Intel GPU profiling failed: {e}")
            error_file = output_file.with_suffix(".error")
            with open(str(error_file), "w") as f:
                f.write(f"Error during GPU profiling: {str(e)}\n")
            return ProfileResult(metadata=metadata)

    def _get_system_stats(self) -> Dict[str, float]:
        """Get current system statistics"""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent

            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory_percent,
                "timestamp": time.time(),
            }
        except ImportError:
            # Fallback without psutil
            try:
                with open("/proc/meminfo", "r") as f:
                    meminfo = f.read()
                    mem_total = int(
                        [l for l in meminfo.split("\n") if "MemTotal" in l][0].split()[
                            1
                        ]
                    )
                    mem_available = int(
                        [l for l in meminfo.split("\n") if "MemAvailable" in l][
                            0
                        ].split()[1]
                    )
                    memory_percent = ((mem_total - mem_available) / mem_total) * 100
            except:
                memory_percent = 0

            return {
                "cpu_usage": 0,
                "memory_usage": memory_percent,
                "timestamp": time.time(),
            }
        except Exception as e:
            print(f"Error getting system stats: {e}")
            return {"cpu_usage": 0, "memory_usage": 0, "timestamp": 0}

    def _parse_timing_file(self, timing_file: Path) -> Dict[str, float]:
        """Parse time command output"""
        timing_info = {"elapsed": 0, "user": 0, "system": 0}

        if not timing_file.exists():
            return timing_info

        try:
            with open(str(timing_file), "r") as f:
                content = f.read()

            # Parse typical time output
            for line in content.split("\n"):
                if "User time" in line:
                    try:
                        timing_info["user"] = float(
                            line.split(":")[1].split("s")[0].strip()
                        )
                    except:
                        pass
                elif "System time" in line:
                    try:
                        timing_info["system"] = float(
                            line.split(":")[1].split("s")[0].strip()
                        )
                    except:
                        pass
                elif "Elapsed" in line:
                    time_str = ""
                    try:
                        time_str = line.split("):", 1)[1].strip()
                        time_parts = list(map(float, time_str.split(":")))
                        if len(time_parts) == 3:
                            h, m, s = time_parts
                            timing_info["elapsed"] = h * 3600 + m * 60 + s
                        elif len(time_parts) == 2:
                            m, s = time_parts
                            timing_info["elapsed"] = m * 60 + s
                        else:
                            timing_info["elapsed"] = time_parts[0]
                    except:
                        try:
                            timing_info["elapsed"] = float(time_str)
                        except:
                            pass

            return timing_info
        except Exception as e:
            print(f"Error parsing timing file: {e}")
            return timing_info

    def _analyze_gpu_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """Analyze command output for GPU-related patterns"""
        analysis = {
            "gpu_errors": 0,
            "gpu_warnings": 0,
            "kernel_launches": 0,
            "memory_operations": 0,
            "opencl_errors": 0,
            "opencl_runtime_detected": False,
            "spla_gpu_timing_reported": False,
            "performance_issues": [],
        }

        combined_output = stdout + stderr

        # Check for OpenCL error patterns
        opencl_errors = [
            "CL_OUT_OF_RESOURCES",
            "CL_MEM_OBJECT_ALLOCATION_FAILURE",
            "CL_INVALID_ARG_VALUE",
            "CL_INVALID_OPERATION",
            "CL_BUILD_PROGRAM_FAILURE",
            "CL_INVALID_KERNEL_NAME",
        ]

        for error_pattern in opencl_errors:
            count = combined_output.count(error_pattern)
            if count > 0:
                analysis["opencl_errors"] += count
                analysis["performance_issues"].append(
                    f"OpenCL error: {error_pattern} ({count} occurrences)"
                )

        # Check for GPU-specific patterns
        if "kernel" in stdout.lower():
            analysis["kernel_launches"] = stdout.lower().count("kernel")

        if "env: OpenCL Acc" in stdout:
            analysis["opencl_runtime_detected"] = True

        if "gpu(ms):" in stdout:
            analysis["spla_gpu_timing_reported"] = True

        if "memory" in stdout.lower() or "mem" in stdout.lower():
            analysis["memory_operations"] = stdout.lower().count(
                "memory"
            ) + stdout.lower().count("mem")

        # Performance indicators
        performance_indicators = [
            "slow",
            "timeout",
            "synchronization",
            "blocking",
            "busy",
            "overflow",
            "underflow",
        ]

        for indicator in performance_indicators:
            if indicator in stdout.lower():
                analysis["performance_issues"].append(
                    f"Performance issue detected: '{indicator}'"
                )

        analysis["gpu_warnings"] = combined_output.lower().count("warning")

        return analysis

    def parse_results(self, raw_output: bytes) -> Dict[str, Any]:
        """Parse profiling results"""
        return {}

    def cleanup(self) -> None:
        """Cleanup profiler resources"""
        pass
