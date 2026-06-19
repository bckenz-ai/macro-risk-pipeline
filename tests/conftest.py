import os
import sys

# Makes "from pipeline import ..." and "from fred_client import ..." work
# when pytest is run from the repository root, by adding src/ to the
# module search path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))