import sys
from pathlib import Path

resources_path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(resources_path))

from bootstrap.examples.financial_assistant.run import main

if __name__ == "__main__":
    main()
