"""Per-page metadata for the detector: objects to count and events that must be visible (written by hand for the test set; in the pipeline the planner writes must_show)."""
OBJECTS = {("mira", 1): ["red kite"], ("mira", 3): ["red kite"], ("mira", 4): ["red kite"], ("boat", 2): ["fishing rod"], ("boat", 3): ["fishing rod"], ("boat", 4): ["fishing rod"], ("boat", 5): ["fishing rod"],
           ("fox", 3): ["lantern"], ("fox", 4): ["lantern"]}
MUST = {("mira", 4): ["the kite string has snapped: the red kite flies away alone and the girl holds only a loose end of string"], ("mira", 5): ["the fisherman holds up the red kite"],
        ("mira", 3): ["a red kite flies high in the sky"], ("arcania", 5): ["a crowd of people stands around the prince"], ("boat", 4): ["a silver fish is caught on the fishing line"],
        ("boat", 5): ["ducks fly up from the water"], ("fox", 3): ["a small lantern stands in the snow"], ("fox", 5): ["the two friends sleep side by side"]}
