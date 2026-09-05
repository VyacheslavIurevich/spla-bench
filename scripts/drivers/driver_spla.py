import drivers.driver as driver

from typing import List
from lib.dataset import Dataset
from lib.algorithm import AlgorithmName
from lib.tool import ToolName
from lib.dataset import DatasetValueType
from lib.util import check_output


class DriverSpla(driver.Driver):
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

        output = check_output([
            self.exec_path(AlgorithmName.bfs),
            f"--mtxpath={dataset.path}",
            f"--niters={num_iterations}",
            f"--source={source_vertex}"
        ])

        return DriverSpla._parse_output(output)

    def run_sssp(self,
                 dataset: Dataset,
                 source_vertex: int,
                 num_iterations: int) -> driver.ExecutionResult:

        output = check_output([
            self.exec_path(AlgorithmName.sssp),
            f"--mtxpath={dataset.path}",
            f"--niters={num_iterations}",
            f"--source={source_vertex}"
        ])

        return DriverSpla._parse_output(output)

    def run_tc(self,
               dataset: Dataset,
               num_iterations: int) -> driver.ExecutionResult:

        dir_flag = 'true' if not dataset.get_directed() else 'false'

        output = check_output([
            self.exec_path(AlgorithmName.tc),
            f"--mtxpath={dataset.path}",
            f"--niters={num_iterations}",
            f"--undirected={dir_flag}"
        ])
        return DriverSpla._parse_output(output)

    def run_pr(self,
               dataset: Dataset,
               num_iterations: int) -> driver.ExecutionResult:

        output = check_output([
            self.exec_path(AlgorithmName.pr),
            f"--mtxpath={dataset.path}",
            f"--niters={num_iterations}",
            f"--eps=1e-4"
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
                f"--niters={iterations}",
                f"--source={source}"
            ]
        if algo == AlgorithmName.sssp:
            return [
                str(self.exec_path(AlgorithmName.sssp)),
                f"--mtxpath={dataset.path}",
                f"--niters={iterations}",
                f"--source={source}"
            ]
        if algo == AlgorithmName.tc:
            dir_flag = 'true' if not dataset.get_directed() else 'false'
            return [
                str(self.exec_path(AlgorithmName.tc)),
                f"--mtxpath={dataset.path}",
                f"--niters={iterations}",
                f"--undirected={dir_flag}"
            ]
        if algo == AlgorithmName.pr:
            return [
                str(self.exec_path(AlgorithmName.pr)),
                f"--mtxpath={dataset.path}",
                f"--niters={iterations}",
                f"--eps=1e-4"
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
        lines = output.decode("ASCII").replace("\r", "").split("\n")
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

        return driver.ExecutionResult(warmup, runs)
