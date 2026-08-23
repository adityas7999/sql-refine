from pathlib import Path
import sys

RULE_TESTER_ROOT = Path(__file__).resolve().parents[1]
if str(RULE_TESTER_ROOT) not in sys.path:
    sys.path.insert(0, str(RULE_TESTER_ROOT))
