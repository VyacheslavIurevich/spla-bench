import sys

path = "./deps/lagraph/src/benchmark/tc_demo.c"

replacements = [
    (
        "int sorting = LAGr_TriangleCount_AutoSort ; // just use auto-sort",
        "int sorting = LAGr_TriangleCount_NoSort ;"
    )
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
