"""The shape the lint exists to catch, reduced to two methods.

`record` is called from another module. `set_merge_outcome` is the update path nothing
calls -- the real defect, which shipped in this repository and was found by hand weeks
later with its own tests passing the whole time.
"""


class GraphStore:
    def record(self, row: dict) -> None:
        self._rows.append(row)

    def set_merge_outcome(self, pr_number: int, merged: bool) -> None:
        self._rows.append({"pr": pr_number, "merged": merged})
