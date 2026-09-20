"""Split the APDE PCVR 67-case matrix into two non-overlapping sequential lanes."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'reports' / 'rcvr_ablation_preflight' / 'run_pcvr_apde_67_b1_b5_t07_20260911.sh'
LANES = {
    'lane1': ('B1_RCVR', 'B3_UNKNOWN_STOP', 'B5_WO_EVIDENCE_ISOLATION'),
    'lane2': ('B2_WO_BINDING', 'B4_UNKNOWN_ALLOW'),
}


def main():
    lines = SOURCE.read_text(encoding='utf-8').splitlines()
    header = lines[:5]
    current = None
    groups = {arm: [] for arms in LANES.values() for arm in arms}
    for line in lines[5:]:
        if line.startswith('# B'):
            current = line[2:]
        if current in groups:
            groups[current].append(line)
    for name, arms in LANES.items():
        out = SOURCE.with_name(f'run_pcvr_apde_67_{name}_t07_20260911.sh')
        rendered = [*header, '']
        for arm in arms:
            rendered.extend(groups[arm])
            rendered.append('')
        command_count = sum(1 for line in rendered if 'run_rcvr_online.py run' in line)
        if command_count != 67 * len(arms):
            raise ValueError(f'{name}_unexpected_command_count:{command_count}')
        out.write_text('\n'.join(rendered), encoding='utf-8')
        print(f'{name} arms={",".join(arms)} commands={command_count} path={out}')


if __name__ == '__main__':
    main()
