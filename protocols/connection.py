"""Connection to source. Proxies stream from source and passes commands to source"""
import selectors
import socket
import threading
import time
import types
from typing import TypeVar, Generic, Tuple, List, Union


T = TypeVar('T')


class Connection(Generic[T], threading.Thread):
    """Class to connect to stream source"""
    def __init__(self, address: Tuple[str, int] = ('', 0), proto: T = None, pos_period: int = 0) -> None:
        super().__init__()
        self._proto: T = proto
        self._address: Tuple[str, int] = address
        self._pos_period: int = pos_period
        self._stream_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._actions: List[Tuple[str, str]] = []
        self._lock: threading.Lock = threading.Lock()
        self._running = True
        self.exception: Union[OSError, None] = None

    def __repr__(self):
        return f'{self.__class__.__name__}(ip {self._address[0]} port {self._address[1]})'

    def run(self) -> None:
        data_length: int = 0
        try:
            self._stream_socket.connect(self._address)
        except socket.error as err:
            self.exception = err
            return
        self._stream_socket.setblocking(False)
        selector: selectors.DefaultSelector = selectors.DefaultSelector()
        selector.register(self._stream_socket,
                          selectors.EVENT_READ | selectors.EVENT_WRITE,
                          types.SimpleNamespace(addr=self._address[1],
                                                inb=b'',
                                                outb=self._proto.stream_request(self._address[0], self._address[1])))
        timing = time.time()
        while self._is_running():
            self._add_actions(selector)
            for key, mask in selector.select(timeout=.01):
                if key.data:
                    try:
                        if mask & selectors.EVENT_READ:
                            data_length = self._on_data(key, data_length)
                        elif mask & selectors.EVENT_WRITE:
                            if key.data.outb:
                                sent = key.fileobj.send(key.data.outb)  # Should be ready to write
                                key.data.outb = key.data.outb[sent:]
                    except:  # noqa # pylint: disable=bare-except
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        if key.data.addr == self._address[1]:
                            self._stop()
            if self._pos_period and time.time() - timing > self._pos_period:
                timing = time.time()
                self.request_action(('getpos',))
        self._stream_socket.close()
        selector.close()

    def join(self, timeout=None) -> None:
        self._stop()
        if super().is_alive():
            super().join(timeout)

    def request_action(self, action: Union[Tuple[str, str], Tuple[str]]) -> None:
        with self._lock:
            self._actions.append(action)

    def _on_data(self, key: selectors.SelectorKey, expected_length: int) -> int:
        data: bytes = key.fileobj.recv(1024)
        if data:
            if key.data.addr == self._address[1]:
                return self._proto.on_stream(key, data, expected_length)
            else:
                self._proto.on_action_reply(data)
        raise EOFError()

    def _add_actions(self, selector: selectors.DefaultSelector) -> None:
        with self._lock:
            for action in self._actions:
                sock: Union[socket.socket, None] = self._proto.add_action(selector,
                                                                          self._stream_socket,
                                                                          self._address[0], self._address[1], action)
                if sock:
                    self._stream_socket = sock
            self._actions.clear()

    def _is_running(self):
        with self._lock:
            return self._running

    def _stop(self):
        with self._lock:
            self._running = False
