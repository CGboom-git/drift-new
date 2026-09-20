import unittest

from agentdojo.task_suite.load_suites import get_suite

from rcdc.task_spec_registry import coverage, entries


class TaskSpecRegistryTests(unittest.TestCase):
    def test_registry_has_exact_agentdojo_v12_task_identity(self):
        expected = {(suite_name, task_id)
                    for suite_name in ('banking', 'slack', 'travel', 'workspace')
                    for task_id in get_suite('v1.2', suite_name).user_tasks}
        self.assertEqual(set(entries()), expected)

    def test_coverage_statuses_are_explicit_and_counts_are_frozen(self):
        values = list(entries().values())
        counts = {status: sum(entry['runtime_status'] == status for entry in values)
                  for status in ('verified', 'not_applicable_read_only', 'needs_semantic_spec')}
        self.assertEqual(counts, {
            'verified': 6,
            'not_applicable_read_only': 37,
            'needs_semantic_spec': 54,
        })
        self.assertEqual(sum(entry['potential_case_count'] for entry in values), 1046)

    def test_unknown_identity_cannot_be_covered(self):
        self.assertEqual(coverage('banking', 'user_task_404')['runtime_status'], 'unknown_task_identity')
