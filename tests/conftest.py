"""
Pytest configuration and fixtures for ACHE SUCATAS tests.
"""
import sys
from pathlib import Path

# Add project root and src/core to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src" / "core"))
