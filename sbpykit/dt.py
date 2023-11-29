from datetime import datetime, timedelta, timezone

from sbpykit import validation
from sbpykit.types import Delta, Timestamp
from sbpykit.klass import Static


class DTUtils(Static):
    @staticmethod
    def get_utc_timestamp() -> Timestamp:
        return datetime.now(timezone.utc).timestamp()

    @staticmethod
    def get_delta_timestamp(delta: Delta) -> Timestamp:
        """
        Calculates delta timestamp from current moment adding given delta in
        seconds.
        """
        validation.validate(delta, Delta)
        return (
            datetime.now(timezone.utc) + timedelta(seconds=delta)
        ).timestamp()
