"""Tests for prime_counter module."""

from skillz.prime_counter import count_with_primes, is_prime


class TestIsPrime:
    """Tests for the is_prime function."""

    def test_negative_numbers_not_prime(self) -> None:
        assert is_prime(-5) is False
        assert is_prime(-1) is False

    def test_zero_and_one_not_prime(self) -> None:
        assert is_prime(0) is False
        assert is_prime(1) is False

    def test_two_is_prime(self) -> None:
        assert is_prime(2) is True

    def test_small_primes(self) -> None:
        primes = [2, 3, 5, 7, 11, 13, 17, 19, 23]
        for p in primes:
            assert is_prime(p) is True

    def test_small_composites(self) -> None:
        composites = [4, 6, 8, 9, 10, 12, 14, 15, 16, 18, 20, 21, 22]
        for c in composites:
            assert is_prime(c) is False


class TestCountWithPrimes:
    """Tests for the count_with_primes function."""

    def test_count_1_to_23(self) -> None:
        """Test counting from 1 to 23 with primes marked."""
        result = count_with_primes(1, 23)
        expected = (
            "1 2* 3* 4 5* 6 7* 8 9 10 11* 12 13* 14 15 16 17* 18 19* "
            "20 21 22 23*"
        )
        assert result == expected

    def test_count_small_range(self) -> None:
        """Test counting a small range."""
        result = count_with_primes(1, 5)
        expected = "1 2* 3* 4 5*"
        assert result == expected

    def test_count_single_number(self) -> None:
        """Test counting a single number."""
        result = count_with_primes(7, 7)
        assert result == "7*"

    def test_count_no_primes(self) -> None:
        """Test counting range with no primes."""
        result = count_with_primes(8, 10)
        assert result == "8 9 10"
