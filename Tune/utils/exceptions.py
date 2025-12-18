# Authored By Certified Coders © 2025
from typing import Union, Tuple

# Import pytgcalls exceptions for proper type checking
try:
    from pytgcalls.exceptions import (
        NoActiveGroupCall,
        NoAudioSourceFound,
        NoVideoSourceFound,
        AlreadyJoinedError,
        NotJoinedError,
    )
except ImportError:
    # Fallback if pytgcalls is not available
    NoActiveGroupCall = type("NoActiveGroupCall", (Exception,), {})
    NoAudioSourceFound = type("NoAudioSourceFound", (Exception,), {})
    NoVideoSourceFound = type("NoVideoSourceFound", (Exception,), {})
    AlreadyJoinedError = type("AlreadyJoinedError", (Exception,), {})
    NotJoinedError = type("NotJoinedError", (Exception,), {})

# Import pyrogram exceptions
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
    """
    Custom exception for user-facing errors that should be displayed to users.
    These are expected errors (e.g., "No active call", "Track not found") 
    that don't need to be logged as internal errors.
    """
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ExpectedError(Exception):
    """
    Base class for expected/graceful errors that should be handled silently
    without logging to error channels. These are normal operational conditions.
    """
    pass


# Exception types that are expected and should not be logged as errors
# These represent normal operational states (e.g., no active call, user left chat)
EXPECTED_EXCEPTIONS: Tuple[type, ...] = (
    NoActiveGroupCall,  # No active voice call - expected when VC is not started
    NotJoinedError,     # Assistant not in call - expected during transitions
    AlreadyJoinedError, # Already in call - race condition, not an error
    UserNotParticipant, # User not in chat - expected permission issue
    ChatWriteForbidden, # Bot cannot write - expected permission issue
)

# Exception types that are expected but should be handled gracefully
# These may still need user-facing messages but shouldn't spam logs
GRACEFUL_EXCEPTIONS: Tuple[type, ...] = (
    NoAudioSourceFound,  # Audio source issue - should be handled with user message
    NoVideoSourceFound,  # Video source issue - should be handled with user message
    ChatAdminRequired,   # Admin required - expected permission issue
    FloodWait,          # Rate limiting - expected, should be handled by pyrogram
)

# Exception types that should never be logged (too common/expected)
SILENT_EXCEPTIONS: Tuple[type, ...] = (
    KeyboardInterrupt,  # User interruption
    SystemExit,         # System shutdown
    GeneratorExit,      # Generator cleanup
    AssistantErr,       # User-facing errors - already handled with messages
)


def is_expected_error(err: Union[Exception, BaseException]) -> bool:
    """
    Check if an error is an expected operational condition that shouldn't be logged.
    These are normal states (e.g., no active call) rather than actual errors.
    """
    return isinstance(err, EXPECTED_EXCEPTIONS)


def is_graceful_error(err: Union[Exception, BaseException]) -> bool:
    """
    Check if an error should be handled gracefully with user messages but not logged.
    These are expected issues that need user feedback but aren't system errors.
    """
    return isinstance(err, GRACEFUL_EXCEPTIONS)


def is_silent_error(err: Union[Exception, BaseException]) -> bool:
    """
    Check if an error should be silently ignored (never logged).
    These include user-facing errors and system interrupts.
    """
    return isinstance(err, SILENT_EXCEPTIONS)


def is_ignored_error(err: Union[Exception, BaseException]) -> bool:
    """
    Check if an error should be ignored by the error logging system.
    
    Returns True for:
    - Expected operational states (NoActiveGroupCall, etc.)
    - Silent exceptions (AssistantErr, KeyboardInterrupt, etc.)
    - Graceful errors that are handled with user messages
    
    This is the main function used by error handlers to determine if logging should occur.
    """
    return (
        is_silent_error(err) or
        is_expected_error(err) or
        is_graceful_error(err)
    )


def should_log_error(err: Union[Exception, BaseException]) -> bool:
    """
    Determine if an error should be logged to the error channel.
    Returns True for unexpected system errors that need investigation.
    """
    return not is_ignored_error(err)
