from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    Decimal,
    DecimalException,
    InvalidOperation,
    ROUND_DOWN,
    ROUND_HALF_EVEN,
    ROUND_HALF_UP,
    localcontext,
)
import re


INPUT_SCALE = Decimal("0.0000000001")
CALC_SCALE = Decimal("0.0000000001")
MAX_ABS_VALUE = Decimal("1000000000000.0000000000")

OPERATIONS = {"+", "-", "*", "/"}
ROUNDING_METHODS = {"math", "bank", "truncate"}

_NUMBER_RE = re.compile(
    r"^[+-]?(?:(?:(?:\d+|\d{1,3}(?: \d{3})+)(?:[.,]\d*)?)|(?:[.,]\d+))$"
)


class CalculationError(ValueError):
    """Raised when user input cannot be calculated."""


@dataclass(frozen=True)
class CalculationResult:
    value: Decimal
    rounded: Decimal


def parse_fixed_number(text: str) -> Decimal:
    """Parse a fixed-point number with dot/comma decimal separator and valid groups."""
    raw = (text or "").strip().replace("\u00a0", " ")

    if not raw:
        raise CalculationError("Введите число.")

    if "e" in raw.lower():
        raise CalculationError("Экспоненциальная запись не поддерживается.")

    if raw.count(".") + raw.count(",") > 1:
        raise CalculationError("Используйте только один разделитель дробной части.")

    if "  " in raw:
        raise CalculationError("Пробелы между разрядами указаны неверно.")

    if not _NUMBER_RE.fullmatch(raw):
        raise CalculationError("Введите обычное число без лишних символов.")

    normalized = raw.replace(" ", "").replace(",", ".")
    if "." in normalized and len(normalized.split(".", 1)[1]) > 10:
        raise CalculationError("Допускается не больше 10 знаков после разделителя.")

    try:
        value = Decimal(normalized)
    except InvalidOperation as exc:
        raise CalculationError("Не удалось прочитать число.") from exc

    _ensure_in_range(value)
    try:
        with localcontext() as context:
            context.prec = 80
            value = value.quantize(INPUT_SCALE, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise CalculationError("Переполнение: число выходит за допустимый диапазон.") from exc
    return _normalize_zero(value)


def calculate(
    operands: list[str] | tuple[str, str, str, str],
    operations: list[str] | tuple[str, str, str],
    rounding_method: str = "math",
) -> CalculationResult:
    """Calculate expression: number1 op1 (number2 op2 number3) op3 number4."""
    if len(operands) != 4:
        raise CalculationError("Введите четыре числа.")
    if len(operations) != 3:
        raise CalculationError("Выберите три операции.")
    if rounding_method not in ROUNDING_METHODS:
        raise CalculationError("Выберите вид округления.")

    values = [parse_fixed_number(value) for value in operands]
    op1, op2, op3 = [_normalize_operation(operation) for operation in operations]

    middle = _apply_operation(values[1], values[2], op2)

    if _operation_priority(op3) > _operation_priority(op1):
        right = _apply_operation(middle, values[3], op3)
        final_value = _apply_operation(values[0], right, op1)
    else:
        left = _apply_operation(values[0], middle, op1)
        final_value = _apply_operation(left, values[3], op3)

    return CalculationResult(
        value=final_value,
        rounded=round_to_integer(final_value, rounding_method),
    )


def calculate_two_operands(left_text: str, right_text: str, operation: str) -> Decimal:
    operation = _normalize_operation(operation)
    return _apply_operation(parse_fixed_number(left_text), parse_fixed_number(right_text), operation)


def round_to_integer(value: Decimal, method: str) -> Decimal:
    if method == "math":
        return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if method == "bank":
        return value.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    if method == "truncate":
        return value.quantize(Decimal("1"), rounding=ROUND_DOWN)
    raise CalculationError("Выберите вид округления.")


def format_result(value: Decimal, max_fraction_digits: int = 10) -> str:
    quantizer = Decimal("1") if max_fraction_digits == 0 else Decimal("1").scaleb(-max_fraction_digits)
    value = _normalize_zero(value.quantize(quantizer, rounding=ROUND_HALF_UP))
    sign = "-" if value < 0 else ""
    text = format(abs(value), "f")

    integer_part, _, fractional_part = text.partition(".")
    grouped_integer = _group_integer(integer_part)
    fractional_part = fractional_part.rstrip("0")

    if fractional_part:
        return f"{sign}{grouped_integer}.{fractional_part}"
    return f"{sign}{grouped_integer}"


def format_fixed(value: Decimal) -> str:
    return format_result(value, max_fraction_digits=10)


def _normalize_operation(operation: str) -> str:
    operation_map = {
        "+": "+",
        "-": "-",
        "*": "*",
        "/": "/",
        "add": "+",
        "subtract": "-",
        "multiply": "*",
        "divide": "/",
    }
    normalized = operation_map.get(str(operation))
    if normalized not in OPERATIONS:
        raise CalculationError("Выберите допустимую операцию.")
    return normalized


def _operation_priority(operation: str) -> int:
    return 2 if operation in {"*", "/"} else 1


def _apply_operation(left: Decimal, right: Decimal, operation: str) -> Decimal:
    try:
        with localcontext() as context:
            context.prec = 80
            result = _calculate_operation(left, right, operation)
    except CalculationError:
        raise
    except DecimalException as exc:
        raise CalculationError("Не удалось выполнить расчет.") from exc

    _ensure_in_range(result)
    try:
        with localcontext() as context:
            context.prec = 80
            rounded = result.quantize(CALC_SCALE, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise CalculationError("Переполнение: число выходит за допустимый диапазон.") from exc
    _ensure_in_range(rounded)
    return _normalize_zero(rounded)


def _calculate_operation(left: Decimal, right: Decimal, operation: str) -> Decimal:
    if operation == "+":
        return left + right
    if operation == "-":
        return left - right
    if operation == "*":
        return left * right
    if operation == "/":
        if right == 0:
            raise CalculationError("Деление на 0 невозможно.")
        return left / right
    raise CalculationError("Выберите допустимую операцию.")


def _ensure_in_range(value: Decimal) -> None:
    if abs(value) > MAX_ABS_VALUE:
        raise CalculationError("Переполнение: число выходит за допустимый диапазон.")


def _normalize_zero(value: Decimal) -> Decimal:
    return Decimal("0").quantize(CALC_SCALE) if value == 0 else value


def _group_integer(integer_part: str) -> str:
    groups = []
    while integer_part:
        groups.append(integer_part[-3:])
        integer_part = integer_part[:-3]
    return " ".join(reversed(groups)) or "0"
