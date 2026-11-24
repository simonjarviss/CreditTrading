"""The te4 no-op proof runs every rule the core sleeve's docstring says it proves.

WHY (the quant review of f1d9f62, finding 2). `src/deploy/sleeves/cef_discount.py`'s module
docstring says the core's targets under `below_min_names` ABSENT, "flatten" or "hold" are today's,
byte for byte, "proved on every real-panel decision date ... against ac15d09's code
(results/cef/te4_impl/sleeve_noop_diff.py ...)". As first committed that script ran no "hold"
child. The claim was true (the reviewer re-ran it with a scratch copy: 14,036 of 14,036
identical), but the docstring cited evidence the repository did not contain, and a provenance line
that names a check must name one that exists (CLAUDE.md, data rules: a number without provenance
is a rumour).

These pin the script's table of claims (`COMPARE`) to the docstring's sentence: each rule the
sentence names is a variant of the new code compared byte for byte with ac15d09's code under the
SAME rule ("hold" against ac15d09's "hold", because "hold" is meant to differ from "flatten").
Nothing here runs the proof (it takes about 21 minutes on the real panel); the script imports only
the standard library at module level, so loading it opens nothing.

THE EVIDENCE, NOT ONLY THE SCRIPT (the third test). A script that could make the comparison is not
a comparison made: the docstring cites "the dated output beside it", so the repository must hold
one full run (`--dates all`, from a clean checkout, verdict NO-OP PROVED) that reports every
`COMPARE` claim byte-identical on every (date, book). It does not tie that output to the sleeve's
current bytes (the output records the git blob ids it ran on): a blob pin would fail on every later
edit of cef_discount.py, the C4 and activation commits included. Re-run the script after changing
the sleeve.

FAILS ON f1d9f62: the script has no `COMPARE` and no "hold" variant. The third test also fails on
0283fae, where the script ran "hold" but no committed output had yet run it.
"""
import importlib.util
import re
from pathlib import Path

from src.deploy.sleeves import cef_discount as cefmod

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "results" / "cef" / "te4_impl" / "sleeve_noop_diff.py"
# The sentence in the sleeve's module docstring that this pins (whitespace normalised).
CLAIM = "ABSENT, \"flatten\" or \"hold\": byte for byte today's targets"
CLAIMED = {"absent": "base:absent", "flatten": "base:absent", "hold": "base:hold"}


def _script():
    spec = importlib.util.spec_from_file_location("te4_sleeve_noop_diff", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_sleeve_docstring_states_the_claim_and_cites_the_script():
    doc = " ".join(cefmod.__doc__.split())
    assert CLAIM in doc
    assert "results/cef/te4_impl/sleeve_noop_diff.py" in doc


def test_the_script_compares_every_claimed_rule_with_ac15d09_under_the_same_rule():
    """ABSENT and "flatten" are one rule (the registry reads an absent key as "flatten"), so
    both are held to ac15d09's key-absent targets; "hold" to ac15d09's "hold"."""
    mod = _script()
    for rule, against in CLAIMED.items():
        new = f"new:{rule}"
        assert new in mod.VARIANTS and against in mod.VARIANTS, (new, against)
        assert mod.COMPARE.get(new) == against, (new, mod.COMPARE.get(new))
    # every comparison is of two variants the script actually runs
    for v, against in mod.COMPARE.items():
        assert v in mod.VARIANTS and against in mod.VARIANTS, (v, against)


def test_the_repository_holds_a_full_run_proving_every_claim():
    """A committed output of the script on EVERY decision date (`--dates all`, not a quick look),
    from a CLEAN checkout, whose verdict is NO-OP PROVED and which reports each `COMPARE` claim
    byte-identical on every (date, book): "N of N"."""
    mod = _script()
    found = []
    for p in sorted(SCRIPT.parent.glob("sleeve_noop_diff_output_*.txt")):
        text = p.read_text()
        if not ("--dates all" in text and "(clean)" in text
                and "VERDICT: NO-OP PROVED" in text):
            continue
        if all(re.search(rf"^{re.escape(v)}\s+vs {re.escape(a)}: (\d+) of \1 \(date, book\) "
                         rf"pickles byte-identical$", text, re.M)
               for v, a in mod.COMPARE.items()):
            found.append(p.name)
    assert found, (f"no committed full run of {SCRIPT.name} in {SCRIPT.parent} proves every "
                   f"COMPARE claim ({sorted(mod.COMPARE)}); run it and commit its output")
