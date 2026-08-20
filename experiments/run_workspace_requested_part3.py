"""Third batch for the requested workspace cases."""
from run_workspace_requested_common import run_cases


CASES = [
    {"suite": "workspace", "user_task": 30, "injection_task": 0, "label": "task0"},
    {"suite": "workspace", "user_task": 30, "injection_task": 3, "label": "task3"},
    {"suite": "workspace", "user_task": 2, "injection_task": 0, "label": "task0"},
    {"suite": "workspace", "user_task": 19, "injection_task": 0, "label": "task0"},
    {"suite": "workspace", "user_task": 19, "injection_task": 3, "label": "task3"},
]


if __name__ == "__main__":
    run_cases(CASES, "run_workspace_requested_part3.py")
