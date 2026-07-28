"""The published contract. A third-party adapter author imports from here and nothing in
this tree has to call any of it for that to be working as designed."""


class Finding:
    def __init__(self, detector: str) -> None:
        self.detector = detector


def make_finding(detector: str) -> Finding:
    return Finding(detector)
