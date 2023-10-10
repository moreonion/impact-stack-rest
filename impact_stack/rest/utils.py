"""Define various helper functions."""

import datetime

# Proxy for datetime.now() so that it can be stubbed while testing.
now = datetime.datetime.now
