import drivers.driver as driver

import re

from typing import List
from lib.dataset import Dataset
from lib.algorithm import AlgorithmName
from lib.tool import ToolName


class DriverSpla(driver.Driver):
    OPENCL_ERRORS = (
        "CL_OUT_OF_RESOURCES",
        "CL_MEM_OBJECT_ALLOCATION_FAILURE",
        "CL_INVALID_ARG_VALUE",
        "CL_INVALID_OPERATION",
        "CL_BUILD_PROGRAM_FAILURE",
        "CL_INVALID_KERNEL_NAME",
    )

    @staticmethod
    def _benchmark_flags(num_iterations: int) -> List[str]:
        return [
            f"--niters={num_iterations + 1}",
            "--run-cpu=false",
            "--run-ref=false",
            "--run-gpu=true",
        ]

    def can_run_bfs(self, dataset: Dataset) -> bool:
        return True

    def can_run_sssp(self, dataset: Dataset) -> bool:
        return True

    def can_run_tc(self, dataset: Dataset) -> bool:
        return True

    def can_run_pr(self, dataset: Dataset) -> bool:
        return True

    def run_bfs(self,
                dataset: Dataset,
                source_vertex: int,
                num_iterations: int) -> driver.ExecutionResult:

        output = self.check_output([
            self.exec_path(AlgorithmName.bfs),
            f"--mtxpath={dataset.path}",
            f"--source={source_vertex}",
            *self._benchmark_flags(num_iterations),
        ])

        return DriverSpla._parse_output(output)

    def run_sssp(self,
                 dataset: Dataset,
                 source_vertex: int,
                 num_iterations: int) -> driver.ExecutionResult:

        output = self.check_output([
            self.exec_path(AlgorithmName.sssp),
            f"--mtxpath={dataset.path}",
            f"--source={source_vertex}",
            *self._benchmark_flags(num_iterations),
        ])

        return DriverSpla._parse_output(output)

    def run_tc(self,
               dataset: Dataset,
               num_iterations: int) -> driver.ExecutionResult:

        dir_flag = 'true' if not dataset.get_directed() else 'false'

        output = self.check_output([
            self.exec_path(AlgorithmName.tc),
            f"--mtxpath={dataset.path}",
            f"--undirected={dir_flag}",
            *self._benchmark_flags(num_iterations),
        ])
        return DriverSpla._parse_output(output)

    def run_pr(self,
               dataset: Dataset,
               num_iterations: int) -> driver.ExecutionResult:

        output = self.check_output([
            self.exec_path(AlgorithmName.pr),
            f"--mtxpath={dataset.path}",
            *self._benchmark_flags(num_iterations),
        ])

        return DriverSpla._parse_output(output)

    def tool_name(self) -> ToolName:
        return ToolName.spla

    def _build_command(self,
                       dataset: Dataset,
                       algo: AlgorithmName,
                       source: int,
                       iterations: int) -> List[str]:
        if algo == AlgorithmName.bfs:
            return [
                str(self.exec_path(AlgorithmName.bfs)),
                f"--mtxpath={dataset.path}",
                f"--source={source}",
                *self._benchmark_flags(iterations),
            ]
        if algo == AlgorithmName.sssp:
            return [
                str(self.exec_path(AlgorithmName.sssp)),
                f"--mtxpath={dataset.path}",
                f"--source={source}",
                *self._benchmark_flags(iterations),
            ]
        if algo == AlgorithmName.tc:
            dir_flag = 'true' if not dataset.get_directed() else 'false'
            return [
                str(self.exec_path(AlgorithmName.tc)),
                f"--mtxpath={dataset.path}",
                f"--undirected={dir_flag}",
                *self._benchmark_flags(iterations),
            ]
        if algo == AlgorithmName.pr:
            return [
                str(self.exec_path(AlgorithmName.pr)),
                f"--mtxpath={dataset.path}",
                *self._benchmark_flags(iterations),
            ]
        raise Exception(f"Algorithm {algo} not supported")

    def _parse_profiled_output(self,
                               dataset: Dataset,
                               algo: AlgorithmName,
                               raw_output: str,
                               iterations: int) -> driver.ExecutionResult:
        if raw_output is None:
            return driver.ExecutionResult(warm_up=0.0, times=[])
        return DriverSpla._parse_output(raw_output.encode('ASCII', errors='ignore'))

    @staticmethod
    def _parse_output(output):
        text = output.decode("ASCII", errors="ignore").replace("\r", "")
        lines = text.split("\n")
        warmup = 0.0
        runs = []
        for line in lines:
            # Parse GPU timings if available, otherwise use CPU timings
            if line.startswith("gpu(ms):"):
                timings_str = line.replace("gpu(ms):", "").strip()
                timings = [
                    float(v.strip()) for v in timings_str.split(",") if v.strip()
                ]
                if timings:
                    if len(timings) > 1:
                        warmup = timings[0]
                        runs = timings[1:]
                    else:
                        runs = timings
            elif line.startswith("cpu(ms):") and not runs:
                timings_str = line.replace("cpu(ms):", "").strip()
                timings = [
                    float(v.strip()) for v in timings_str.split(",") if v.strip()
                ]
                if timings:
                    if len(timings) > 1:
                        warmup = timings[0]
                        runs = timings[1:]
                    else:
                        runs = timings

        result = driver.ExecutionResult(warmup, runs)

        env_match = re.search(
            r"^env:\s*(?P<platform>.*?)\s+"
            r"device:\s*(?P<device>.*?)\s+"
            r"vendor:(?P<vendor>\S+)\s+"
            r"mcu:(?P<mcu>\d+)\s+"
            r"wave:(?P<wave>\d+)\s+"
            r"mwgs:(?P<mwgs>\d+)\s*$",
            text,
            re.MULTILINE,
        )
        if env_match:
            result.metadata.update({
                "gpu_platform": env_match.group("platform"),
                "gpu_device": env_match.group("device"),
                "gpu_vendor": env_match.group("vendor"),
                "gpu_max_compute_units": int(env_match.group("mcu")),
                "gpu_wave_size": int(env_match.group("wave")),
                "gpu_max_work_group_size": int(env_match.group("mwgs")),
            })

        error_counts = {
            error: text.count(error)
            for error in DriverSpla.OPENCL_ERRORS
            if error in text
        }
        result.metadata["opencl_error_counts"] = error_counts

        return result
