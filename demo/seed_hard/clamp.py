def clamp(n: int, lo: int, hi: int) -> int:
    if n < lo:
        return hi
    if n > hi:
        return lo
    return n
