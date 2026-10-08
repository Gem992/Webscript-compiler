// Watch the 'Optimized' tab: folding, propagation, dead code
const WIDTH = 10
const HEIGHT = 5 * 2
const UNUSED = 99
const DEBUG = false

let area = WIDTH * HEIGHT + 0
let scaled = area * 1

if DEBUG {
    print("debug mode")
} else {
    print("area:", area, "scaled:", scaled)
}

while false {
    print("never runs")
}

fn answer() -> int {
    return 6 * 7
    print("unreachable")
}
print(answer())
