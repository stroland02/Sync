"""The two names the Precedent rename deliberately did not touch.

`CI-W591` renamed the migration corpus to Precedent. `SYNC_CORPUS_SALT` and `.sync-corpus-salt`
kept their names because they are deployment surface: an operator has the variable set and the
file on disk, and `sync.remediate.precedent` argues that the salt must be stable across runs or
the store cannot be joined to itself.

Renaming either would re-salt every digest and orphan every row already written. Nothing would
raise. The rename would look finished and every aggregate would quietly start from zero, which is
the failure this file exists to make impossible to cause by tidying.
"""

from __future__ import annotations

from sync.remediate.precedent import SALT_FILE, SALT_VARIABLE


def test_the_salt_variable_keeps_the_name_operators_already_set():
    assert SALT_VARIABLE == "SYNC_CORPUS_SALT"


def test_the_salt_file_keeps_the_name_already_on_disk():
    assert SALT_FILE.name == ".sync-corpus-salt"
