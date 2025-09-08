import sys
from pathlib import Path

# Add the project root directory to sys.path so that imports work correctly
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
