"""Stage 3 (Enrich) connectors — knowledge graph and market signals, each behind a
swappable interface so the underlying access method/source can change at config time
without touching `enrich.py`. See `base.py` for the interfaces, `obsidian.py` for the
knowledge-graph backends, `signals.py` for the market-signals backends.
"""
