# Contributing

Ideas, bug reports and pull requests are welcome.

- **Bug in a script?** Open an issue with the command you ran, the error, and (if you can) a few anonymised rows of the input file showing the column names.
- **Better playbook rules?** The writing rules live in `references/`. Keep them specific and testable ("titles ≤ 60 chars"), not general advice.
- **New input format?** Add the column aliases to `COLUMN_ALIASES` in `scripts/analyze_gsc.py` and a sample file to `examples/`.

Before opening a PR, run the sample end to end (commands in the README "Without Claude" section) and make sure `verify_workbook.py` prints `RESULT: PASS`.

Please never commit real client GSC exports or reports. The `.gitignore` blocks `.csv`/`.xlsx` outside `examples/` for that reason.
