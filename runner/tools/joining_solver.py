"""The structured joining solver: prefix extension under a compressor.

Agent-Stamp: 00000000-muse-7e57-d0c5-58316a922026

docs/infrastructure-documents/proofs/v4-the-joining-solver.md
is the page this module serves. The construction arrived in
the project's P versus NP discussion by email on 23 November
2026: extend a formula's prefixes variable by variable, keep
the retained list small with a compressor, and hold the
compressor to a contract, that some prefix in the list
before compression can be completed to a satisfying
assignment exactly when some prefix in the list after
compression can. docs/infrastructure-documents/proofs/
properties.md states the conditional consequence as its
Theorem 4. This module is the research artifact the
completion checklist's item 23 asked for: the construction
embodied, small enough to check at every round.

Representation, specified completely:

- Variables are the integers 1 to n. A literal is a nonzero
  integer: v means variable v is true, and -v means it is
  false.
- A clause is a tuple of literals. A formula is a tuple of
  clauses. A clause is satisfied by an assignment when at
  least 1 of its literals is true under it, and falsified
  when every 1 of its literals is false.
- A prefix is a tuple of values, 0 or 1, for an initial
  segment of a fixed variable order: prefix[i] is the value
  of order[i].

The solver works in rounds, 1 per variable: extend each
retained prefix by 0 and by 1, then compress the extended
list. Completability is decided by exhaustive search over
the unread variables, with pruning, so this module is an
instrument for small instances: it checks the contract at
every round rather than assuming it, and it is not a solver
for large ones.

Compressors:

- exact_compress keeps 1 representative per distinct
  residual key, first occurrence winning. Prefixes with the
  same residual key have the same completions, so it keeps
  the contract. It promises no size.
- keep_first(w) returns a compressor that keeps only the
  first w prefixes of the extended list. It promises a size
  and nothing else.

solve() returns a Result: the verdict, a satisfying prefix
when the verdict is satisfiable, and 1 Round record per
variable, holding the round's sizes before and after
compression and whether the contract held at that round.
"""

from __future__ import annotations

from dataclasses import dataclass

DEAD = ("dead",)


def _clause_open(clause, assigned):
    """The state of 1 clause under a partial assignment.

    assigned maps variable to value. Returns None when the
    clause is satisfied, the DEAD marker when every literal
    is false, and otherwise the frozenset of the literals
    whose variables are not yet assigned.
    """
    open_lits = []
    for lit in clause:
        var = abs(lit)
        if var in assigned:
            if (assigned[var] == 1) == (lit > 0):
                return None
        else:
            open_lits.append(lit)
    if not open_lits:
        return DEAD
    return frozenset(open_lits)


def residual_key(clauses, order, prefix):
    """A hashable key for the residual of a prefix.

    2 prefixes with the same key have the same completions:
    the assignments to the unread variables that satisfy
    every clause under each. A prefix with a falsified
    clause has the DEAD key, the empty residual.
    """
    assigned = dict(zip(order[: len(prefix)], prefix))
    key = []
    for clause in clauses:
        state = _clause_open(clause, assigned)
        if state is DEAD:
            return DEAD
        key.append(state)
    return tuple(key)


def _falsified(clause, assigned):
    """Whether every literal of the clause is assigned and
    false under the partial assignment."""
    for lit in clause:
        var = abs(lit)
        if var not in assigned:
            return False
        if (assigned[var] == 1) == (lit > 0):
            return False
    return True


def extendible(clauses, order, prefix):
    """Whether some completion of the prefix satisfies
    every clause, decided by search over the unread
    variables, pruning any branch that falsifies a clause.
    """
    assigned = dict(zip(order[: len(prefix)], prefix))
    rest = order[len(prefix):]

    def search(i):
        for clause in clauses:
            if _falsified(clause, assigned):
                return False
        if i == len(rest):
            return True
        var = rest[i]
        for value in (0, 1):
            assigned[var] = value
            if search(i + 1):
                return True
            del assigned[var]
        return False

    return search(0)


def satisfies(clauses, order, full_prefix):
    """Whether a complete prefix satisfies every clause."""
    assigned = dict(zip(order, full_prefix))
    return all(
        _clause_open(clause, assigned) is None for clause in clauses
    )


def verdict_brute_force(clauses, order):
    """The satisfiability verdict by full enumeration."""
    return extendible(clauses, order, ())


def _some_extendible(clauses, order, prefixes):
    return any(extendible(clauses, order, p) for p in prefixes)


def contract_holds(clauses, order, before, after):
    """The compressor contract between 2 lists of prefixes
    of the same length: some prefix in before can be
    completed exactly when some prefix in after can.
    """
    return _some_extendible(clauses, order, before) == _some_extendible(
        clauses, order, after
    )


def exact_compress(clauses, order, prefixes):
    """1 representative per distinct residual key, first
    occurrence winning, order preserved."""
    seen = set()
    kept = []
    for prefix in prefixes:
        key = residual_key(clauses, order, prefix)
        if key not in seen:
            seen.add(key)
            kept.append(prefix)
    return kept


def keep_first(width):
    """A compressor keeping only the first width prefixes
    of the extended list, in generation order."""

    def compress(clauses, order, prefixes):
        return list(prefixes[:width])

    return compress


@dataclass
class Round:
    variable: int
    before: int
    after: int
    contract: bool


@dataclass
class Result:
    verdict: bool
    witness: tuple | None
    rounds: list


def solve(clauses, order, compress):
    """Run the joining solver on a formula under an order
    with a compressor, checking the contract at every round.

    compress is called as compress(clauses, order, prefixes)
    and returns the retained list.
    """
    prefixes = [()]
    rounds = []
    for var in order:
        extended = []
        for prefix in prefixes:
            extended.append(prefix + (0,))
            extended.append(prefix + (1,))
        kept = compress(clauses, order, extended)
        rounds.append(
            Round(
                variable=var,
                before=len(extended),
                after=len(kept),
                contract=contract_holds(
                    clauses, order, extended, kept
                ),
            )
        )
        prefixes = kept
    witness = None
    for prefix in prefixes:
        if satisfies(clauses, order, prefix):
            witness = prefix
            break
    return Result(
        verdict=witness is not None, witness=witness, rounds=rounds
    )
