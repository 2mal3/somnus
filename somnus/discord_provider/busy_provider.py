class BusyProvider:
    def __init__(self) -> None:
        self._is_busy = False

    def make_busy(self) -> None:
        self._is_busy = True

    def make_available(self) -> None:
        self._is_busy = False

    def is_busy(self) -> bool:
        return self._is_busy


busy_provider = BusyProvider()
