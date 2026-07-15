import argparse
import random
import numpy as np
import logging

def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    return seed

def get_logger(filename=None):
    logger = logging.getLogger('logger')
    logger.setLevel(logging.DEBUG)
    logging.basicConfig(format='%(asctime)s - %(levelname)s -   %(message)s',
                    datefmt='%m/%d/%Y %H:%M:%S',
                    level=logging.INFO)
    if filename is not None:
        handler = logging.FileHandler(filename)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s: %(message)s'))
        logging.getLogger().addHandler(handler)
    return logger

def get_args(description='DRIFT'):
    parser = argparse.ArgumentParser(description=description)
    # Eval Setting
    parser.add_argument('--benchmark_version', type=str, default='v1.2', help='the version of agentdojo')
    parser.add_argument('--model', type=str, default='gpt-4o-mini-2024-07-18', help='gpt-4o-mini, gpt-4o')
    parser.add_argument("--suites", type=str, default="banking,slack,travel,workspace", help="which suites to use, separated by comma.")
    parser.add_argument('--force_rerun', action='store_true', help='Whether to force rerun.')
    parser.add_argument('--do_attack', action='store_true', help='Whether the setting is under attack.')
    parser.add_argument('--attack_type', type=str, default="important_instructions", help='The attack type')
    parser.add_argument('--target_user_tasks', type=str, default=None, help='User task number you want to evaluate, sperated by comma, such as "1,4,7".')
    parser.add_argument('--target_injection_tasks', type=str, default=None, help='Injection task number you want to specific evaluate, sperated by comma, such as "1,2,3".')

    # DRIFT Setting
    parser.add_argument("--build_constraints", action='store_true', help="Whether to build initial constraints.")
    parser.add_argument("--injection_isolation", action='store_true', help="Whether to detect injection instruction.")
    parser.add_argument("--dynamic_validation", action='store_true', help="Whether to validate dynamically.")
    parser.add_argument("--adaptive_attack", action='store_true', help="Whether to implement adaptive attack.")
    parser.add_argument(
        "--source_flow_log",
        nargs="?",
        const="source_flow",
        default=None,
        help="Enable source-flow logging. Optionally provide a directory for per-run logs.",
    )
    parser.add_argument(
        "--source_flow_validation",
        action="store_true",
        help="Enable source-flow validation before ACTION/WRITE execution.",
    )
    parser.add_argument(
        "--controlled_action_extension",
        action="store_true",
        help="Enable Controlled Action Extension for trajectory-outside ACTION tools (Phase 3).",
    )
    parser.add_argument(
        "--cae_mode",
        type=str,
        choices=["on", "off", "strict", "block", "repair"],
        default=None,
        help="CAE mode: on (current behavior), off (fully disabled), strict (block high-risk ACTION). "
             "If not set, uses --controlled_action_extension flag for backward compatibility.",
    )
    parser.add_argument(
        "--disable_delegated_task_source",
        action="store_true",
        help="Disable delegated task source detection (ablation).",
    )

    # Environment
    parser.add_argument('--seed', type=int, default=98, help='Random Seed.')

    args = parser.parse_args()

    # Resolve cae_mode with backward compatibility
    if args.cae_mode is not None:
        pass  # explicitly set, use as-is
    elif getattr(args, 'controlled_action_extension', False):
        args.cae_mode = 'on'
    else:
        args.cae_mode = 'off'

    return args
