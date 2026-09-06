import abc
import statistics

from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional

import lib.util as util
import config as config

from lib.dataset import Dataset
from build.build import build_tool
from lib.tool import ToolName
from lib.algorithm import AlgorithmName


@dataclass
class ExecutionResult:
    """
    Result of the execution of the single algorithm benchmark run
    """
    warm_up: int
    times: List[int]
    profiling: Optional[object] = None

    def avg(self):
        return statistics.mean(self.times) if self.times else 0.0

    def median(self):
        return statistics.median(self.times) if self.times else 0.0

    def stdev(self):
        return statistics.stdev(self.times) if len(self.times) >= 2 else 0.0

    def brief_str(self) -> str:
        result = (
            f'runs={len(self.times)}, warm_up={self.warm_up:.2f}ms, '
            f'avg={self.avg():.2f}ms, median={self.median():.2f}ms, '
            f'stdev={self.stdev():.2f}'
        )
        if self.profiling and self.profiling.has_cpu_data():
            result += ', profile=cpu'
        if self.profiling and self.profiling.has_gpu_data():
            result += ', profile=gpu'
        if self.profiling and self.profiling.has_flamegraph():
            result += ', flamegraph'
        if self.profiling and self.profiling.numeric_metrics:
            result += f', metrics: {self.profiling.metrics_brief_str()}'
        return result

    def __str__(self) -> str:
        return self.brief_str()

    def __repr__(self) -> str:
        return self.brief_str()


class Driver:
    def __init__(self, profiler_manager: Optional[object] = None):
        self.profiler_manager = profiler_manager
        self.build()

    """
    Base class for any driver, which is responsible for running
    algorithm benchmarks for third-party tools from stand-alone
    executable files.

    Algorithms:
        * bfs
        * sssp
        * tc
        * [future] cc
        * [future] page rank
    """

    @abc.abstractmethod
    def can_run_bfs(self, dataset: Dataset) -> bool:
        return False

    @abc.abstractmethod
    def can_run_sssp(self, dataset: Dataset) -> bool:
        return False

    @abc.abstractmethod
    def can_run_tc(self, dataset: Dataset) -> bool:
        return False

    @abc.abstractmethod
    def can_run_pr(self, dataset: Dataset) -> bool:
        return False

    @abc.abstractmethod
    def run_bfs(self,
                dataset: Dataset,
                source_vertex: int,
                num_iterations: int) -> ExecutionResult:
        """
        Run bfs algorithm benchmark.

        :param dataset: Dataset with its properties to run on
        :param source_vertex: Source vertex to start algorithm
        :param num_iterations: Number of iteration to run
        :return: execution results
        """
        pass

    @abc.abstractmethod
    def run_sssp(self,
                 dataset: Dataset,
                 source_vertex: int,
                 num_iterations: int) -> ExecutionResult:
        """
        Run sssp algorithm benchmark.

        :param dataset: Dataset with its properties to run on
        :param source_vertex: Source vertex to start algorithm
        :param num_iterations: Number of iteration to run
        :return: execution results
        """
        pass

    @abc.abstractmethod
    def run_tc(self,
               dataset: Dataset,
               num_iterations: int) -> ExecutionResult:
        """
        Run tc algorithm benchmark.

        :param dataset: Dataset with its properties to run on
        :param num_iterations: Number of iteration to run
        :return: execution results
        """
        pass

    @abc.abstractmethod
    def run_pr(self,
               dataset: Dataset,
               num_iterations: int) -> ExecutionResult:
        """
        Run pagerank algorithm benchmark.

        :param dataset: Dataset with its properties to run on
        :param num_iterations: Number of iteration to run
        :return: execution results
        """
        pass

    @abc.abstractmethod
    def tool_name(self) -> ToolName:
        """
        :return: Name of the underhood tool
        """
        pass

    def exec_path(self, algo: AlgorithmName) -> Path:
        return config.tool_algo_exec_path(self.tool_name(), algo)

    def print_status(self, status: str, *args):
        util.print_status(self.tool_name(), status, *args)

    def build(self) -> bool:
        build_tool(self.tool_name())

    def can_run(self, dataset: Dataset, algo: AlgorithmName) -> bool:
        can_run = {
            AlgorithmName.bfs: self.can_run_bfs,
            AlgorithmName.sssp: self.can_run_sssp,
            AlgorithmName.tc: self.can_run_tc,
            AlgorithmName.pr: self.can_run_pr
        }
        return can_run[algo](dataset)

    def run(self, dataset: Dataset, algo: AlgorithmName) -> ExecutionResult:
        if not self.can_run(dataset, algo):
            raise Exception(
                f'Algorithm {str(algo)} can not be run on the dataset {dataset.name}')

        dataset_category = dataset.get_category()

        iterations = dataset_category.iterations()

        if algo in [AlgorithmName.bfs, AlgorithmName.sssp]:
            source = config.find_best_source(
                str(dataset.path), str(dataset.name), is_directed=dataset.get_directed()
            )
        else:
            source = config.DEFAULT_SOURCE

        self.print_status('run',
                          f'begin {algo.name}',
                          f'iterations={iterations}',
                          f'source={source}' if algo in [AlgorithmName.bfs, AlgorithmName.sssp] else '')

        result: ExecutionResult = None

        if self.profiler_manager:
            result = self._run_with_profiling(dataset, algo, source, iterations)
        else:
            if algo == AlgorithmName.bfs:
                result = self.run_bfs(dataset, source, iterations)
            elif algo == AlgorithmName.sssp:
                result = self.run_sssp(dataset, source, iterations)
            elif algo == AlgorithmName.tc:
                result = self.run_tc(dataset, iterations)
            elif algo == AlgorithmName.pr:
                result = self.run_pr(dataset, iterations)

        self.print_status(
            'run', f'finish {str(algo.name)}', result.brief_str())

        return result

    def _run_with_profiling(self,
                            dataset: Dataset,
                            algo: AlgorithmName,
                            source: int,
                            iterations: int) -> ExecutionResult:
        if self.profiler_manager.profiles_individual_flamegraph_runs():
            return self._run_with_median_flamegraph(
                dataset, algo, source, iterations)

        command = self._build_command(dataset, algo, source, iterations)
        try:
            profiling_result = self.profiler_manager.run_profiling(
                command, self.tool_name(), dataset, algo, iterations)
        finally:
            self._cleanup_profile_command()

        result = self._parse_profiled_output(
            dataset, algo, profiling_result.raw_output, iterations)
        profiling_result.add_metric('benchmark.time', result.times, 'ms')
        profiling_result.add_metric('benchmark.warm_up', [result.warm_up], 'ms')
        profiling_result.metadata['completed_runs'] = len(result.times)
        self.profiler_manager.write_profile_summary(profiling_result)
        result.profiling = profiling_result
        return result

    def _run_with_median_flamegraph(self,
                                    dataset: Dataset,
                                    algo: AlgorithmName,
                                    source: int,
                                    iterations: int) -> ExecutionResult:
        candidates = []
        candidate_results = []
        valid_timings = []

        for run_index in range(1, iterations + 1):
            command = self._build_command(dataset, algo, source, 1)
            try:
                candidate = self.profiler_manager.run_flamegraph_candidate(
                    command,
                    self.tool_name(),
                    dataset,
                    algo,
                    run_index)
                candidate_result = self._parse_profiled_output(
                    dataset, algo, candidate.raw_output, 1)
            finally:
                self._cleanup_profile_command()

            candidates.append(candidate)
            candidate_results.append(candidate_result)
            if candidate_result.times:
                process_time = candidate_result.avg()
                valid_timings.append((len(candidates) - 1, process_time))
                self.print_status(
                    'profile run',
                    f'dataset={dataset.name}',
                    f'run={run_index}/{iterations}',
                    f'execution_time={process_time:.2f}ms')
            else:
                self.print_status(
                    'profile run',
                    f'dataset={dataset.name}',
                    f'run={run_index}/{iterations}',
                    'execution_time=unavailable')

        if valid_timings:
            median_time = statistics.median(
                timing for _, timing in valid_timings)
            selected_index, selected_time = min(
                valid_timings,
                key=lambda item: abs(item[1] - median_time))
            times = [timing for _, timing in valid_timings]
            warm_up = candidate_results[selected_index].warm_up
        else:
            median_time = None
            selected_time = None
            selected_index = None
            times = []
            warm_up = 0.0

        profiling_result = self.profiler_manager.finalize_flamegraph_candidates(
            candidates,
            selected_index,
            self.tool_name(),
            dataset,
            algo,
            iterations)
        profiling_result.metadata.update({
            'completed_runs': len(times),
            'representative_execution_time_ms': selected_time,
            'median_execution_time_ms': median_time,
        })
        profiling_result.add_metric('benchmark.time', times, 'ms')
        profiling_result.add_metric('benchmark.warm_up', [warm_up], 'ms')
        profiling_result.add_metric(
            'cpu.benchmark_iterations', [iterations], 'runs')
        self.profiler_manager.write_profile_summary(profiling_result)

        result = ExecutionResult(warm_up=warm_up, times=times)
        result.profiling = profiling_result
        return result

    def _build_command(self,
                       dataset: Dataset,
                       algo: AlgorithmName,
                       source: int,
                       iterations: int) -> List[str]:
        raise NotImplementedError("Subclasses must implement _build_command")

    def _cleanup_profile_command(self) -> None:
        pass

    def _parse_profiled_output(self,
                               dataset: Dataset,
                               algo: AlgorithmName,
                               raw_output: Optional[str],
                               iterations: int) -> ExecutionResult:
        return ExecutionResult(warm_up=0.0, times=[])
