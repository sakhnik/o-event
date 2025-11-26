

class Printer:
    """
    Simple ESC/POS printer wrapper.
    Auto-closeable:
        with Printer("/dev/usb/lp0") as p:
            p.text("Hello\n")
            p.cut()
    """

    def __init__(self, device="/dev/usb/lp0", encoding="cp1251"):
        self.device = device
        self.encoding = encoding
        self.fd = None

    # ------------------------
    # Context manager
    # ------------------------
    def __enter__(self):
        # open device in binary write mode
        self.fd = open(self.device, "wb", buffering=0)
        self._init_printer()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.fd:
                self.fd.write(b"\x1b@\n")  # reset
        finally:
            if self.fd:
                self.fd.close()
            self.fd = None

    # ------------------------
    # ESC/POS low-level send
    # ------------------------
    def _raw(self, data: bytes):
        if self.fd is None:
            raise RuntimeError("Printer is not open")
        self.fd.write(data)

    def _init_printer(self):
        self._raw(b"\x1b@\n")     # ESC @  – initialize
        self._raw(b"\x1c\x2e\x1b\x52\x00\x1bt\x17")  # Windows-1251

    # ------------------------
    # High-level printing
    # ------------------------
    def text(self, s: str):
        self._raw(s.encode(self.encoding, errors="replace"))

    def line(self, s=""):
        self.text(s + "\n")

    def bold_on(self):
        self._raw(b"\x1b\x45\x01")

    def bold_off(self):
        self._raw(b"\x1b\x45\x00")

    def underline_on(self):
        self._raw(b"\033-\x01")

    def underline2_on(self):
        self._raw(b"\033-\x02")

    def underline_off(self):
        self._raw(b"\033-\x00")

    def align(self, mode: str):
        if mode == "left":
            self._raw(b"\x1b\x61\x00")
        elif mode == "center":
            self._raw(b"\x1b\x61\x01")
        elif mode == "right":
            self._raw(b"\x1b\x61\x02")

    def feed(self, lines: int):
        self._raw(b"\n" * lines)

    def cut(self, partial=False):
        """Feed and cut."""
        self._raw(b"\n\n\n")
        if partial:
            self._raw(b"\x1d\x56\x42\x00")  # partial cut
        else:
            self._raw(b"\x1d\x56\x00")      # full cut


class PrinterMux:
    def __init__(self):
        self.parts = []

    def __enter__(self):
        self.parts.clear()
        try:
            self.p = Printer().__enter__()
        except Exception as e:
            print(e)
            self.p = None
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.p:
            self.p.__exit__(exc_type, exc, tb)
        self.p = None

    def __getattr__(self, name):
        def mocked_method(*args, **kwargs):
            if self.p:
                return self.p.__getattr__(name)(*args, **kwargs)
        return mocked_method

    def text(self, t):
        self.parts.append(t)
        if self.p:
            self.p.text(t)

    def get_output(self):
        return ''.join(self.parts).split('\n')
