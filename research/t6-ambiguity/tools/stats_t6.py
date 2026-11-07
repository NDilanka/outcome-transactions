import math
def binom_cdf(k, n, p):
    return sum(math.comb(n, i) * p**i * (1-p)**(n-i) for i in range(0, k+1))
def cp_interval(x, n, alpha=0.05):
    def bisect(f, lo, hi):
        for _ in range(200):
            mid = (lo+hi)/2
            if f(mid) > 0: hi = mid
            else: lo = mid
        return (lo+hi)/2
    lower = 0.0 if x == 0 else bisect(lambda p: (1-binom_cdf(x-1, n, p)) - alpha/2, 0.0, 1.0)
    upper = 1.0 if x == n else bisect(lambda p: alpha/2 - binom_cdf(x, n, p), 0.0, 1.0)
    return lower, upper
def wilson(x, n, z=1.959964):
    p = x/n; d = 1 + z*z/n
    c = (p + z*z/(2*n))/d; h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return c-h, c+h
if __name__ == '__main__':
    for lab, x, n in [('frozen gate', 1, 39), ('sens gate', 3, 39), ('judge-high gate', 0, 39),
                      ('detector hits', 3, 3), ('detector false alarm', 30, 36), ('judge-alone unint (sens)', 11, 39), ('judge-high-only unint', 4, 39)]:
        cl, cu = cp_interval(x, n); wl, wu = wilson(x, n)
        print(f"{lab:26} {x}/{n} = {x/n:.3f}  CP95 [{cl:.3f}, {cu:.3f}]  Wilson95 [{wl:.3f}, {wu:.3f}]")
    print('independence expected frozen 6*11/39 =', round(6*11/39, 2), '| sens 11*11/39 =', round(11*11/39, 2))
