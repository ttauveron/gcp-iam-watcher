import logging
from typing import List

from .base import Destination, IamChangeEvent


class CompositeDestination(Destination):
    def __init__(self, destinations: List[Destination]):
        self.destinations = destinations

    def send(self, event: IamChangeEvent) -> None:
        errors: List[str] = []
        for d in self.destinations:
            try:
                d.send(event)
            except Exception as e:
                # never fail the whole pipeline because one sink died
                logging.exception("destination_failed", extra={"dest": d.__class__.__name__})
                errors.append(f"{d.__class__.__name__}: {e}")

        if errors:
            # Let your function log a single summarized error; your runtime logs can be routed to a DLQ topic if desired
            logging.error("one_or_more_destinations_failed", extra={"errors": errors})
