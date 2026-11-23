"""Entrypoints: the ways to run AnimeVerse (the `animeverse` command, and the API with the web UI).

This is the only layer that knows every concrete class: it reads the
settings, builds the adapters and hands them to the use cases.
"""
