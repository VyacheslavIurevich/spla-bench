import sys

path = "./deps/lagraph/src/benchmark/bfs_demo.c"

replacements = [
    (
        "#if 0\n                GrB_free (&level) ;",
        "#if 1\n                GrB_free (&level) ;"
    ),
    (
        "int32_t maxlevel ;",
        "uint32_t maxlevel ;"
    ),
    (
        "GRB_TRY (GrB_reduce (&maxlevel, NULL, GrB_MAX_MONOID_INT32,\n                    level, NULL)) ;",
        "GRB_TRY (GrB_reduce (&maxlevel, NULL, GrB_MAX_MONOID_UINT32, level, NULL)) ;"
    ),
    (
        "src: %12\" PRId64 \" %10.4f sec maxlevel: %d\\n\",\n                    trial, nthreads, (double) src, ttrial, maxlevel",
        "src: %12\" PRId64 \" %10.4f sec maxlevel: %u\\n\",\n                    trial, nthreads, src, ttrial, maxlevel"
    ),
        (
        "                GrB_free (&parent) ;\n                double ttrial = LAGraph_WallClockTime ( ) ;\n                LAGRAPH_TRY (LAGr_BreadthFirstSearch (NULL, &parent,\n                    G, src, msg)) ;\n                ttrial = LAGraph_WallClockTime ( ) - ttrial ;\n                tp [nthreads] += ttrial ;\n                printf (\"parent only  pushpull trial: %2d threads: %2d \"\n                    \"src: %12\" PRId64 \" %10.4f sec\\n\",\n                    trial, nthreads, src, ttrial) ;\n                fflush (stdout) ; fflush (stderr) ;",
        "                // GrB_free (&parent) ;\n                // double ttrial = LAGraph_WallClockTime ( ) ;\n                // LAGRAPH_TRY (LAGr_BreadthFirstSearch (NULL, &parent,\n                //     G, src, msg)) ;\n                // ttrial = LAGraph_WallClockTime ( ) - ttrial ;\n                // tp [nthreads] += ttrial ;\n                // printf (\"parent only  pushpull trial: %2d threads: %2d \"\n                //     \"src: %12\" PRId64 \" %10.4f sec\\n\",\n                //     trial, nthreads, src, ttrial) ;\n                // fflush (stdout) ; fflush (stderr) ;"
    ),
    (
        '                GrB_free (&parent) ;\n                GrB_free (&level) ;\n                ttrial = LAGraph_WallClockTime ( ) ;\n                LAGRAPH_TRY (LAGr_BreadthFirstSearch (&level, &parent,\n                    G, src, msg)) ;\n                ttrial = LAGraph_WallClockTime ( ) - ttrial ;\n                tpl [nthreads] += ttrial ;\n\n                GRB_TRY (GrB_reduce (&maxlevel, NULL, GrB_MAX_MONOID_INT32,\n                    level, NULL)) ;\n                printf ("parent+level pushpull trial: %2d threads: %2d "\n                    "src: %12" PRId64 " %10.4f sec\\n",\n                    trial, nthreads, (double) src, ttrial) ;\n                fflush (stdout) ;',
        # '                GrB_free (&parent) ;\n                GrB_free (&level) ;\n                ttrial = LAGraph_WallClockTime ( ) ;\n                LAGRAPH_TRY (LAGr_BreadthFirstSearch (&level, &parent,\n                    G, src, msg)) ;\n                ttrial = LAGraph_WallClockTime ( ) - ttrial ;\n                tpl [nthreads] += ttrial ;\n\n                GRB_TRY (GrB_reduce (&maxlevel, NULL, GrB_MAX_MONOID_UINT32, level, NULL)) ;\n                printf ("parent+level pushpull trial: %2d threads: %2d "\n                    "src: %12" PRId64 " %10.4f sec\\n",\n                    trial, nthreads, src, ttrial) ;\n                fflush (stdout) ;',
        '                // GrB_free (&parent) ;\n                // GrB_free (&level) ;\n                // ttrial = LAGraph_WallClockTime ( ) ;\n                // LAGRAPH_TRY (LAGr_BreadthFirstSearch (&level, &parent,\n                //     G, src, msg)) ;\n                // ttrial = LAGraph_WallClockTime ( ) - ttrial ;\n                // tpl [nthreads] += ttrial ;\n\n                // GRB_TRY (GrB_reduce (&maxlevel, NULL, GrB_MAX_MONOID_UINT32, level, NULL)) ;\n                // printf ("parent+level pushpull trial: %2d threads: %2d "\n                //     "src: %12" PRId64 " %10.4f sec\\n",\n                //     trial, nthreads, src, ttrial) ;\n                // fflush (stdout) ;'
    ),
    (
        "            printf (         \"Avg: BFS pushpull parent only, threads %3d: %10.3f sec, graph: %s\\n\",\n                 nthreads, tp [nthreads], matrix_name) ;\n            fprintf (stderr, \"Avg: BFS pushpull parent only, threads %3d: %10.3f sec, graph: %s\\n\",\n                 nthreads, tp [nthreads], matrix_name) ;\n            fflush (stdout) ; fflush (stderr) ;",
        "            // printf (         \"Avg: BFS pushpull parent only, threads %3d: %10.3f sec, graph: %s\\n\",\n            //      nthreads, tp [nthreads], matrix_name) ;\n            // fprintf (stderr, \"Avg: BFS pushpull parent only, threads %3d: %10.3f sec, graph: %s\\n\",\n            //      nthreads, tp [nthreads], matrix_name) ;\n            // fflush (stdout) ; fflush (stderr) ;"
    ),
    (
        "#if 0\n            fprintf (stderr, \"Avg: BFS pushpull level only",
        "#if 1\n            fprintf (stderr, \"Avg: BFS pushpull level only"
    ),
    (
        '            fprintf (stderr, "Avg: BFS pushpull level+parent threads %3d: "\n                "%10.3f sec: %s\\n",\n                 nthreads, tpl [nthreads], matrix_name) ;',
        '            // fprintf (stderr, "Avg: BFS pushpull level+parent threads %3d: "\n            //     "%10.3f sec: %s\\n",\n            //      nthreads, tpl [nthreads], matrix_name) ;'
    ),
    (
        '            printf ("Avg: BFS pushpull level+parent threads %3d: "\n                "%10.3f sec: %s\\n",\n                 nthreads, tpl [nthreads], matrix_name) ;',
        '            // printf ("Avg: BFS pushpull level+parent threads %3d: "\n            //     "%10.3f sec: %s\\n",\n            //      nthreads, tpl [nthreads], matrix_name) ;'
    ),
]

revert = "--revert" in sys.argv
if revert:
    replacements = [(new, old) for old, new in replacements]
    print("Mode: revert")
else:
    print("Mode: patch")

with open(path, "r") as f:
    content = f.read()

for old, new in replacements:
    if old not in content:
        print(f"WARNING: pattern not found:\n  {old!r}")
    else:
        content = content.replace(old, new, 1)
        print(f"OK: replaced")

with open(path, "w") as f:
    f.write(content)

print(f"Done: {path}")
