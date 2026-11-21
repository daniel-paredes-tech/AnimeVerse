"""Lets `python -m animeverse` work like the `animeverse` command."""

import sys

from animeverse.entrypoints.cli import main

sys.exit(main())
