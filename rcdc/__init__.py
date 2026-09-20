"""Internal compatibility package for the opt-in RCVR experiment layer."""

# ``allow`` is intentionally experiment-only: it makes the treatment of an
# epistemically unresolved binding explicit without weakening the default
# Full-RCVR configuration.
MODES = ('off', 'shadow', 'strict', 'allow', 'retry', 'full')
METHOD_NAME = 'RCVR'
VERSION = 'rcvr-mechanism-1'


def add_arguments(parser):
    # ``rcdc`` remains the package/legacy CLI spelling so existing scripts keep
    # working. New experiment artifacts use RCVR terminology exclusively.
    parser.add_argument('--rcdc_mode', choices=MODES, default='off')
    parser.add_argument('--rcdc_recovery_steps', type=int, default=2)
    return parser
