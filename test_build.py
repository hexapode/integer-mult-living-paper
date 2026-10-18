import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from build import digest, render

class LivingPaperTests(unittest.TestCase):
    def test_coverage_staleness_and_hostile_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prs = []
            for number, state in [(1, 'merged'), (2, 'open'), (3, 'closed')]:
                prs.append(dict(number=number, state=state, title='Test & $ claim',
                    author='researcher', author_type='User', created_at='2026-01-01',
                    updated_at='2026-01-02', head='abc123', base='abc122',
                    head_repo='example/repo', url=f'https://github.com/example/repo/pull/{number}',
                    body='---\n* invalid YAML here\n---\n\nAn equation $x^2$ and ![asset](https://example.org/image.png).'))
            prs[0]['body'] += '\n\n```python\nunclosed_fence = True\n'
            snapshot = dict(prs=prs, repo='example/repo', contributors=[], main_commit='abc123',
                started_at='2026-01-01', finished_at='2026-01-02', collection='fixture',
                sources={'certificates/selected-result.json':json.dumps({'kappa':'1/1000'})})
            source=root/'snapshot.json'
            source.write_text(json.dumps(snapshot))
            editorial=root/'editorial'
            editorial.mkdir()
            (editorial/'pr-1.json').write_text(json.dumps(dict(source_sha256='old', explanation_markdown='Old explanation.')))
            args=Namespace(snapshot=source,output=root/'out',editorial=editorial)
            render(args)
            coverage=json.loads((args.output/'coverage.json').read_text())
            self.assertEqual([c['pr'] for c in coverage],[1,2])
            self.assertEqual(coverage[0]['explanation'],'editorial-stale')
            tex=(args.output/'paper.tex').read_text()
            self.assertIn('x^2',tex)
            self.assertNotIn('\\includegraphics',tex)
            first=(args.output/'paper.tex').read_bytes()
            render(args)
            self.assertEqual(first,(args.output/'paper.tex').read_bytes())
            self.assertNotEqual(digest(prs[0]), 'old')

if __name__ == '__main__':
    unittest.main()
