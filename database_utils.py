import time
import logging
from functools import wraps
from typing import Callable, Any

from sqlalchemy.exc import OperationalError, DisconnectionError
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def retry_db_operation(max_retries: int = 3, delay: float = 1.0):
    """
    FIXED: Decorator to retry database operations on connection failures
    Now handles transactions properly
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DisconnectionError) as e:
                    last_exception = e
                    error_msg = str(e).lower()

                    # Check if it's a connection-related error
                    connection_errors = [
                        'ssl connection has been closed',
                        'connection closed',
                        'server closed the connection',
                        'connection timeout',
                        'connection refused',
                        'connection lost',
                        'server has gone away'
                    ]

                    if any(keyword in error_msg for keyword in connection_errors):
                        if attempt < max_retries:
                            logger.warning(
                                f"Database connection error on attempt {attempt + 1}/{max_retries + 1}: {e}. "
                                f"Retrying in {current_delay} seconds..."
                            )

                            # Try to rollback the session if it exists
                            if args and hasattr(args[1], 'rollback'):
                                try:
                                    args[1].rollback()
                                except:
                                    pass  # Ignore rollback errors

                            time.sleep(current_delay)
                            current_delay *= 1.5  # Exponential backoff
                            continue

                    # If not a retry-able error or max retries reached
                    logger.error(f"Database operation failed after {max_retries + 1} attempts: {e}")
                    raise HTTPException(
                        status_code=503,
                        detail="Database temporarily unavailable. Please try again."
                    )
                except Exception as e:
                    # For non-connection errors, don't retry
                    # But rollback the transaction if possible
                    if args and hasattr(args[1], 'rollback'):
                        try:
                            args[1].rollback()
                        except:
                            pass
                    raise e

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception

        return wrapper

    return decorator


def is_connection_error(error: Exception) -> bool:
    """
    Check if an error is a database connection error.
    """
    if not isinstance(error, (OperationalError, DisconnectionError)):
        return False

    error_msg = str(error).lower()
    connection_keywords = [
        'ssl connection has been closed',
        'connection closed',
        'server closed the connection',
        'connection timeout',
        'connection refused',
        'connection lost',
        'server has gone away'
    ]

    return any(keyword in error_msg for keyword in connection_keywords)