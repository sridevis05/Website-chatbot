import os
import sys

# Inject local packages path to bypass Windows path limit issues
packages_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "packages"))
if packages_path not in sys.path:
    sys.path.insert(0, packages_path)
