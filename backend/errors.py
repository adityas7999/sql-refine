"""Typed, sanitized errors shared by API modules."""


class ApiError(Exception):
    def __init__(self, message: str, *, code: str = "BAD_REQUEST", status: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


class ValidationError(ApiError):
    def __init__(self, message: str, code: str = "INVALID_REQUEST"):
        super().__init__(message, code=code, status=400)


class ConnectionSessionError(ApiError):
    def __init__(self, message: str = "The connection session is missing or expired."):
        super().__init__(message, code="CONNECTION_SESSION_EXPIRED", status=401)


class DatabaseAccessError(ApiError):
    def __init__(self, message: str = "MySQL rejected the operation or the database is unavailable.", code: str = "DATABASE_ERROR", status: int = 422):
        super().__init__(message, code=code, status=status)


class QueryTimeoutError(ApiError):
    def __init__(self):
        super().__init__("MySQL stopped the analysis because it exceeded the configured timeout.", code="QUERY_TIMEOUT", status=408)

