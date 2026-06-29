# LAGraph Benchmark Patches

Two scripts that patch LAGraph benchmark source files to match the comparison setup used in SPLA benchmarks.

## What they do

**`patch_lagraph_bfs.py`** modifies `deps/lagraph/src/benchmark/bfs_demo.c`:
- Switches BFS mode from `parent only` to `level only`
- Fixes `maxlevel` type from `int32_t` to `uint32_t` (avoids INT32 overflow)
- Suppresses `parent only` and `level+parent` timing output

**`patch_lagraph_tc.py`** modifies `deps/lagraph/src/benchmark/tc_demo.c`:
- Switches Triangle Counting presort from `AutoSort` to `NoSort` for a fair comparison with SPLA

## Usage

### Apply patches
```bash
python patch_lagraph_bfs.py
python patch_lagraph_tc.py
```

### Revert to original
```bash
python patch_lagraph_bfs.py --revert
python patch_lagraph_tc.py --revert
```

### Rebuild after patching
```bash
cmake --build deps/lagraph/build --target bfs_demo tc_demo -j$(nproc)
```
