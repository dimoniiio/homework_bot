class BreakInfiniteLoop(Exception):
    """Исключение для прерывания бесконечных циклов в тестах."""


class ExpectedField(Exception):
    """Исключение для отсутствующих полей в ответе API."""


class StatusApi(Exception):
    """Исключение для статус кода не равного 200."""
