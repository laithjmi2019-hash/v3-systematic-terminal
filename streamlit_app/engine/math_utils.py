import numpy as np

def clamp(value: float, min_val: float, max_val: float) -> float:
    if value is None or np.isnan(value):
        value = 0.0
    return max(min_val, min(max_val, value))

def normalize(value: float, min_val: float, max_val: float) -> float:
    if value is None or np.isnan(value):
        return 0.0
    if value <= min_val:
        return 0.0
    if value >= max_val:
        return 1.0
    return clamp((value - min_val) / (max_val - min_val), 0.0, 1.0)

def inverse_normalize(value: float, min_val: float, max_val: float) -> float:
    if value is None or np.isnan(value):
        return 0.0
    if value <= min_val:
        return 1.0
    if value >= max_val:
        return 0.0
    return clamp((max_val - value) / (max_val - min_val), 0.0, 1.0)

def std_dev(arr: list) -> float:
    if not arr or len(arr) <= 1:
        return 0.0
    return float(np.std(arr, ddof=1))

def mean(arr: list) -> float:
    if not arr or len(arr) == 0:
        return 0.0
    return float(np.mean(arr))

def calculate_volatility_penalty(series: list) -> float:
    m = mean(series)
    if m == 0:
        return 0.5
    sd = std_dev(series)
    return min(sd / abs(m), 0.5)
