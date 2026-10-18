import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from build_pdf import validate_pdf

class PdfPublicationTests(unittest.TestCase):
    def test_stale_pdf_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp);(output/'paper.tex').write_text('edition one')
            (output/'paper.pdf').write_bytes(b'%PDF-1.7\nfixture')
            digest=lambda name:hashlib.sha256((output/name).read_bytes()).hexdigest()
            (output/'paper-pdf-manifest.json').write_text(json.dumps({'source_sha256':digest('paper.tex'),'pdf_sha256':digest('paper.pdf')}))
            validate_pdf(output)
            (output/'paper.tex').write_text('edition two')
            with self.assertRaisesRegex(ValueError,'does not match'):validate_pdf(output)
    def test_missing_pdf_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'no verified PDF'):validate_pdf(Path(tmp))
