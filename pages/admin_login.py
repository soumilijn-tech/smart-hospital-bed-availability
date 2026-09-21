import runpy
from pathlib import Path

# Run the main application
APP_PATH = Path(__file__).resolve().parent.parent / "app.py"

runpy.run_path(
    str(APP_PATH),
    run_name="__main__"
)
