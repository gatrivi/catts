import tempfile
import unittest
from pathlib import Path
from scripts.local_advisor import source_packet, note_path


class AdvisorTests(unittest.TestCase):
    def test_context_is_scoped_and_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            project = root / 'project'
            project.mkdir()
            (project / 'Button.jsx').write_text('export const Button = () => null;', encoding='utf-8')
            (root / 'outside.txt').write_text('private', encoding='utf-8')
            (project / '.env').write_text('SECRET=x', encoding='utf-8')
            (project / 'large.txt').write_text('x' * 16001, encoding='utf-8')
            self.assertIn('Button.jsx', source_packet(project, ['Button.jsx']))
            for name in ['../outside.txt', '.env', 'large.txt']:
                with self.subTest(name=name), self.assertRaises(ValueError):
                    source_packet(project, [name])

    def test_projects_do_not_share_notes(self):
        self.assertNotEqual(note_path(Path('one/app')), note_path(Path('two/app')))


if __name__ == '__main__':
    unittest.main()
