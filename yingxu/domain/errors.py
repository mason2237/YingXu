"""Stable use-case errors, independent of transport and GUI."""
class ProtocolError(Exception):
    def __init__(self, code, message, *, request_id=None, retryable=False):
        super().__init__(message)
        self.code, self.message = code, message
        self.request_id, self.retryable = request_id, retryable
