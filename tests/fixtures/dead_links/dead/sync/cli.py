"""Module-scope use of `open_pr`, so the only symbol left dead is the one under test."""

from sync.forge.github import open_pr

RUNNER = open_pr
