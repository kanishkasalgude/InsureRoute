import sys
import os

# Add the backend directory to sys.path so that absolute imports within backend/ work
sys.path.insert(0, os.path.dirname(__file__))

from main import app
