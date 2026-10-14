"""NLP for review text.

tagging.py   - Rationale 1: theme tags that feed the recommender as evidence.
polarity.py  - Rationale 2: per-theme polarity that drives internal conflict flags.
pipeline.py  - load -> extract -> ZIP summary -> flags; crowd_themes() for MCP.
config.py    - taxonomy, lexicons, thresholds.
"""
