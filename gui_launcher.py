import multiprocessing
import sys
from pharmabot.gui.app import run_gui

if __name__ == "__main__":
    multiprocessing.freeze_support()
    run_gui()
