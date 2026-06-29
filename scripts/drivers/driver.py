import abc
import statistics

from pathlib import Path
from dataclasses import dataclass
from typing import List

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

    def avg(self):
        return statistics.mean(self.times) if self.times else 0.0

    def median(self):
        return statistics.median(self.times) if self.times else 0.0

    def stdev(self):
        return statistics.stdev(self.times) if len(self.times) >= 2 else 0.0

    def brief_str(self) -> str:
        return f'warm_up={self.warm_up:.2f}ms, avg={self.avg():.2f}ms, median={self.median():.2f}ms, stdev={self.stdev():.2f}'

    def __str__(self) -> str:
        return self.brief_str()

    def __repr__(self) -> str:
        return self.brief_str()


class Driver:
    def __init__(self):
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
                          f'soure={source}' if algo in [AlgorithmName.bfs, AlgorithmName.sssp] else '')

        result: ExecutionResult = None

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
