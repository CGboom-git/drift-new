"""First batch for the requested workspace cases."""
from run_workspace_requested_common import run_cases


CASES = [
    {"suite": "workspace", "user_task": 13, "injection_task": 0, "label": "task0"},
    {"suite": "workspace", "user_task": 13, "injection_task": 2, "label": "task2"},
    {"suite": "workspace", "user_task": 13, "injection_task": 4, "label": "task4"},
]


if __name__ == "__main__":
    run_cases(CASES, "run_workspace_requested_part1.py")
