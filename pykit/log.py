import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, NoReturn

from aiofile import async_open
from loguru import logger as _logger

from pykit.uuid import uuid4


class log:
    err_track_dir: Path = Path(tempfile.gettempdir(), "pykit_err_track_dir")
    is_debug: bool = False
    std_verbosity: int = 1
    """
    Verbosity level for stdout/stderr.

    For all other targets verbosity is not applied - all msgs are passed to
    the sink as it is (yet then it can be blocked there according to the
    sink's configuration).

    Levels:
        0. silent
        1. cozy chatter
        2. rap god

    Methods that produce logging accept variable "v" which defines the
    minimal level of verbosity required to make the intended log. For example
    if "info('hello', v=1)", the info message would only be produced on
    verbosity level 1 or 2.

    For debug logs verbosity level is unavailable - they must be emitted
    always for their level.
    """

    @classmethod
    def debug(cls, *args, sep: str = ", "):
        if cls.is_debug:
            _logger.debug(sep.join([str(arg) for arg in args]))

    @classmethod
    def info(cls, msg: Any, v: int = 1):
        if v < 1:
            return
        if cls.std_verbosity >= v:
            _logger.info(msg)

    @classmethod
    def warn(cls, msg: Any, v: int = 1):
        if v < 1:
            return
        if cls.std_verbosity >= v:
            _logger.warning(msg)

    @classmethod
    def err(cls, msg: Any, v: int = 1):
        if v < 1:
            return
        if cls.std_verbosity >= v:
            _logger.error(msg)

    @classmethod
    def catch(cls, err: Exception, v: int = 1):
        if v < 1:
            return
        if cls.std_verbosity >= v:
            _logger.exception(err)

    @classmethod
    def err_or_catch(
        cls, err: Exception, catch_if_v_equal_or_more: int,
    ):
        if cls.std_verbosity >= catch_if_v_equal_or_more:
            cls.catch(err)
            return
        cls.err(err)

    @classmethod
    def fatal(cls, msg: Any, *, exit_code: int = 1) -> NoReturn:
        log.err(f"FATAL({exit_code}) :: {msg}")
        sys.exit(exit_code)

    @staticmethod
    def _try_get_err_traceback_str(err: Exception) -> str | None:
        """
        Copy of err_utils.try_get_traceback_str to avoid circulars.
        """
        s = None
        tb = err.__traceback__
        if tb:
            extracted_list = traceback.extract_tb(tb)
            s = ""
            for item in traceback.StackSummary.from_list(
                    extracted_list).format():
                s += item
        return s

    @classmethod
    def track(cls, err: Exception, msg: Any, v: int = 1) -> str | None:
        """
        Tracks an err with attached msg.

        The err traceback is written to <log.err_track_dir>/<sid>.log, and the
        msg is logged with the sid. This allows to find out error's traceback
        in a separate file by the original log message.

        If cannot retrieve a traceback to retrieve, the log will still be
        written, but pointed as "$notrack".

        If ``v`` parameter doesn't match current verbosity, nothing will be
        done.

        Returns tracksid or None.
        """
        if cls.std_verbosity < v:
            return None

        cls.err_track_dir.mkdir(parents=True, exist_ok=True)
        tb = cls._try_get_err_traceback_str(err)
        if tb:
            sid = uuid4()
            track_path = Path(cls.err_track_dir, f"{sid}.log")
            final_msg = msg + f"; $track:{track_path}"
            with track_path.open("w+") as f:
                f.write(tb)
            log.err(final_msg, v)
            return sid

        final_msg = msg + "; $notrack"
        log.err(final_msg, v)
        return None

    @classmethod
    async def atrack(cls, err: Exception, msg: Any, v: int = 1):
        """
        Asynchronous version of ``log.track``.
        """
        if cls.std_verbosity < v:
            return None

        cls.err_track_dir.mkdir(parents=True, exist_ok=True)
        tb = cls._try_get_err_traceback_str(err)
        if tb:
            sid = uuid4()
            track_path = Path(cls.err_track_dir, f"{sid}.log")
            final_msg = msg + f"; $track:{track_path}"
            async with async_open(track_path, "w+") as f:
                await f.write(tb)
            log.err(final_msg, v)
            return sid

        final_msg = msg + "; $notrack"
        log.err(final_msg, v)
        return None
