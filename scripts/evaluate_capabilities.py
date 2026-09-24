"""Compare original tools with selected, already-reviewed published extensions.

Uses the shared fixed-input experiment CLI and never publishes tools itself.
"""

from evaluate_decisions import main

if __name__ == "__main__":
    main(intervention="tools")
