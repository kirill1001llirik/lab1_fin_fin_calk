from decimal import Decimal
import unittest

from financial_calculator.logic import (
    CalculationError,
    calculate,
    calculate_two_operands,
    format_result,
    parse_fixed_number,
    round_to_integer,
)


class FixedNumberTests(unittest.TestCase):
    def test_accepts_dot_comma_and_grouped_spaces(self) -> None:
        self.assertEqual(parse_fixed_number("12.5"), Decimal("12.5000000000"))
        self.assertEqual(parse_fixed_number("-12,5"), Decimal("-12.5000000000"))
        self.assertEqual(parse_fixed_number("1 234 567,89"), Decimal("1234567.8900000000"))

    def test_rejects_invalid_grouped_spaces(self) -> None:
        invalid_values = ["1  234.56", "12 34.56", "1234 567.89", "1 23 5.67"]
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(CalculationError):
                    parse_fixed_number(value)

    def test_rejects_exponential_and_wrong_sign_position(self) -> None:
        for value in ["123e+2", "0.0-1"]:
            with self.subTest(value=value):
                with self.assertRaises(CalculationError):
                    parse_fixed_number(value)

    def test_adds_subtracts_multiplies_and_divides(self) -> None:
        self.assertEqual(calculate_two_operands("2", "3", "+"), Decimal("5.0000000000"))
        self.assertEqual(calculate_two_operands("2", "3", "-"), Decimal("-1.0000000000"))
        self.assertEqual(calculate_two_operands("2", "3", "*"), Decimal("6.0000000000"))
        self.assertEqual(calculate_two_operands("1", "3", "/"), Decimal("0.3333333333"))

    def test_division_by_zero_is_error(self) -> None:
        with self.assertRaises(CalculationError):
            calculate_two_operands("10", "0", "/")

    def test_detects_overflow(self) -> None:
        with self.assertRaises(CalculationError):
            calculate_two_operands("1 000 000 000 000", "0.0000000001", "+")

        with self.assertRaisesRegex(CalculationError, "Переполнение"):
            parse_fixed_number("99999999999999999999999")

    def test_huge_multiplication_reports_overflow_without_breaking_next_calculation(self) -> None:
        with self.assertRaisesRegex(CalculationError, "Переполнение"):
            calculate_two_operands("99999999999", "99999999999", "*")

        self.assertEqual(calculate_two_operands("2", "3", "+"), Decimal("5.0000000000"))

    def test_four_operand_expression_uses_parentheses_and_priority(self) -> None:
        result = calculate(["2", "3", "4", "5"], ["+", "*", "*"], "math")
        self.assertEqual(result.value, Decimal("62.0000000000"))
        self.assertEqual(result.rounded, Decimal("62"))

    def test_left_to_right_for_equal_priority_after_parentheses(self) -> None:
        result = calculate(["100", "10", "5", "2"], ["-", "-", "-"], "math")
        self.assertEqual(result.value, Decimal("93.0000000000"))

    def test_rounding_methods_to_integer(self) -> None:
        self.assertEqual(round_to_integer(Decimal("2.5"), "math"), Decimal("3"))
        self.assertEqual(round_to_integer(Decimal("2.5"), "bank"), Decimal("2"))
        self.assertEqual(round_to_integer(Decimal("2.9"), "truncate"), Decimal("2"))
        self.assertEqual(round_to_integer(Decimal("-2.5"), "math"), Decimal("-3"))
        self.assertEqual(round_to_integer(Decimal("-2.9"), "truncate"), Decimal("-2"))

    def test_formats_result_with_spaces_dot_and_without_trailing_zeros(self) -> None:
        self.assertEqual(format_result(Decimal("1000000000000.0000000000")), "1 000 000 000 000")
        self.assertEqual(format_result(Decimal("-1234567.5000000000")), "-1 234 567.5")
        self.assertEqual(format_result(Decimal("0.3333333333")), "0.3333333333")


if __name__ == "__main__":
    unittest.main()
