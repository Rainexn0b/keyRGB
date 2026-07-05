# Commit procedure

Single-line flow:

```bash
.venv/bin/python -m buildpython --profile=full --with-black
git add .
git commit -m "comment"
git push
```

Detailed flow:

```bash
.venv/bin/python -m buildpython --profile=full --with-black --continue-on-error
git add -p
git commit
git push
```
