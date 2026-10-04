# Branch Changes Relative to `main`

This document describes the cumulative state of the current `spla-bench` branch
relative to the `main` branch, including committed changes and local changes to
the experimental methodology.

The current goal of the branch is to run and profile BFS, SSSP, triangle
counting, and PageRank on LAGraph/CPU and spla/GPU, and to save the results in a
format suitable for subsequent analysis.

## 1. General Experimental Methodology

The main experiment now compares the implementations available out of the box:

- the algorithm sources in `deps/lagraph` and `deps/spla` are not modified;
- LAGraph is treated as the CPU implementation;
- spla is run only through the GPU backend;
- the libraries' internal algorithmic differences are preserved;
- the main dataset contains only undirected graphs;
- one warm-up run of the same implementation is performed before measurement;
- the warm-up is excluded from the statistics;
- individual timings, commands, configuration, and raw output are retained.

This is a comparison of ready-to-use library implementations, not an execution
of the same computational kernel on different devices.

The following differences are preserved:

- LAGraph BFS constructs parents, whereas spla BFS constructs levels;
- LAGraph TC uses its own method selection and sorting;
- spla TC uses its own masked implementation;
- LAGraph PageRank uses the GAP variant and an L1 stopping criterion;
- spla PageRank uses its own implementation and an L2 stopping criterion.

These differences are considered part of the libraries' standard behavior and
are recorded in the result metadata.

## 2. Dependency Updates

The spla submodule URL was changed:

- previously: `JetBrains-Research/spla`;
- now: `SparseLinearAlgebra/spla`.

The spla submodule was updated from revision `a1877e7` to `b81d1e2`.

The LAGraph URL was changed to the form ending in `.git`.

The Gunrock and GraphBLAST revisions were not changed.

The local `deps/suitesparse_graphblas/` directory is a clone/output of a local
SuiteSparse GraphBLAS build and must not be committed as project source code.

## 3. Datasets

The old small matrix set was replaced with graphs from the SuiteSparse Matrix
Collection, downloaded through the `graphs-theory-datasets` repository.

Links were added for:

- `coAuthorsCiteseer`;
- `coPapersDBLP`;
- `amazon-2008`;
- `hollywood-2009`;
- `belgium_osm`;
- `roadNet-CA`;
- `com-Orkut`;
- `cit-Patents`;
- `rgg_n_2_22_s0`;
- `soc-LiveJournal1`;
- `indochina-2004`;
- `rgg_n_2_23_s0`;
- `road_central`.

The main `BENCHMARK_DATASETS` list is restricted to undirected graphs:

- `coAuthorsCiteseer`;
- `coPapersDBLP`;
- `belgium_osm`;
- `roadNet-CA`;
- `com-Orkut`;
- `rgg_n_2_22_s0`;
- `rgg_n_2_23_s0`;
- `road_central`.

The directed graphs `amazon-2008`, `cit-Patents`, and `soc-LiveJournal1` are
excluded from the main experiment because the standard spla examples
symmetrize Matrix Market input. They should be investigated separately using
an explicitly agreed-upon loading policy.

`hollywood-2009` is currently disabled because LAGraph BFS fails on it, while
`indochina-2004` previously did not finish within a practical amount of time.

The `extra_large` category now uses three measured runs.

## 4. Source Vertex Selection

Automatic source selection was added for BFS and SSSP:

1. the matrix is read with SciPy;
2. the largest connected component is found;
3. the vertex whose degree is closest to the median is selected from that component;
4. the result is cached only for the lifetime of the current process.

For a directed graph, the largest strongly connected component was used.
The undirected variant is used for the current main dataset.

## 5. Dataset Handling

In `scripts/lib/dataset.py`:

- handling of archives containing multiple `.mtx` files was fixed;
- archive contents are sorted to make file selection reproducible;
- an unknown value type is recomputed instead of storing `unknown`;
- `get_vertices()` and `brief_info()` were added;
- `n`, `nnz`, directedness, value type, and size category were added to the
  diagnostic output.

## 6. PageRank Support

`pr` was added to the algorithm list.

Executable paths were added:

- LAGraph: `src/benchmark/gappagerank_demo`;
- spla: `pr`.

The following were implemented for PageRank:

- availability checks in the drivers;
- execution of the standard binary;
- parsing individual LAGraph `trial:` lines;
- parsing spla `gpu(ms):` output;
- warm-up and retention of the configured number of measurements;
- a description of the differences between stopping criteria in metadata.

The standard termination criteria are not unified. PageRank results are
therefore interpreted as the runtime of each implementation with its own
criterion, rather than as the cost of a fixed number of identical iterations.

## 7. GPU-Only spla Mode

All spla commands receive:

```text
--run-cpu=false
--run-ref=false
--run-gpu=true
```

This excludes the sequential CPU and reference variants from the GPU benchmark
process. This is especially important for TC on large graphs, where the
reference implementation could consume most of the time or effectively never
finish.

These parameters are applied to BFS, SSSP, TC, and PageRank both during normal
execution and when constructing the profiling command.

## 8. Warm-Up and Number of Measurements

spla receives `--niters=N+1`:

- the first GPU sample is treated as the warm-up;
- the next `N` samples are retained as measurements.

For standard LAGraph:

- BFS and SSSP receive a file containing `N+1` identical sources;
- the first measured trial is discarded;
- BFS is parsed from `parent only` lines produced by the standard `bfs_demo`;
- TC and PageRank are run as many times as needed to collect `N+1` standard
  trials;
- the first collected trial is treated as the warm-up;
- the next `N` trials are retained.

A strict check is performed after execution:

```text
number of measured samples == configured_measured_runs
```

Any mismatch is treated as an error, not as a partial success.

## 9. Drivers

### Common Driver

`ExecutionResult` was extended with the following fields:

- `profiling`;
- `metadata`;
- `raw_output`.

The common driver now:

- records every executed command;
- combines stdout and stderr;
- determines the dependency revision if `deps` is a standalone Git worktree;
- records the backend, algorithm, dataset, source, and repetition parameters;
- checks the number of measurements;
- passes raw output to the final summary.

### LAGraph

Working BFS, SSSP, TC, and PageRank drivers were implemented.

The current methodology uses unmodified demonstration programs:

- BFS — `parent only` lines;
- SSSP — `sssp` lines;
- TC — `trial` lines;
- PageRank — `trial:` lines.

### spla

All four algorithms are considered available for supported datasets.

The parser:

- uses `gpu(ms):` preferentially;
- retains the first GPU sample as the warm-up;
- uses the remaining samples as measurements;
- retains CPU timing only as a fallback for parsing old output;
- records the `env:` platform, device, vendor, `mcu`, `wave`, and `mwgs`;
- records counts of known OpenCL error strings from the same stdout.

## 10. Profiling

The `scripts/profiling/` package was added.

### Core Entities

`profiler_base.py` contains:

- the profiler interface;
- `NumericMetric`;
- `ProfileResult`;
- serialization of metrics and artifacts.

For numeric metrics, the following are calculated:

- raw samples;
- mean;
- median;
- standard deviation;
- variance;
- minimum and maximum;
- the Shapiro–Wilk test result when there are enough samples.

### CPU Profiling

`cpu_profiler.py` uses Linux `perf`:

- `perf record` for the call graph;
- `perf stat` for hardware counters;
- retention of `.perf` files;
- retention of folded stacks;
- collection of cycles, instructions, cache misses, LLC misses, and branch misses.

### Flamegraph

`flamegraph.py`:

- uses Brendan Gregg's FlameGraph tools;
- clones them into `~/.spla-bench/flamegraph` if no local copy is available;
- converts perf script output into folded stacks;
- creates SVG and interactive HTML.

### Profiling Management

`profiler_manager.py` coordinates:

- the CPU call graph;
- hardware counters;
- flamegraph generation;
- JSON summary output.

In flamegraph mode, separate profiled processes are executed. The run whose
time is closest to the median is selected for visualization.

Hardware counters may be collected in a separate additional pass and do not
necessarily correspond to the same process from which the main timing was
obtained.

## 11. Benchmark CLI

The following profiling options were added:

- `--cpu-profile` — separate `perf stat` pass (hardware counters);
- `--flamegraph` — per-run `perf record` callgraphs and flamegraph SVG/HTML.

Use `--cpu-profile` together with `--flamegraph` on LAGraph when both counters
and callgraphs are needed. There is no combined “enable everything” shortcut flag.

For spla, `--flamegraph` uses the same CPU `perf record` path on the benchmark
process (host code, OpenCL runtime, synchronization). It does not show individual
OpenCL kernels. GPU device fields and OpenCL errors are parsed from the same
spla stdout as the timings and do not require a separate profiler.

Parsing of `--format` was fixed.

The output path is converted to `Path`, and the directory for the specific run
is created before the profilers are initialized.

The console displays:

- the tool/backend mapping;
- dataset parameters;
- the configured number of repetitions;
- the start and end of each measurement;
- the actual number of parsed samples.

## 12. Result Structure

A timestamped directory and a `recent` symlink are created for each run.

The symlink now points to the child timestamped directory name relative to its
own directory and does not duplicate the parent path.

The following are created:

- a CSV or TXT file with the main summary;
- `benchmark_summary.json`;
- `logs/`;
- `charts/`;
- `profiling/`, if profiling is enabled.

### `benchmark_summary.json`

For each tool/algorithm/dataset combination, the following are retained:

- the number of measured runs;
- the warm-up;
- all timing samples;
- aggregated statistics;
- the profiling summary;
- experiment metadata.

Metadata contains:

- the tool and backend;
- the dependency revision;
- the algorithm;
- the dataset and its path;
- input `n` and `nnz`;
- directed/undirected;
- the BFS/SSSP source vertex;
- the configured number of measurements;
- the number of warm-up runs;
- `OMP_NUM_THREADS`;
- full commands;
- for spla, the `env:` device description and OpenCL error counts;
- the path to the raw output.

### Raw output

The complete combined stdout/stderr for each measurement is saved to:

```text
logs/{tool}_{algorithm}_{dataset}.log
```

This makes it possible to recheck the number of trials, the selected method,
and library messages after the experiment has completed.

### Charts

SVG charts are generated automatically:

- by mean time;
- by median;
- with variance labels.

`charts/index.html` contains a consolidated list of generated images.

## 13. Building LAGraph and SuiteSparse

The SuiteSparse GraphBLAS integration was fixed:

- the `suitesparse_graphblas` name was corrected;
- a build directory is created before invoking CMake;
- the selected GraphBLAS acquisition method is taken into account;
- include/library paths are passed to CMake as strings;
- separate `build_local`, `build_build`, and `build_download` directories are
  used;
- the `deps/lagraph/build` symlink is created safely and is not overwritten
  unconditionally;
- a typo in `SuitesparseMethod.download` was fixed.

The build error message now lists the specific missing targets.

## 14. Changed Files

The following files differ from `main`:

- `.gitmodules`;
- `README.md`;
- `deps/spla`;
- `scripts/benchmark.py`;
- `scripts/build/build.py`;
- `scripts/build/lagraph.py`;
- `scripts/config.py`;
- `scripts/drivers/driver.py`;
- `scripts/drivers/driver_lagraph.py`;
- `scripts/drivers/driver_spla.py`;
- `scripts/lib/algorithm.py`;
- `scripts/lib/benchmark_summary.py`;
- `scripts/lib/dataset.py`.

The following files were added:

- `scripts/profiling/__init__.py`;
- `scripts/profiling/profiler_base.py`;
- `scripts/profiling/cpu_profiler.py`;
- `scripts/profiling/flamegraph.py`;
- `scripts/profiling/profiler_manager.py`.

## 15. Known Limitations

- The main experiment deliberately compares different standard implementations,
  so not every timing ratio can be interpreted as the pure speedup of a single
  algorithmic kernel.
- PageRank uses different internal stopping norms.
- spla GPU device fields come from the library `env:` line, not from a separate
  OpenCL kernel profiler.
- The strict parser terminates the run with an error if the output format of a
  third-party demonstration program changes.
- Gunrock and GraphBLAST did not receive the same level of metadata and profiling
  integration as LAGraph and spla.
- Directed graphs are excluded and require a separate methodology.
- `hollywood-2009` and `indochina-2004` are not yet included in the main run.
- The local `deps/suitesparse_graphblas/` is not part of the branch changes and
  must not be committed.
- The README still contains some outdated wording describing PageRank as a
  future algorithm and an old spla link; these should be updated before the merge.

## 16. Checks of Current Local Changes

The following checks were performed for the current methodology:

- syntax checking of the modified Python files with `py_compile`;
- a smoke test of spla GPU timing parsing;
- a smoke test of LAGraph BFS warm-up and parent-only timing;
- a smoke test of collecting the required number of standard TC trials;
- verification that `deps/lagraph` and `deps/spla` contain no changes;
- `git diff --check`.

This document does not confirm a full experiment or a complete rebuild of all
dependencies.
