import pytest
import sys
import os

# Import fixtures from parent conftest.py
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from conftest import setup_test_environment