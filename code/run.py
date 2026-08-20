import os
import sys
import argparse

# Ensure code/ is on sys.path
code_dir = os.path.dirname(os.path.abspath(__file__))
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

from main import main as run_main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PingSense WhatsApp Notification Router")
    parser.add_argument("--input", default="dataset/messages.csv", help="Input messages CSV path")
    parser.add_argument("--output", default="dataset/output.csv", help="Output predictions CSV path")
    args = parser.parse_args()
    
    run_main()
