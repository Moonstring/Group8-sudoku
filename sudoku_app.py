"""A small Streamlit interface for the IT5005 propositional Sudoku solver."""

import json
import time
from collections import deque
from pathlib import Path

import streamlit as st

from logic_ import parse_definite_clause
from sudoku_solver import (
    atom,
    build_definite_kb,
    build_general_kb,
    solve_full_grid_fc,
    solve_full_grid_bc,
    pl_bc_entails,
)


def load_puzzles():
    """Keep only givens; reference solutions never enter the application."""
    with Path(__file__).with_name('puzzles.json').open(encoding='utf-8') as stream:
        raw = json.load(stream)
    puzzles = [
        {tuple(map(int, key.split('_'))): int(value)
         for key, value in puzzle['givens'].items()}
        for puzzle in raw['puzzles']
    ]
    return raw['n'], raw['box_h'], raw['box_w'], puzzles


def trace_forward(kb, target):
    """Record actual Horn rule firings for an explanation of one query.

    This UI-only helper does not replace either core solver. Start exclusively
    from KB clauses, not BC's memoized conclusions, to retain complete proofs.
    Each new conclusion stores its rule and already-established premises.
    """
    records, rules, pending, index = {}, [], [], {}
    for clause in kb.clauses:
        premises, head = parse_definite_clause(clause)
        if not premises:
            records.setdefault(head, {'premises': (), 'rule': None})
        else:
            premises = tuple(dict.fromkeys(premises))
            rule_id = len(rules)
            rules.append((premises, head, clause))
            pending.append(len(premises))
            for premise in premises:
                index.setdefault(premise, []).append(rule_id)

    agenda = deque(sorted(records, key=str))
    while agenda and target not in records:
        fact = agenda.popleft()
        for rule_id in index.get(fact, ()):
            pending[rule_id] -= 1
            if pending[rule_id] == 0:
                premises, head, rule = rules[rule_id]
                if head not in records:
                    records[head] = {'premises': premises, 'rule': rule}
                    agenda.append(head)
    return records


def proof_order(records, target):
    """Return only the target's dependencies, with premises before conclusions."""
    ordered, visited = [], set()

    def visit(fact):
        if fact in visited or fact not in records:
            return
        visited.add(fact)
        for premise in records[fact]['premises']:
            visit(premise)
        ordered.append(fact)

    visit(target)
    return ordered


def unpack_atom(fact):
    text = str(fact)
    prefix = 'Not' if text.startswith('Not') else 'Is'
    return prefix, *map(int, text[len(prefix):].split('_'))


def elimination_sentence(fact, records, box_h, box_w):
    """Translate a fired elimination rule into a board-specific sentence."""
    _, r, c, v = unpack_atom(fact)
    source = records[fact]['premises'][0]
    _, sr, sc, sv = unpack_atom(source)
    if (r, c) == (sr, sc):
        return f'Exclude {v}: R{r}C{c} is already {sv}.'
    if r == sr:
        unit = f'row {r}'
    elif c == sc:
        unit = f'column {c}'
    elif (r - 1) // box_h == (sr - 1) // box_h and (c - 1) // box_w == (sc - 1) // box_w:
        unit = 'the same box'
    else:
        raise ValueError('The recorded elimination does not share a Sudoku unit.')
    origin = 'given' if not records[source]['premises'] else 'proved earlier in this explanation'
    return f'Exclude {v}: R{sr}C{sc} = {sv} ({origin}) shares {unit} with R{r}C{c}.'


def board_html(n, box_h, box_w, givens, values, selected=None):
    css = '''<style>
    .sudoku-wrap {max-width: 510px; margin: 0 auto; padding: 2px 0 16px;}
    .sudoku-board {width:100%; border-collapse:collapse; table-layout:fixed;
        font-family: ui-sans-serif, system-ui, sans-serif; color:#172b4d;}
    .sudoku-board th {font-size:12px; font-weight:500; color:#718198;
        height:25px; border:0; text-align:center;}
    .sudoku-board th:first-child {width:24px;}
    .sudoku-board td {border:1px solid #cdd7e4; text-align:center;
        padding:0; height:46px; font-size:23px; background:#ffffff;}
    .sudoku-board td.given {background:#eef2f7; font-weight:750; color:#182c48;}
    .sudoku-board td.deduced {color:#235dcc; font-weight:550;}
    .sudoku-board td.box-top {border-top:2px solid #6a7d96;}
    .sudoku-board td.box-bottom {border-bottom:2px solid #6a7d96;}
    .sudoku-board td.box-left {border-left:2px solid #6a7d96;}
    .sudoku-board td.box-right {border-right:2px solid #6a7d96;}
    .sudoku-board td.selected {background:#fff2c7; box-shadow:inset 0 0 0 2px #dca734;}
    .sudoku-legend {display:flex; flex-wrap:wrap; gap:16px; margin:14px 0 0 24px;
        color:#64748b; font-size:12px;}
    .sudoku-legend b {color:#182c48;} .sudoku-legend .blue {color:#235dcc;}
    .sudoku-legend .gold {color:#977015;}
    @media (max-width:520px) {.sudoku-board td {height:35px; font-size:20px;}}
    </style>'''
    parts = [css, '<div class="sudoku-wrap"><table class="sudoku-board" aria-label="Sudoku board">',
             '<thead><tr><th></th>']
    parts.extend(f'<th scope="col">{c}</th>' for c in range(1, n + 1))
    parts.append('</tr></thead><tbody>')
    for r in range(1, n + 1):
        parts.append(f'<tr><th scope="row">{r}</th>')
        for c in range(1, n + 1):
            value = values.get((r, c))
            classes = ['given' if (r, c) in givens else 'deduced']
            if (r - 1) % box_h == 0:
                classes.append('box-top')
            if r % box_h == 0:
                classes.append('box-bottom')
            if (c - 1) % box_w == 0:
                classes.append('box-left')
            if c % box_w == 0:
                classes.append('box-right')
            if (r, c) == selected:
                classes.append('selected')
            label = f'Row {r}, column {c}: {value if value is not None else "empty"}'
            parts.append(f'<td class="{" ".join(classes)}" aria-label="{label}">'
                         f'{int(value) if value is not None else "&nbsp;"}</td>')
        parts.append('</tr>')
    parts.append('</tbody></table><div class="sudoku-legend">'
                 '<span><b>Given</b> · shaded</span><span class="blue">Deduced · blue</span>'
                 '<span class="gold">Queried cell · yellow</span></div></div>')
    return ''.join(parts)


def render_reasoning(result, box_h, box_w):
    st.subheader('Why this result?')
    r, c, v = result['query']
    records, target = result['trace'], result['target']
    st.caption(f'Explanation for R{r}C{c} = {v}. '
               'These steps are recorded from forward chaining on the same puzzle rules; '
               'the True / False check above uses backward chaining.')
    if target not in records:
        st.info('No proof was found for this value or its exclusion under the current rules.')
        return
    order = proof_order(records, target)
    initial = [fact for fact in order if not records[fact]['premises']]
    fills = [fact for fact in order
             if records[fact]['premises'] and unpack_atom(fact)[0] == 'Is']
    fact_labels = [f'R{r0}C{c0} = {v0}' for _, r0, c0, v0 in map(unpack_atom, initial)]
    with st.expander(f'Starting clues · {len(initial)} givens', expanded=not fills):
        st.write(', '.join(fact_labels))
    for step, fact in enumerate(fills, start=1):
        _, fr, fc, fv = unpack_atom(fact)
        with st.expander(f'{step}. R{fr}C{fc} = {fv} · last remaining candidate',
                         expanded=fact == target):
            st.markdown('\n'.join(
                '- ' + elimination_sentence(premise, records, box_h, box_w)
                for premise in records[fact]['premises']
            ))
            st.write(f'Every other value is excluded, so R{fr}C{fc} must be {fv}.')
    if unpack_atom(target)[0] == 'Not':
        with st.expander(f'Why R{r}C{c} cannot be {v}', expanded=True):
            st.write(elimination_sentence(target, records, box_h, box_w))
    elif not records[target]['premises']:
        st.info(f'R{r}C{c} = {v} is an initial clue, so no deduction is needed.')


def main():
    st.set_page_config(page_title='Sudoku Solver', page_icon='🔢', layout='centered')
    st.html('<style>.stMainBlockContainer {max-width:1080px; padding-top:2rem;}'
            'h1 {letter-spacing:-0.04em;} h3 {letter-spacing:-0.02em;}</style>')
    st.title('Sudoku Solver')
    st.caption('Choose a puzzle, solve the grid, or explore why a number belongs in a cell.')
    n, box_h, box_w, puzzles = load_puzzles()
    puzzle_index = st.selectbox(
        'Puzzle', range(len(puzzles)), key='puzzle_selector',
        format_func=lambda i: f'Puzzle {i + 1} · {len(puzzles[i])} givens',
    )
    givens = puzzles[puzzle_index]
    if st.session_state.get('active_puzzle') != puzzle_index:
        st.session_state.active_puzzle = puzzle_index
        st.session_state.puzzle_result = None
        st.session_state.query_result = None
        st.session_state.query_kb = None

    board_column, control_column = st.columns([1.12, 1], gap='large')
    with control_column:
        st.subheader('Solve the puzzle')
        algorithm = st.radio('Algorithm', ['Backward chaining', 'Forward chaining'],
                             key='algorithm', horizontal=True)
        st.caption('Forward chaining takes longer. Both methods use the same puzzle rules.')
        solve_column, reset_column = st.columns([1.5, 1])
        solve_clicked = solve_column.button('Solve grid', type='primary',
                                             use_container_width=True, key='solve_grid')
        reset_clicked = reset_column.button('Reset', use_container_width=True, key='reset')
        if reset_clicked:
            st.session_state.puzzle_result = None
            st.session_state.query_result = None
            st.session_state.query_kb = None
        if solve_clicked:
            solver = solve_full_grid_bc if algorithm == 'Backward chaining' else solve_full_grid_fc
            with st.spinner(f'Solving with {algorithm.lower()}…'):
                started = time.perf_counter()
                try:
                    values = solver(n, box_h, box_w, givens)
                except (ValueError, RecursionError) as error:
                    st.error(f'The current rules could not complete this puzzle: {error}')
                else:
                    st.session_state.puzzle_result = {
                        'values': values, 'algorithm': algorithm,
                        'seconds': time.perf_counter() - started,
                    }
        solved = st.session_state.puzzle_result
        if solved:
            st.success(f"Solved · {solved['seconds']:.2f} s · {solved['algorithm']}")

        st.subheader('Check a cell')
        with st.form('cell_query'):
            row_col, column_col, value_col = st.columns(3)
            r = row_col.number_input('Row', 1, n, 2, step=1, key='query_row')
            c = column_col.number_input('Column', 1, n, 2, step=1, key='query_column')
            v = value_col.number_input('Value', 1, n, 9, step=1, key='query_value')
            check_clicked = st.form_submit_button('Check & explain', use_container_width=True)
        if check_clicked:
            with st.spinner('Checking the cell and recording its explanation…'):
                if st.session_state.query_kb is None:
                    st.session_state.query_kb = build_definite_kb(n, box_h, box_w, givens)
                kb = st.session_state.query_kb
                query = atom('Is', r, c, v)
                verdict = bool(pl_bc_entails(kb, query))
                target = query if verdict else atom('Not', r, c, v)
                st.session_state.query_result = {
                    'query': (r, c, v), 'verdict': verdict, 'target': target,
                    'trace': trace_forward(kb, target),
                }
        result = st.session_state.query_result
        if result:
            qr, qc, qv = result['query']
            if result['verdict']:
                st.success(f'True — R{qr}C{qc} = {qv} is entailed.')
            else:
                st.info(f'False — R{qr}C{qc} = {qv} is not entailed.')

    with board_column:
        st.subheader('Your board')
        st.caption(f'{n} × {n} grid · {len(givens)} given · {n*n-len(givens)} to deduce')
        values = st.session_state.puzzle_result['values'] if st.session_state.puzzle_result else givens
        result = st.session_state.query_result
        selected = result['query'][:2] if result else None
        st.html(board_html(n, box_h, box_w, givens, values, selected))
    st.divider()
    if st.session_state.query_result:
        render_reasoning(st.session_state.query_result, box_h, box_w)
    else:
        st.subheader('Explore the reasoning')
        st.write('Enter a row, column and value, then choose **Check & explain** '
                 'to see the clues and deduction steps behind the result.')
        if puzzle_index == 0:
            st.caption('Try R2C2 = 9 in Puzzle 1 for a short, clear example.')


if __name__ == '__main__':
    main()
