from heapq import heappop, heappush

from src.simulation.event import SimulationEvent


class SimulationClock:
    def __init__(self, start_time=0, end_time=0):
        self.current_time = start_time
        self.end_time = end_time
        self._events = []
        self._next_sequence = 0

    def schedule(self, time, event_type, callback=None, payload=None, priority=0):
        event = SimulationEvent(
            time=time,
            priority=priority,
            sequence=self._next_sequence,
            event_type=event_type,
            callback=callback,
            payload=payload or {},
        )
        self._next_sequence += 1
        heappush(self._events, event)
        return event

    def pop_next(self):
        if not self._events:
            return None
        event = heappop(self._events)
        self.current_time = event.time
        return event

    def has_events(self):
        return bool(self._events)
