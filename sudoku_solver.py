"""IT5005 Assignment 1: student implementation file.

Implement the functions marked below. Do not modify utils.py or logic_.py.
"""

from utils import *
from logic_ import *


# Do not change this function; it is used to create atomic propositions.
def atom(prefix, r, c, v):
    """prefix is 'Is' or 'Not'. Returns the Expr for e.g. Is3_2_4."""
    return expr(f'{prefix}{r}_{c}_{v}')


def build_general_kb(n, box_h, box_w, givens):
    """Return a PropKB encoding this n x n Sudoku's constraints plus the given
    cells, as general clauses.

    Parameters
    ----------
    n, box_h, box_w : int
    givens : dict[(int, int), int]

    Returns
    -------
    PropKB
    """
    kb = PropKB()
    
    # Each cell is assigned **at least one** value from $\{1, \dots, n\}$
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            clause = atom('Is', r, c, 1)
            for v in range(2, n + 1):
                clause = clause | atom('Is', r, c, v)
            kb.tell(clause)
    
    # Each cell is assigned **at most one** value from $\{1, \dots, n\}$
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v1, v2 in combinations(range(1, n + 1), 2):
                kb.tell(~atom('Is', r, c, v1) | ~atom('Is', r, c, v2))
    
    # No two cells in the same row hold the same value.
    for r in range(1, n + 1):
        for v in range(1, n + 1):
            for c1, c2 in combinations(range(1, n + 1), 2):
                kb.tell(~atom('Is', r, c1, v) | ~atom('Is', r, c2, v))
    
    
    # No two cells in the same column hold the same value.
    for c in range(1, n + 1):
        for v in range(1, n + 1):
            for r1, r2 in combinations(range(1, n + 1), 2):
                kb.tell(~atom('Is', r1, c, v) | ~atom('Is', r2, c, v))
                
    # No two cells in the same box hold the same value.
    for br in range(n//box_h):
        for bc in range(n//box_w):
            r_start = br * box_h + 1
            r_end = r_start + box_h
            c_start = bc * box_w + 1
            c_end = c_start + box_w
            box_cells = [(r, c) for r in range(r_start, r_end) for c in range(c_start, c_end)]
            for (r1, c1), (r2, c2) in combinations(box_cells, 2):
                for v in range(1, n + 1):
                    kb.tell(~atom('Is', r1, c1, v) | ~atom('Is', r2, c2, v))
    
    # The **givens** cells hold their stated values.
    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    return kb


def build_definite_kb(n, box_h, box_w, givens):
    """Return a PropDefiniteKB encoding this n x n Sudoku's constraints plus
    the given cells, using elimination + last-candidate reasoning.

    Parameters
    ----------
    n, box_h, box_w : int
    givens : dict[(int, int), int] -- {(row, col): value}, 1-indexed

    Returns
    -------
    PropDefiniteKB
    """
    kb = PropDefiniteKB()

    # elimination
    # Each cell is assigned **at most one** value from $\{1, \dots, n\}$
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v1 in range(1, n + 1):
                for v2 in range(1, n + 1):
                    if v2 != v1:
                        kb.tell(atom('Is', r, c, v1) |'==>'| atom('Not', r, c, v2))
    
    # No two cells in the same row/column/box hold the same value.
    def peers(r, c, n, box_h, box_w):
        result = set()
        for i in range(1, n + 1):
            if i != r:
                result.add((i, c))
        for j in range(1, n + 1):
            if j != c:
                result.add((r, j))
        r_start = (r - 1) // box_h * box_h + 1
        c_start = (c - 1) // box_w * box_w + 1
        for r1 in range(r_start, r_start + box_h):
            for c1 in range(c_start, c_start + box_w):
                if (r1, c1) != (r, c):
                    result.add((r1, c1))
        return result
    
    for r in range(1, n + 1):
        for c in range(1, n + 1):
                for (r2, c2) in peers(r, c, n, box_h, box_w):  
                    for v in range(1, n + 1):
                        kb.tell(atom('Is', r, c, v) |'==>'| atom('Not', r2, c2, v))
    
    # last-candidate reasoning
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v0 in range(1, n + 1):
                premise = None
                for v in range(1, n + 1):
                    if v != v0:
                        if premise is None:
                            premise = atom('Not', r, c, v) 
                        else:
                            premise = premise & atom('Not', r, c, v)
                kb.tell(premise |'==>'| atom('Is', r, c, v0))
    
    # The **givens** cells hold their stated values.
    for (r, c), v in givens.items():
        kb.tell(atom('Is', r, c, v))

    return kb


class _PremiseIndexedKB(PropDefiniteKB):
    """Read-only inference view with fast premise lookup.

    The provided pl_fc_entails is unchanged. Its normal lookup scans all
    clauses for every inferred fact; this view indexes the same clauses once.
    Create a new view if the underlying puzzle or rules change.
    """

    def __init__(self, source):
        super().__init__()
        self.clauses = list(source.clauses)
        self._by_premise = {}
        for clause in self.clauses:
            if clause.op == '==>':
                for premise in set(conjuncts(clause.args[0])):
                    self._by_premise.setdefault(premise, []).append(clause)

    def clauses_with_premise(self, premise):
        return self._by_premise.get(premise, [])


def solve_full_grid_fc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + pl_fc_entails.

    Returns
    -------
    dict[(int, int), int] -- {(row, col): value} for every cell
    """
    kb = _PremiseIndexedKB(build_definite_kb(n, box_h, box_w, givens))
    solved = {}

    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                query = atom("Is", r, c, v)

                if pl_fc_entails(kb, query):
                    solved[(r, c)] = v
                    break
            else:
                raise ValueError(
                    f"No value can be proved for cell ({r}, {c})"
                )

    return solved

def pl_bc_entails(kb, query):
    clauses = tuple(kb.clauses)
    if getattr(kb, '_bc_clauses', None) != clauses:
        kb._bc_known = set()
        kb._bc_rules = {}

        for clause in clauses:
            premises, head = parse_definite_clause(clause)
            if not premises:
                kb._bc_known.add(head)
            else:
                kb._bc_rules.setdefault(head, []).append(premises)

        kb._bc_clauses = clauses

    known = kb._bc_known
    failed, path = set(), set()

    def prove(goal):
        if goal in known:
            return True
        if goal in failed or goal in path:
            return False

        path.add(goal)
        try:
            for premises in kb._bc_rules.get(goal, []):
                for premise in premises:
                    if not prove(premise):
                        break
                else:
                    known.add(goal)
                    failed.clear()
                    return True

            failed.add(goal)
            return False
        finally:
            path.remove(goal)

    return prove(query)


def solve_full_grid_bc(n, box_h, box_w, givens):
    """Solve the whole puzzle using build_definite_kb + your own pl_bc_entails.

    For each cell, try each candidate value until pl_bc_entails confirms one
    -- the same per-cell strategy as solve_full_grid_fc, but backed by
    backward chaining instead of a single shared forward-chaining pass.

    Returns
    -------
    dict[(int, int), int] -- {(row, col): value} for every cell
    """
    kb = build_definite_kb(n, box_h, box_w, givens)
    solved = {}
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v in range(1, n + 1):
                if pl_bc_entails(kb, atom('Is', r, c, v)):
                    solved[(r, c)] = v
                    break
            else:
                raise ValueError(f'No value can be proved for cell ({r}, {c})')
    return solved
