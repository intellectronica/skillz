"""Module for counting numbers and identifying primes."""


def is_prime(n: int) -> bool:
    """
    Check if a number is prime.

    Args:
        n: The number to check

    Returns:
        True if n is prime, False otherwise
    """
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True


def count_with_primes(start: int = 1, end: int = 23) -> str:
    """
    Count from start to end and mark prime numbers with an asterisk.

    Args:
        start: Starting number (inclusive)
        end: Ending number (inclusive)

    Returns:
        A string with numbers, primes marked with asterisks
    """
    result = []
    for n in range(start, end + 1):
        if is_prime(n):
            result.append(f"{n}*")
        else:
            result.append(str(n))
    return " ".join(result)


def main() -> None:
    """Print numbers from 1 to 23 with primes marked."""
    print(count_with_primes(1, 23))


if __name__ == "__main__":
    main()
