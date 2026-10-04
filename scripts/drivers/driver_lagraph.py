import os
import time

from typing import List

from drivers.driver import ExecutionResult, Driver
from lib.dataset import Dataset
from lib.algorithm import AlgorithmName
from lib.tool import ToolName


class DriverLaGraph(Driver):
    @staticmethod
    def _discard_first(
        result: ExecutionResult,
        measured_runs: int,
    ) -> ExecutionResult:
        if len(result.times) < measured_runs + 1:
            return result
        result.warm_up = result.times[0]
        result.times = result.times[1:measured_runs + 1]
        return result

    def _collect_stock_trials(
        self,
        command: List,
        line_start: str,
        time_token: int,
        measured_runs: int,
    ) -> ExecutionResult:
        samples = []
        while len(samples) < measured_runs + 1:
            output = self.check_output(command)
            parsed = self._parse_output(output, line_start, time_token)
            if not parsed.times:
                raise RuntimeError(
                    f"LAGraph command produced no '{line_start}' timings"
                )
            samples.extend(parsed.times)
        return ExecutionResult(samples[0], samples[1:measured_runs + 1])

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

        with TemporarySourcesFile([source_vertex + 1] * (num_iterations + 1)) as sources_file:
            output = self.check_output([
                self.exec_path(AlgorithmName.bfs),
                dataset.path,
                sources_file.name
            ])

            return self._discard_first(
                self._parse_output(output, "parent only", 9),
                num_iterations,
            )

    def run_sssp(self,
                 dataset: Dataset,
                 source_vertex: int,
                 num_iterations: int) -> ExecutionResult:

        with TemporarySourcesFile([source_vertex + 1] * (num_iterations + 1)) as sources_file:
            output = self.check_output([
                self.exec_path(AlgorithmName.sssp),
                dataset.path,
                sources_file.name,
                '1'
            ])

            return self._discard_first(
                self._parse_output(output, "sssp", 8),
                num_iterations,
            )

    def run_tc(self,
               dataset: Dataset,
               num_iterations: int) -> ExecutionResult:

        return self._collect_stock_trials(
            [self.exec_path(AlgorithmName.tc), dataset.path],
            "trial ",
            2,
            num_iterations,
        )

    def run_pr(self,
               dataset: Dataset,
               num_iterations: int) -> ExecutionResult:

        return self._collect_stock_trials(
            [self.exec_path(AlgorithmName.pr), dataset.path],
            "trial:",
            3,
            num_iterations,
        )

    def tool_name(self) -> ToolName:
        return ToolName.lagraph

    def _build_command(self,
                       dataset: Dataset,
                       algo: AlgorithmName,
                       source: int,
                       iterations: int) -> List[str]:
        if algo == AlgorithmName.bfs:
            self.sources_file = TemporarySourcesFile(
                [source + 1] * (iterations + 1)
            )
            self.sources_file.__enter__()
            return [
                str(self.exec_path(AlgorithmName.bfs)),
                str(dataset.path),
                self.sources_file.name
            ]
        if algo == AlgorithmName.sssp:
            self.sources_file = TemporarySourcesFile(
                [source + 1] * (iterations + 1)
            )
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
            return ExecutionResult(warm_up=0.0, times=[])

        output = raw_output.encode('ASCII', errors='ignore')
        if algo == AlgorithmName.bfs:
            return self._discard_first(
                self._parse_output(output, "parent only", 9),
                iterations,
            )
        if algo == AlgorithmName.sssp:
            return self._discard_first(
                self._parse_output(output, "sssp", 8),
                iterations,
            )
        if algo == AlgorithmName.tc:
            return self._discard_first(
                self._parse_output(output, "trial ", 2),
                iterations,
            )
        if algo == AlgorithmName.pr:
            return self._discard_first(
                self._parse_output(output, "trial:", 3),
                iterations,
            )
        return ExecutionResult(warm_up=0.0, times=[])

    @staticmethod
    def _parse_output(output: bytes,
                      trial_line_start: str,
                      trial_line_token: int):
        time_factor = 1000
        lines = output.decode("ASCII").split("\n")
        trials = []
        for trial_line in lines_startswith(lines, trial_line_start):
            trials.append(float(tokenize(trial_line)[
                          trial_line_token]) * time_factor)
        return ExecutionResult(0, trials)


def lines_startswith(lines: List[str], token) -> List[str]:
    return list(filter(lambda s: s.startswith(token), lines))


def tokenize(line: str) -> List[str]:
    return list(filter(lambda x: x, line.split(' ')))


class TemporarySourcesFile():
    def __init__(self, sources: List[int]):
        self.name = f'sources_{str(time.ctime())}_.mtx'
        self.sources = sources

    def __enter__(self):
        with open(self.name, 'wb') as sources_file:
            sources_file.write(make_sources_content(self.sources))
        return self

    def __exit__(self, type, value, traceback):
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
