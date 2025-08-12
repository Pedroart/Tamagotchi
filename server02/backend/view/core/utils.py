def lerp(a, b, t): return a + (b - a) * t

def shade_color(base, far, k):
    return (int(lerp(base[0], far[0], k)),
            int(lerp(base[1], far[1], k)),
            int(lerp(base[2], far[2], k)))
