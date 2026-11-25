"""Wind relative to the aircraft: headwind/tailwind and crosswind components."""
import math


def components(hdg, wind_dir, wind_kt):
    """hdg and wind_dir in degrees true (wind_dir = where the wind comes FROM).

    Returns (rel, head, cross):
      rel   -- angle the wind comes from, clockwise from the nose (0 = straight ahead)
      head  -- headwind in kt (negative = tailwind)
      cross -- crosswind in kt (positive = from the right, negative = from the left)
    """
    rel = (wind_dir - hdg) % 360.0
    r = math.radians(rel)
    return rel, wind_kt * math.cos(r), wind_kt * math.sin(r)
