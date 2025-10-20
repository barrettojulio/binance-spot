def clamp01(x):
    return max(0.0, min(1.0, float(x) if x is not None else 0.0))
