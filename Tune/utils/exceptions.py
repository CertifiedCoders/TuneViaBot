# Authored By Certified Coders © 2025
from typing import Union, Tuple

try:
    from pytgcalls.exceptions import NoActiveGroupCall
except ImportError:
    NoActiveGroupCall = type("NoActiveGroupCall", (Exception,), {})

try:
    from pyrogram.errors import (
        FloodWait,
        ChatWriteForbidden,
        UserNotParticipant,
        ChatAdminRequired,
    )
except ImportError:
    FloodWait = type("FloodWait", (Exception,), {})
    ChatWriteForbidden = type("ChatWriteForbidden", (Exception,), {})
    UserNotParticipant = type("UserNotParticipant", (Exception,), {})
    ChatAdminRequired = type("ChatAdminRequired", (Exception,), {})


class AssistantErr(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ExpectedError(Exception):
    pass


EXPECTED_EXCEPTIONS: Tuple[type, ...] = (
    NoActiveGroupCall,
    UserNotParticipant,
    ChatWriteForbidden,
)

GRACEFUL_EXCEPTIONS: Tuple[type, ...] = (
    ChatAdminRequired,
    FloodWait,
)

SILENT_EXCEPTIONS: Tuple[type, ...] = (
    KeyboardInterrupt,
    SystemExit,
    GeneratorExit,
    AssistantErr,
)


def is_expected_error(err: Union[Exception, BaseException]) -> bool:
    return isinstance(err, EXPECTED_EXCEPTIONS)


def is_graceful_error(err: Union[Exception, BaseException]) -> bool:
    return isinstance(err, GRACEFUL_EXCEPTIONS)


def is_silent_error(err: Union[Exception, BaseException]) -> bool:
    return isinstance(err, SILENT_EXCEPTIONS)


def is_ignored_error(err: Union[Exception, BaseException]) -> bool:
    return (
        is_silent_error(err) or
        is_expected_error(err) or
        is_graceful_error(err)
    )


def should_log_error(err: Union[Exception, BaseException]) -> bool:
    return not is_ignored_error(err)
