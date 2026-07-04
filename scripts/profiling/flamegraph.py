"""
Flamegraph generator for CPU callgraphs
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional
from profiler_base import Profiler


class FlamegraphGenerator:
    """Generate flamegraphs from perf data"""

    def __init__(self, flamegraph_dir: Optional[Path] = None):
        self.flamegraph_dir = (
            flamegraph_dir or Path.home() / ".spla-bench" / "flamegraph"
        )
        self.flamegraph_dir.mkdir(parents=True, exist_ok=True)
        self.setup_flamegraph_repo()

    def setup_flamegraph_repo(self):
        """Clone or update FlameGraph repository"""
        repo_url = "https://github.com/brendangregg/FlameGraph.git"

        if not (self.flamegraph_dir / "flamegraph.pl").exists():
            print(f"Cloning FlameGraph repository to {self.flamegraph_dir}")
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", repo_url, str(self.flamegraph_dir)],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                print(f"Failed to clone FlameGraph repository: {e}")

        self.flamegraph_pl = self.flamegraph_dir / "flamegraph.pl"
        self.stackcollapse_pl = self.flamegraph_dir / "stackcollapse-perf.pl"

    def is_available(self) -> bool:
        """Check if flamegraph tools are available"""
        return (
            self.flamegraph_pl.exists()
            and self.stackcollapse_pl.exists()
            and shutil.which("perf") is not None
        )

    def generate_flamegraph(self, perf_file: Path, output_svg: Path) -> bool:
        """Generate flamegraph SVG from perf data"""

        if not self.is_available():
            print("Flamegraph tools not available")
            return False

        if not perf_file.exists():
            print(f"Perf file not found: {perf_file}")
            return False

        if not (self.flamegraph_pl.exists() and self.stackcollapse_pl.exists()):
            print("FlameGraph repository not properly set up")
            return False

        try:
            print(f"Generating flamegraph for {perf_file}")

            # Convert perf data to collapsed stack format
            collapsed_file = perf_file.with_suffix(".folded")

            perf_script_cmd = ["perf", "script", "-i", str(perf_file)]
            fold_cmd = [str(self.stackcollapse_pl)]

            # Run perf script | stackcollapse-perf.pl > folded
            with open(collapsed_file, "w") as collapsed_f:
                perf_process = subprocess.run(
                    perf_script_cmd, capture_output=True, text=True, check=True
                )

                fold_process = subprocess.run(
                    fold_cmd,
                    input=perf_process.stdout,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                collapsed_f.write(fold_process.stdout)

            # Generate flamegraph SVG
            subprocess.run(
                [str(self.flamegraph_pl), str(collapsed_file)],
                stdout=open(output_svg, "w"),
                check=True,
            )

            print(f"Flamegraph saved to {output_svg}")
            return True

        except subprocess.CalledProcessError as e:
            print(f"Failed to generate flamegraph: {e}")
            print(
                f"Perf process output: {perf_process.stdout if 'perf_process' in locals() else ''}"
            )
            print(
                f"Fold process output: {fold_process.stdout if 'fold_process' in locals() else ''}"
            )
            return False

        except Exception as e:
            print(f"Unexpected error generating flamegraph: {e}")
            return False

    def generate_interactive_flamegraph(
        self, perf_file: Path, output_html: Path
    ) -> bool:
        """Generate interactive HTML flamegraph"""

        svg_file = output_html.with_suffix(".svg")
        if not self.generate_flamegraph(perf_file, svg_file):
            return False

        # Create simple HTML wrapper
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Flamegraph</title>
    <style>
        body {{ margin: 0; padding: 20px; font-family: Arial, sans-serif; }}
        .container {{ max-width: 100%; overflow: auto; }}
        h1 {{ text-align: center; }}
        svg {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <h1>Interactive Flamegraph</h1>
    <div class="container">
        <iframe src="{svg_file.name}" width="100%" height="1000" style="border: none;"></iframe>
    </div>
</body>
</html>
"""

        try:
            with open(output_html, "w") as f:
                f.write(html_content)
            print(f"Interactive flamegraph saved to {output_html}")
            return True
        except Exception as e:
            print(f"Failed to create interactive flamegraph: {e}")
            return False

    def cleanup(self):
        """Cleanup temporary files"""
        pass
