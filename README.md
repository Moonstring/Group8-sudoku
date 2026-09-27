# Group8-sudoku
IT5005

**Live app:** [Group8 Sudoku Solver](https://group8-sudoku-2vztnnyx5chlwvimukec3c.streamlit.app/)

## Sudoku Solver

A Streamlit app for selecting and solving five Sudoku puzzles with forward or backward chaining, checking individual cell values, and reading step-by-step explanations.

- Full-grid solving uses the shared functions in `sudoku_solver.py`.
- Cell queries use backward chaining.
- Explanations record forward-chaining rule firings on the same knowledge base.
- Puzzle givens are the inference input; reference solutions are used only for validation.

## Run locally

Use Python 3.12, then run from the repository root:

```bash
python -m pip install -r requirements.txt
python -m streamlit run sudoku_app.py
```

For a quick demonstration, select Puzzle 1 and check row 2, column 2, value 9, then value 3.

## Deploy to Streamlit Community Cloud

- Repository: `Moonstring/Group8-sudoku`
- Branch: `main`
- Main file path: `sudoku_app.py`
- Python version in Advanced settings: `3.12`

The dependencies are declared in `requirements.txt`; the optional theme is in `.streamlit/config.toml`.

