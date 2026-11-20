import os
import sys

from fsxwl.app import App, load_config

if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    App(base, load_config(base)).run()
