# Setup

Add the freeze-transitive hook to you pre-commit configuration.

```yaml
repos:
  # Add freeze-transitive to the end of repos, it's important it's the last repository
  # as environments for previous hooks must be setup before it runs.
  - repo: https://github.com/antonagestam/freeze-transitive
    # rev: ...
    hooks:
      - id: freeze-transitive
```

Copy your pre-commit configuration to a template file. From now on
`.pre-commit-hooks.yaml` acts as a lockfile and you should make no manual edits to it,
instead make edits in `.pre-commit-template.yaml`. Both files should be checked into
version control.

```sh
$ cp .pre-commit-hooks.yaml .pre-commit-template.yaml
```

Now run pre-commit and verify it has updated `.pre-commit-hooks.yaml` with all
transitive dependencies pinned.

```sh
$ pre-commit run --all-files
```

To run autoupdate, you need to point pre-commit at the template file.

```sh
$ pre-commit autoupdate --config=.pre-commit-template.yaml
```
