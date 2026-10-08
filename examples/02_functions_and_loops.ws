// Functions, recursion, loops
fn factorial(n: int) -> int {
    if n <= 1 {
        return 1
    }
    return n * factorial(n - 1)
}

fn greet(name: string) {
    print("Hello, " + name + "!")
}

greet("WebScript")

for i in range(1, 6) {
    print("factorial(" + str(i) + ") =", factorial(i))
}

let total = 0
let k = 0
while k < 5 {
    total = total + k
    k = k + 1
}
print("sum of 0..4 =", total)
