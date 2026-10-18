## Why the frontier has more than one coordinate

The repository illustrates a central problem for automated research: the newest
numerical claim and the selected reviewed result can move at different speeds.
At this edition, the selected record still attributes the conditional exponent
saving $0.001672660197076918$ to [PR 1094](https://github.com/CrocSwap/integer-mult-bounds/pull/1094).
Meanwhile, [PR 3743](https://github.com/CrocSwap/integer-mult-bounds/pull/3743)
examines a moment bracket near $0.001730418899766071163804$ for a T488 profile.
The latter submission expressly claims no new kappa and no word replay. These
numbers describe different evidence situations; replacing the former with the
latter would erase that distinction.

A useful paper must consequently explain both the mathematical candidate frontier
and the frontier of completed evidence. The first asks which construction might
achieve a better exponent. The second asks which construction, assumptions and
reproduction obligations have actually been admitted by the project's review
process. Neither can be reconstructed reliably by sorting PR titles numerically.

## A construction, an arithmetic check, and a structural caution

PR 1094 changes whole-helper placement through rare full-bin patterns while
retaining the scalar word and its timings. Its significance is that allocation
can change the idle-rank profile even without changing the underlying word.
The submission reports a finite witness and extensive local checks, while retaining
all-size and transfer assumptions. This is a construction contribution with
conditional consequences.

PR 3743 instead narrows the arithmetic interpretation of an existing T488 profile.
It reports a sign change across adjacent decimal endpoints separated by $10^{-24}$.
That helps situate the released numerical string relative to the moment root.
It does not itself construct or replay the word. This is evidence about the
arithmetic of a candidate, a distinct and useful contribution.

[PR 3749](https://github.com/CrocSwap/integer-mult-bounds/pull/3749) supplies a different
lesson: two idle histograms with equal total idle mass can fall on opposite sides
of the moment threshold. Under the submission's stated calculation, aggregation
therefore loses information relevant to admission. A scalar summary of resource
usage is insufficient to replace the rank distribution. This is a scoped structural
warning, not a new multiplication bound.

These examples motivate a contribution-complete paper. Constructions, arithmetic
checks and restrictions on valid reasoning all advance the research account, even
when only some change the selected exponent. The explanations above are editorial
readings of the cited submissions and the selected record, not independent replays.
