#!/usr/bin/env python3
"""Compile the current edition, then bind its PDF to the exact LaTeX source."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_pdf(output):
    pdf=output/'paper.pdf';tex=output/'paper.tex';record=output/'paper-pdf-manifest.json'
    if not all(p.is_file() for p in (pdf,tex,record)):
        raise ValueError('This edition has no verified PDF; refusing to publish a missing or stale download')
    metadata=json.loads(record.read_text())
    if metadata.get('source_sha256')!=sha(tex) or metadata.get('pdf_sha256')!=sha(pdf):
        raise ValueError('PDF does not match this edition; rebuild before publishing')
    with pdf.open('rb') as stream:
        if stream.read(5)!=b'%PDF-':raise ValueError('PDF output has an invalid file header')
    return metadata


def compile_pdf():
    output=ROOT/'output';tex=output/'paper.tex'
    if not shutil.which('latexmk'):raise RuntimeError('Install latexmk and XeLaTeX to generate the downloadable paper')
    # Compile in an empty directory. A failed compile cannot reuse an earlier PDF.
    with tempfile.TemporaryDirectory(prefix='paper-pdf-',dir=output) as temporary:
        work=Path(temporary);shutil.copyfile(tex,work/'paper.tex')
        env=dict(os.environ,openin_any='p',openout_any='p')
        command=['latexmk','-xelatex','-interaction=nonstopmode','-halt-on-error','-file-line-error',
                 '-no-shell-escape','paper.tex']
        with (output/'pdf-build.log').open('w') as log:
            result=subprocess.run(command,cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        if result.returncode:
            tail=(output/'pdf-build.log').read_text(errors='replace')[-7000:]
            raise RuntimeError('PDF compilation failed; previous website is retained.\n'+tail)
        produced=work/'paper.pdf'
        if not produced.is_file():raise RuntimeError('Compiler succeeded without producing a PDF')
        info=subprocess.check_output(['pdfinfo',str(produced)],text=True)
        pages=re.search(r'^Pages:\s+(\d+)',info,re.M)
        if not pages:raise RuntimeError('Could not verify PDF page count')
        produced.replace(output/'paper.pdf')
    metadata={'source_sha256':sha(tex),'pdf_sha256':sha(output/'paper.pdf'),
              'pages':int(pages[1]),'compiler':'latexmk / XeLaTeX',
              'snapshot_sha256':json.loads((output/'manifest.json').read_text())['snapshot_sha256'],
              'compiler_version':subprocess.check_output(['xelatex','--version'],text=True).splitlines()[0]}
    (output/'paper-pdf-manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
    validate_pdf(output)
    print(f'PDF verified: {metadata["pages"]} pages; source {metadata["source_sha256"][:12]}')


if __name__=='__main__':compile_pdf()
