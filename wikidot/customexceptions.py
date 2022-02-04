# -*- coding: utf-8 -*-
# Docstring completed
"""Exceptions for wikidot.py"""
from __future__ import annotations


class WikidotError(Exception):
    """A base exception of all custom exceptions in wikidot.py

    Parameters
    ----------
    message
        Error message
    """

    def __init__(self, message: str):
        super().__init__(message)


class TemporaryErrorForHandle(WikidotError):
    """Temporary exception for temporarily remembering that other exception has occurred. This exception should not be eventually raised.

    Parameters
    ----------
    message
        Error message
    """

    def __init__(self, message: str):
        super().__init__(message)


class SessionCreateError(WikidotError):
    """Exception indicating that an error has occurred while logging in or out of Wikidot.

    Parameters
    ----------
    message
        Error message
    """

    def __init__(self, message: str):
        super().__init__(message)


class RequestError(WikidotError):
    """Base exception for errors related to request.

    Parameters
    ----------
    message
        Error message
    """

    def __init__(self, message: str):
        super().__init__(message)


class AMCRequestError(RequestError):
    """Exception raised when ajax-module-connector.php returns an unexpected response code.

    Parameters
    ----------
    message
        Error message
    status_code
        HTTP status code (mainly 4xx or 5xx)
    """

    def __init__(self, message: str, *, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class Forbidden(RequestError):
    """Exception raised when you don't have permission to do something you try.

    Parameters
    ----------
    message
        Error message
    """

    def __init__(self, message: str):
        super().__init__(message)


class NotFound(RequestError):
    """Exception raised when the page you try to do something is not found.

    Parameters
    ----------
    message
        Error message
    """

    def __init__(self, message: str):
        super().__init__(message)


class NotOK(RequestError):
    """Exception raised when the "status" value in the response body of ajax-module-connector.php is not "ok".

    Parameters
    ----------
    message
        Error message
    status_code
        "status" value in the response body
    """

    def __init__(self, message: str, status_code: str):
        super().__init__(message)
        self.status_code = status_code


class ReturnedDataError(RequestError):
    """Exception raised when ajax-module-connector.php response is not in the expected format.

    Parameters
    ----------
    message
        Error message
    reason
        reason code

            * `empty` - when response body is empty
    """

    def __init__(self, message: str, reason=None):
        super().__init__(message)
        self.reason = reason


class FileError(WikidotError):
    """Base exception for errors related to files.

    Parameters
    ----------
    message
        Error message
    """

    def __init__(self, message: str):
        super().__init__(message)


class FileDuplicateError(FileError):
    """Exception raised when name of the file you tried to upload is already taken.

    Parameters
    ----------
    message
        Error message
    name
        Duplicated name

    """

    def __init__(self, message: str, name: str):
        super().__init__(message)
        self.name = name


class NoRequiredDataError(WikidotError):
    """Exception raised when a/some data required for the request is/are insufficient

    Parameters
    ----------
    message
        Error message

    """

    def __init__(self, message: str):
        super().__init__(message)


class PageExistsError(WikidotError):
    """Exception raised when the page you try to create is already exists.

    Parameters
    ----------
    message
        Error message

    """

    def __init__(self, message: str):
        super().__init__(message)


class APIError(RequestError):
    """Base exception for errors related to WikidotAPI.

    Parameters
    ----------
    message
        Error message

    """

    def __init__(self, message: str):
        super().__init__(message)


class APIUnauthorizedError(APIError):
    """Exception raised when Authorized WikidotAPI session is not found, or failed to create session.

    Parameters
    ----------
    message
        Error message

    """

    def __init__(self, message: str):
        super().__init__(message)


class APITargetError(APIError):
    """Exception raised when target site/page is not found.

    Parameters
    ----------
    message
        Error message

    """

    def __init__(self, message: str):
        super().__init__(message)


class APIDisabledError(APIError):
    """Exception raised when the site you try to request is disabled API access.

    Parameters
    ----------
    message
        Error message

    """

    def __init__(self, message: str):
        super().__init__(message)


class ProcessingError(APIError):
    """Exception raised when error occurred while processing a request.

    Parameters
    ----------
    message
        Error message

    """

    def __init__(self, message: str):
        super().__init__(message)
