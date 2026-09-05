import os
import time

from typing import List

from drivers.driver import ExecutionResult, Driver
from lib.dataset import Dataset
from lib.algorithm import AlgorithmName
from lib.tool import ToolName
from lib.util import check_output


class DriverLaGraph(Driver):
    def can_run_bfs(self, _: Dataset) -> bool:
        return True

    def can_run_sssp(self, _: Dataset) -> bool:
        return True

    def can_run_tc(self, _: Dataset) -> bool:
        return True

    def can_run_pr(self, _: Dataset) -> bool:
        return True

    def run_bfs(self,
                dataset: Dataset,
                source_vertex: int,
                num_iterations: int) -> ExecutionResult:

        with TemporarySourcesFile([source_vertex + 1] * num_iterations) as sources_file:
            output = check_output([
                self.exec_path(AlgorithmName.bfs),
                dataset.path,
                sources_file.name
            ])

            return DriverLaGraph._parse_output(output, "level only", 9, "warmup", 4)

    def run_sssp(self,
                 dataset: Dataset,
                 source_vertex: int,
                 num_iterations: int) -> ExecutionResult:

        with TemporarySourcesFile([source_vertex + 1] * num_iterations) as sources_file:
            output = check_output([
                self.exec_path(AlgorithmName.sssp),
                dataset.path,
                sources_file.name,
                '1'
            ])

            return DriverLaGraph._parse_output(output, "sssp", 8)

    def run_tc(self,
               dataset: Dataset,
               num_iterations: int) -> ExecutionResult:

        output = check_output([
            self.exec_path(AlgorithmName.tc),
            dataset.path
        ])

        return DriverLaGraph._parse_output(output, "trial ", 2, "nthreads: ", 3)

    def run_pr(self,
               dataset: Dataset,
               num_iterations: int) -> ExecutionResult:

        output = check_output([
            self.exec_path(AlgorithmName.pr),
            dataset.path
        ])

        return DriverLaGraph._parse_output(output, "Avg: PR", 4)

    def tool_name(self) -> ToolName:
        return ToolName.lagraph

    def _build_command(self,
                       dataset: Dataset,
                       algo: AlgorithmName,
                       source: int,
                       iterations: int) -> List[str]:
        if algo == AlgorithmName.bfs:
            self.sources_file = TemporarySourcesFile([source + 1] * iterations)
            self.sources_file.__enter__()
            return [
                str(self.exec_path(AlgorithmName.bfs)),
                str(dataset.path),
                self.sources_file.name
            ]
        if algo == AlgorithmName.sssp:
            self.sources_file = TemporarySourcesFile([source + 1] * iterations)
            self.sources_file.__enter__()
            return [
                str(self.exec_path(AlgorithmName.sssp)),
                str(dataset.path),
                self.sources_file.name,
                '1'
            ]
        if algo == AlgorithmName.tc:
            return [str(self.exec_path(AlgorithmName.tc)), str(dataset.path)]
        if algo == AlgorithmName.pr:
            return [str(self.exec_path(AlgorithmName.pr)), str(dataset.path)]
        raise Exception(f"Algorithm {algo} not supported")

    def _cleanup_profile_command(self) -> None:
        sources_file = getattr(self, 'sources_file', None)
        if sources_file is not None:
            sources_file.__exit__(None, None, None)
            self.sources_file = None

    def _parse_profiled_output(self,
                               dataset: Dataset,
                               algo: AlgorithmName,
                               raw_output: str,
                               iterations: int) -> ExecutionResult:
        if raw_output is None:
            return ExecutionResult(warm_up=0.0, times=[0.0])

        output = raw_output.encode('ASCII', errors='ignore')
        if algo == AlgorithmName.bfs:
            result = DriverLaGraph._parse_output(output, "level only", 9, "warmup", 4)
            if result.times:
                return result

            avg_lines = lines_startswith(raw_output.split("\n"), "Avg: BFS")
            if avg_lines:
                result.times = [float(tokenize(avg_lines[0])[7]) * 1000]
            return result
        if algo == AlgorithmName.sssp:
            return DriverLaGraph._parse_output(output, "sssp", 8)
        if algo == AlgorithmName.tc:
            return DriverLaGraph._parse_output(output, "trial ", 2, "nthreads: ", 3)
        if algo == AlgorithmName.pr:
            return DriverLaGraph._parse_output(output, "Avg: PR", 4)
        return ExecutionResult(warm_up=0.0, times=[0.0])

    @staticmethod
    def _parse_output(output: bytes,
                      trial_line_start: str,
                      trial_line_token: int,
                      warmup_line_start: str = None,
                      warmup_line_token: int = None):
        time_factor = 1000
        lines = output.decode("ASCII").split("\n")
        trials = []
        for trial_line in lines_startswith(lines, trial_line_start):
            trials.append(float(tokenize(trial_line)[
                          trial_line_token]) * time_factor)
        warmup = 0
        if warmup_line_start is not None:
            warmup_lines = lines_startswith(lines, warmup_line_start)
            if warmup_lines:
                warmup = float(tokenize(warmup_lines[0])[
                               warmup_line_token]) * time_factor
        return ExecutionResult(warmup, trials)


def lines_startswith(lines: List[str], token) -> List[str]:
    return list(filter(lambda s: s.startswith(token), lines))


def tokenize(line: str) -> List[str]:
    return list(filter(lambda x: x, line.split(' ')))


class TemporarySourcesFile():
    def __init__(self, sources: List[int]):
        self.name = f'sources_{str(time.ctime())}_.mtx'
        self.freeze = False
        self.fd = None
        self.sources = sources

    def __enter__(self):
        with open(self.name, 'wb') as sources_file:
            sources_file.write(make_sources_content(self.sources))
        return self

    def __exit__(self, type, value, traceback):
        if not self.freeze:
            os.remove(self.name)


def make_sources_content(sources: List[int]):
    n = len(sources)
    sources = '\n'.join(map(str, sources))

    return f'''
%%MatrixMarket matrix array real general
%-------------------------------------------------------------------------------
% Temporary sources file
%-------------------------------------------------------------------------------
{n} 1
{sources}
'''.encode('ascii')
