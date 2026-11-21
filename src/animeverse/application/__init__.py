"""Application layer: the use cases, and the ports (contracts) they need.

It depends only on the domain. It never imports a database driver, an HTTP
client or a web framework: those live in infrastructure and are plugged in
through the ports.
"""
