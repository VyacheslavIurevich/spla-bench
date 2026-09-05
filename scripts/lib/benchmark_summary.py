import csv
import html
import json
import os

from typing import Dict, List, Tuple, Callable
from enum import Enum
from pathlib import Path
from datetime import datetime

from lib.tool import ToolName
from lib.dataset import Dataset
from lib.algorithm import AlgorithmName
from lib.util import print_status
from drivers.driver import ExecutionResult
from profiling.profiler_base import NumericMetric


"""

datatset | tool_1 | tool_2 | ... | tool_n
---------|--------|--------|-----|-------
name_1   | ...    | ...    | ... | ...
name_2   | ...    | ...    | ... | ...
...

"""


class OutputFormat(Enum):
    raw = 'txt'
    csv = 'csv'

    def __str__(self) -> str:
        return self.value

    def extension(self):
        return f'.{self.value}'


def print_all_results(result: ExecutionResult):
    return result.brief_str()


def print_median(result: ExecutionResult):
    return str(result.median())


class ResultsPrinter(Enum):
    all = 'all'
    median = 'median'

    def __str__(self) -> str:
        return self.value

    def print(self, result: ExecutionResult) -> str:
        match_printer = {
            ResultsPrinter.all: print_all_results,
            ResultsPrinter.median: print_median
        }
        return match_printer[self](result)


class BenchmarkSummary:
    def __init__(self):
        self.measurements: Dict[AlgorithmName,
                                Dict[str, Dict[ToolName, ExecutionResult]]] = {}

    def add_measurement(self,
                        tool: ToolName,
                        dataset: Dataset,
                        algo: AlgorithmName,
                        result: ExecutionResult):
        (
            self.measurements
            .setdefault(algo, {})
            .setdefault(dataset.name, {})
            .setdefault(tool, result)
        )

    def algorithms(self) -> List[AlgorithmName]:
        return list(self.measurements.keys())

    def results_per_algorithm(self) -> List[Tuple[AlgorithmName, Dict[str, Dict[ToolName, ExecutionResult]]]]:
        return list(self.measurements.items())

    def results_per_algorithm_dataset(self) -> List[Tuple[AlgorithmName, str, Dict[ToolName, ExecutionResult]]]:
        items = []
        for algo, results in self.results_per_algorithm():
            items.extend(
                map(lambda item: (algo, item[0], item[1]), results.items()))
        return items

    def measurements_list(self) -> List[Tuple[AlgorithmName, str, ToolName, ExecutionResult]]:
        items = []
        for algo, tool_by_dataset in self.measurements.items():
            for dataset_name, result_by_tool in tool_by_dataset.items():
                for tool, result in result_by_tool.items():
                    items.append((algo, dataset_name, tool, result))
        return items

    @staticmethod
    def prepare_output_dir(output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / datetime.ctime(datetime.now())
        output.mkdir(exist_ok=False)
        recent_link = output_dir / 'recent'
        if recent_link.exists() or recent_link.is_symlink():
            recent_link.unlink()
        os.symlink(output, recent_link, target_is_directory=True)

        print_status('summary', 'dump', f'symlink: {recent_link}, original: {output}')
        return output

    def dump(self,
             format: OutputFormat,
             output_dir: Path,
             results_printer: Callable,
             run_output_dir: Path = None):
        output = run_output_dir or self.prepare_output_dir(output_dir)

        if format == OutputFormat.raw:
            def process_result(t):
                algo, dataset, tool, result = t
                return f'algo: {algo}, dataset: {dataset}, tool: {tool}, result: {results_printer.print(result)}'

            processed_measurements = list(
                map(process_result, self.measurements_list()))
            output_file_name = (output / 'raw').with_suffix(format.extension())
            with output_file_name.open('w') as out_file:
                print(*processed_measurements, sep='\n', file=out_file)

        elif format == OutputFormat.csv:
            for algo, algo_results in self.results_per_algorithm():
                algo_output = (
                    output / str(algo)
                ).with_suffix(format.extension())

                if algo_results == {}:
                    continue
                all_tools = map(
                    str, list(list(algo_results.values())[0].keys()))
                with algo_output.open('w') as algo_file:
                    csv_writer = csv.DictWriter(
                        algo_file, ['dataset', *all_tools])
                    csv_writer.writeheader()
                    for dataset_name, dataset_results in algo_results.items():
                        csv_row = {}
                        for tool, result in dataset_results.items():
                            csv_row[str(tool)] = results_printer.print(
                                result)
                        csv_row['dataset'] = dataset_name
                        csv_writer.writerow(csv_row)

        else:
            raise Exception(f'Format {format.name} is not supported')

        self._dump_json(output)
        self._dump_timing_charts(output)

    def _dump_json(self, output: Path) -> None:
        results = []
        for algo, dataset, tool, result in self.measurements_list():
            timing = NumericMetric([float(value) for value in result.times], 'ms')
            results.append({
                'algorithm': str(algo),
                'dataset': dataset,
                'tool': str(tool),
                'runs': len(result.times),
                'warm_up_ms': result.warm_up,
                'execution_time': timing.to_dict(),
                'profiling': result.profiling.to_dict() if result.profiling else None,
            })

        output_file = output / 'benchmark_summary.json'
        with output_file.open('w') as out_file:
            json.dump({'results': results}, out_file, indent=2)
        print_status('summary', 'json', output_file)

    def _dump_timing_charts(self, output: Path) -> None:
        charts_dir = output / 'charts'
        charts_dir.mkdir(exist_ok=True)
        chart_files = []

        for algo, algo_results in self.results_per_algorithm():
            rows = []
            for dataset, tool_results in algo_results.items():
                for tool, result in tool_results.items():
                    metric = NumericMetric(
                        [float(value) for value in result.times], 'ms')
                    rows.append((f'{dataset} / {tool}', metric))

            for statistic in ('mean', 'median'):
                chart_file = charts_dir / f'{algo}_{statistic}.svg'
                self._write_svg_chart(
                    chart_file, f'{algo}: execution time ({statistic})',
                    rows, statistic)
                chart_files.append(chart_file)

        index_file = charts_dir / 'index.html'
        with index_file.open('w') as out_file:
            out_file.write('<!doctype html><meta charset="utf-8">')
            out_file.write('<title>Benchmark timing charts</title>')
            out_file.write('<h1>Benchmark timing charts</h1>')
            for chart_file in chart_files:
                out_file.write(
                    f'<h2>{html.escape(chart_file.stem)}</h2>'
                    f'<img src="{html.escape(chart_file.name)}" '
                    f'style="max-width:100%;height:auto">')
        print_status('summary', 'charts', index_file)

    @staticmethod
    def _write_svg_chart(output_file: Path,
                         title: str,
                         rows: List[Tuple[str, NumericMetric]],
                         statistic: str) -> None:
        width = max(800, 140 + len(rows) * 90)
        height = 560
        left, top, bottom = 80, 60, 180
        plot_width = width - left - 30
        plot_height = height - top - bottom
        values = [
            metric.mean() if statistic == 'mean' else metric.median()
            for _, metric in rows
        ]
        max_value = max(values, default=0.0) or 1.0
        slot_width = plot_width / max(len(rows), 1)
        bar_width = max(12, slot_width * 0.65)

        svg = [
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<style>text{font-family:sans-serif;fill:#222}'
            '.axis{stroke:#555;stroke-width:1}.bar{fill:#4c78a8}'
            '.variance{font-size:10px}.label{font-size:11px}</style>',
            f'<text x="{width / 2}" y="30" text-anchor="middle" '
            f'font-size="18">{html.escape(title)}</text>',
            f'<line class="axis" x1="{left}" y1="{top}" '
            f'x2="{left}" y2="{top + plot_height}"/>',
            f'<line class="axis" x1="{left}" y1="{top + plot_height}" '
            f'x2="{left + plot_width}" y2="{top + plot_height}"/>',
            f'<text x="18" y="{top + plot_height / 2}" '
            f'transform="rotate(-90 18 {top + plot_height / 2})" '
            f'text-anchor="middle">time, ms</text>',
        ]

        for index, ((label, metric), value) in enumerate(zip(rows, values)):
            x = left + index * slot_width + (slot_width - bar_width) / 2
            bar_height = value / max_value * plot_height
            y = top + plot_height - bar_height
            svg.extend([
                f'<rect class="bar" x="{x:.2f}" y="{y:.2f}" '
                f'width="{bar_width:.2f}" height="{bar_height:.2f}"/>',
                f'<text x="{x + bar_width / 2:.2f}" y="{max(top + 12, y - 16):.2f}" '
                f'text-anchor="middle" font-size="11">{value:.3g} ms</text>',
                f'<text class="variance" x="{x + bar_width / 2:.2f}" '
                f'y="{max(top + 24, y - 4):.2f}" text-anchor="middle">'
                f'variance={metric.variance():.3g}</text>',
                f'<text class="label" x="{x + bar_width / 2:.2f}" '
                f'y="{top + plot_height + 16}" text-anchor="end" '
                f'transform="rotate(-55 {x + bar_width / 2:.2f} '
                f'{top + plot_height + 16})">{html.escape(label)}</text>',
            ])

        svg.append('</svg>')
        output_file.write_text('\n'.join(svg))
