"""Exercise the actual publisher shell step with clean and conflicting Git trees."""
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def publisher_apply_script():
    lines = (ROOT / '.github/workflows/publish-production-data.yml').read_text().splitlines()
    start = lines.index('      - name: Apply production patch atomically')
    start = lines.index('        run: |', start) + 1
    end = start
    while end < len(lines) and (not lines[end].strip() or lines[end].startswith('          ')):
        end += 1
    return textwrap.dedent('\n'.join(lines[start:end]))


class PublisherPatchApplyTests(unittest.TestCase):
    def check_patch(self, *, conflict):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / 'artifact'
            artifact.mkdir()

            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, text=True)

            git('init', '-q')
            git('config', 'user.email', 'test@example.com')
            git('config', 'user.name', 'Test')
            (root / 'data').mkdir()
            target = root / 'data/earnings_calendar.json'
            target.write_text('{"version":"base"}\n')
            git('add', 'data')
            git('commit', '-qm', 'base')
            base = git('rev-parse', 'HEAD').strip()
            target.write_text('{"version":"producer"}\n')
            (artifact / 'production-data.patch').write_text(git('diff', '--binary', 'HEAD'))
            git('checkout', '--', 'data')
            if conflict:
                target.write_text('{"version":"newer-production"}\n')
                git('add', 'data')
                git('commit', '-qm', 'newer production')
            index_before = (root / '.git/index').read_bytes()
            (artifact / 'metadata.json').write_text(json.dumps({
                'base_sha': base, 'producer_run_id': '42',
                'changed_paths': ['data/earnings_calendar.json'],
            }))
            output = root / 'outputs'
            result = subprocess.run(
                ['bash', '-c', publisher_apply_script().replace('/tmp/production-data', str(artifact))],
                cwd=root, env={**os.environ, 'GITHUB_OUTPUT': str(output)},
                text=True, capture_output=True,
            )
            if conflict:
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('REJECTED_PATCH_BASE', result.stdout)
                self.assertEqual(target.read_text(), '{"version":"newer-production"}\n')
                self.assertEqual((root / '.git/index').read_bytes(), index_before)
                evidence = json.loads((artifact / 'apply-failure.json').read_text())
                self.assertEqual(evidence['publisher_base_sha'], git('rev-parse', 'HEAD').strip())
                self.assertFalse(output.exists())
            else:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(target.read_text(), '{"version":"producer"}\n')
                self.assertIn('data/earnings_calendar.json', git('diff', '--cached', '--name-only'))
                self.assertIn('changed=true', output.read_text())

    def test_clean_patch_is_staged(self):
        self.check_patch(conflict=False)

    def test_conflict_preserves_worktree_and_index(self):
        self.check_patch(conflict=True)
