# backend/app/domain/exceptions.py
class DomainException(Exception):
    pass

class EntityNotFoundException(DomainException):
    pass

class AccessDeniedException(DomainException):
    pass

class RateLimitExceededException(DomainException):
    def __init__(self, ttl: int):
        self.ttl = ttl

class ImageValidationException(DomainException):
    pass