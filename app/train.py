"""Train and compare the fleet, then save the winner:  uv run python -m app.train [--fast]"""

from __future__ import annotations

import sys

from app import model


def main() -> None:
    fast = "--fast" in sys.argv
    print("Training the fleet with 5-fold cross-validation + grid search" + (" (fast)" if fast else "") + "...")
    bundle = model.train(fast=fast, verbose=True)
    path = model.save(bundle)
    print(f"Winner: {bundle['best']} - saved to {path}")


if __name__ == "__main__":
    main()
