# Contributing to piscout

Thanks for helping! Bug fixes, docs and small improvements are welcome.

## Quick start (Windows)

```bash
git clone https://github.com/<you>/piscout   # your fork
cd piscout
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m pytest               # all tests should pass
.venv\Scripts\python run_gui.py              # run the app
```

## Pull requests

- One change per pull request, on a branch of your fork. Mention `Closes #<issue>` if it fixes one. Look for issues labelled
  [good first issue](https://github.com/MilkteaTW1/piscout/labels/good%20first%20issue) and comment on one to say you are taking it.
- Add or extend a test in `tests/` for what you change.
- Be careful with anything that touches a Raspberry Pi or an SD card: describe how you tested it, and never test flashing on a drive you care about.
- The maintainer makes the releases; a merged change reaches users with the next one.

Security problems: see [SECURITY.md](SECURITY.md), not a public issue.
