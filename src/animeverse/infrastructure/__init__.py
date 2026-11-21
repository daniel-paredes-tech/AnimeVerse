"""Infrastructure layer: adapters that implement the application's ports.

Everything that talks to the outside world lives here: the AniList API
(anilist/) and PostgreSQL (postgres/). Library errors are translated into
the errors declared in application/ports.py before they leave this layer.
"""
