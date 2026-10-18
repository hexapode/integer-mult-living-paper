# A living paper for automated research

This prototype treats a paper as a maintained mathematical argument with a complete,
versioned contribution record. It is intentionally explicit about the difference
between importing evidence and explaining or validating it.

## Run

Requirements: Python 3.10+, authenticated GitHub CLI (`gh`), Pandoc.

```sh
python3 build.py refresh
python3 build.py build
```

`refresh` walks **all REST pages**, avoiding GitHub Search's 1,000-result ceiling.
It stores all PR statuses, the default branch commit, repository contributors,
selected result, review ledger and context. It preserves immutable snapshots and
writes a delta log. GitHub is moving during collection: PR metadata is an observed
interval, while repository files are pinned to one commit. Authentication/network
failures stop refresh; old snapshots are not silently presented as fresh.

`build` is offline. It generates `output/paper.tex`, `paper.md`, a shorter
`overview.tex`, a coverage report, and a manifest recording source/editorial/output
hashes and the Pandoc version. Every merged/open PR has a section with its full
available description, credit, status, URL and head SHA. Closed/unmerged PRs stay
in the snapshots and previous editions. Empty descriptions are flagged. Rebuilding
with the same inputs and Pandoc version produces the same manuscript.

```sh
python3 build.py build --snapshot data/snapshot-HASH.json --output editions/HASH
```

For a PDF, use a Unicode-capable LaTeX installation, for example:

```sh
latexmk -lualatex -interaction=nonstopmode -halt-on-error output/paper.tex
```

The script generates LaTeX; that alone does not certify PDF compilation. Arbitrary
contributor equations/macros can require editorial typesetting fixes. It strips raw
HTML/TeX blocks, retains mathematical notation, and links figures without fetching
them. Keep shell escape disabled when compiling external-source mathematics.

## The editorial layer

The full PR body is source testimony, **not an independent explanation**. The first
edition is a complete source-derived draft, not a finished mathematical monograph.
Do not confuse 100% PR coverage with 100% explanatory or verification coverage.

Add a file `editorial/pr-N.json`:

```json
{
  "source_sha256": "copy this PR's fingerprint from output/coverage.json",
  "explanation_markdown": "**Question.** ...\n\n**Mechanism.** ...\n\n**Result and evidence.** ...\n\n**Limitations.** ...\n\n**Connection to prior work.** ..."
}
```

Explain the problem, assumptions, mechanism, mathematical result, evidence,
limitations, and predecessors; cite exact sources. Corrections, tooling and negative
results deserve explanations too. The build preserves editorial notes and visibly
marks them stale when PR metadata changes. A current fingerprint means source
freshness, not review or proof. Three sample explanations demonstrate this layer.

`editorial/narrative.md` supplies a cross-contribution account. It is human/agent-maintained. Its explicit cited sources are tracked, but implicit mathematical dependencies still require editorial review.

Author policy: non-bot repository contributors plus included PR authors, credited
by GitHub handle. This is an attribution draft, not implied consent or endorsement.
PR bodies and the pinned CONTRIBUTORS file retain additional predecessor credits.
Reviewers, commit coauthors, external researchers and identity deduplication need
an explicit editorial policy before publication.

## Where this can go

A full research-paper engine should maintain a **claim graph**, not only PR records:

- A claim has a precise statement, assumptions, source revision, evidence and scope.
- Contributions create, strengthen, refute, reproduce or explain claims.
- Review and merge are independent events; a claim can be conditional or disputed.
- A changed premise queues every dependent explanation for revision.
- The readable narrative is an edited traversal of this graph.
- Frozen editions remain citable, with diffs explaining changes to knowledge and credit.

Next work is to ingest linked proofs/artifacts and review discussions, create claim
records, and write substantive explanations for every contribution. This prototype
does not fetch those sources or run research certificates. It never takes the maximum
number mentioned in a PR as the established frontier. GitHub publication is described below.

## GitHub Pages publication

The public reader is published from this repository by
`.github/workflows/publish.yml`. GitHub Actions checks the upstream project at
minutes **07 and 37 of every hour**, plus on pushes to main and manual dispatch.
GitHub may delay scheduled runs; this is not an exact wall-clock guarantee.
The process runs on GitHub, not on the author's laptop.

Every changed edition is built, checked for complete PR coverage, published to
Pages, and archived as a GitHub Release with its LaTeX, Markdown, coverage report,
build manifest and compressed source snapshot. The content fingerprint includes
upstream sources, contributor records, scripts, templates and editorial notes;
unchanged content is skipped. A failed build leaves the previous site online.
A release is created only after deployment succeeds, allowing interrupted
publications to retry. The published site's source-collection time shows freshness.

The reader includes a short account, searchable contribution pages, the complete
manuscript in HTML, and downloadable LaTeX. Mathematics is rendered in the browser
using MathJax 3.2.2 with its safe extension. PR HTML, active link schemes and custom
HTML attributes are excluded from the rendered evidence. The corpus is treated as
data; no upstream code or reproduction commands are executed by the workflow.

**Editorial scope:** the Action refreshes source-derived explanations and flags
outdated editorial notes. It does not call a model or autonomously synthesize new
mathematics. Review and commit changes under `editorial/` to publish new substantive
explanations. The narrative's cited source bindings are tracked in
`editorial/narrative-sources.json`; a mismatch labels it historical pending review.

For local website generation after building:

```sh
python3 publish.py site
python3 -m http.server 8765 --directory _site
```

To force a check on GitHub:

```sh
gh workflow run publish.yml --repo hexapode/integer-mult-living-paper
```
