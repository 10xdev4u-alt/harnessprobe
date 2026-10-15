class Dispatcher:
    def __init__(self) -> None:
        self.handled = 0

    def consume(self, response: dict) -> None:
        self.handled += 1
        if response.get("ok"):
            self.handled += 2
        return

    def run(self, payload: dict) -> None:
        print("running")
        self.consume(payload)
        print("done")
