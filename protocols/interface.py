"""Class of protocols source. Defines common source interface"""
import abc
import selectors
import socket
from typing import Tuple, Union


class Interface(abc.ABC):
    @abc.abstractmethod
    def stream_request(self, address: str, port: int) -> bytes:
        """Starts streaming from source.
           Returns initial request for starting streaming"""
        raise NotImplementedError

    @abc.abstractmethod
    def on_action_reply(self, data: bytes) -> None:
        """Handler, called when action on source is fulfilled"""
        raise NotImplementedError

    @abc.abstractmethod
    def on_stream(self,
                  key: selectors.SelectorKey,
                  data: bytes,
                  expected_length: int) -> int:
        """Handler, called when stream packet is received.
           Returns size of next stream packet"""
        raise NotImplementedError

    @abc.abstractmethod
    def add_action(self,
                   selector: selectors.DefaultSelector,
                   stream_socket: socket.socket,
                   address: str,
                   port: int,
                   action: Tuple[str, str]) -> Union[socket.socket, None]:
        """Adds action in action queue to be passed to source.
           Returns new stream socket or None"""
        raise NotImplementedError
