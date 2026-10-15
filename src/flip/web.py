"""Start the web app: `python -m flip.web`.

It opens in your browser at http://localhost:8501. Stop it with Ctrl+C in
the terminal. Extra options are passed to Streamlit, e.g.
`python -m flip.web --server.port 8502`.
"""

import sys
from pathlib import Path

from streamlit.web import cli


def main() -> None:
    app = Path(__file__).with_name("app.py")
    sys.argv = ["streamlit", "run", str(app), *sys.argv[1:]]
    sys.exit(cli.main())


if __name__ == "__main__":
    main()
