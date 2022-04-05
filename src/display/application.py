"""NPSAppManaged application to manage the display"""
from __future__ import annotations
import argparse
import socket

import npyscreen
import re
from .display import DisplayException, DisplayForm
from .axon import AxonForm
from .cctv import CctvForm
from .rtsp import RtspForm
from protocols import connection, axon, cctv, rtsp
from typing import List, Tuple, Union


def run():
    Application.create().run()


class Application(npyscreen.NPSAppManaged):
    @staticmethod
    def create() -> Application:
        parser: argparse.ArgumentParser = argparse.ArgumentParser(description='cctv-dvr frontend')
        parser.add_argument('url',
                            type=str,
                            help='cctv url (http://cctvip:port/dvr_url/control/0/0)')
        parser.add_argument('-cp', type=int, default=2232, help='cctv-dvr control port (def. 2232)')
        parser.add_argument('-pos_period',
                            type=int,
                            default=0,
                            help='period to ask for position sec. (def. 0 - no requests)')
        parser.add_argument('-speed', type=int, default=1, help='Axon stream speed (def. 1)')
        args: argparse.Namespace = parser.parse_args()
        m = re.search(r'(?P<proto>\w{4})://(?P<ip>[^/\r\n]+):(?P<port>\d{3,6})/(?P<content>.+)', args.url)
        if not m or m['proto'] not in ['http', 'rtsp']:
            raise DisplayException(f'invalid url {args.url}')
        if m['proto'] == 'http':
            return CctvApplication((m['ip'], int(m['port'])), m['content'], int(args.cp), int(args.pos_period))
        elif 'SourceEndpoint.' in m['content']:
            return AxonApplication((m['ip'], int(m['port'])), m['content'])
        return RtspApplication((m['ip'], int(m['port'])), m['content'])

    def __init__(self, address: Tuple[str, int], content: str):
        super().__init__()
        self._address: Tuple[str, int] = ('', 0)
        self._credentials: List = []
        credentials: List[str, ...] = address[0].split('@')
        if len(credentials) == 2:
            self._address = (credentials[1], address[1])
            self._credentials = credentials[0].split(':')
        else:
            self._address = address
        self._content: str = content
        self._connection: connection.Connection = connection.Connection()

    def __del__(self) -> None:
        self._connection.join()

    def on_created(self, form: DisplayForm) -> None:
        raise NotImplementedError

    def verify(self) -> Union[socket.error, None]:
        return self._connection.exception

    def request_action(self, action: Union[Tuple[str, str], Tuple[str]]) -> None:
        if self._connection:
            self._connection.request_action(action)


class CctvApplication(Application):
    """NPSAppManaged application to manage the CCTV display"""
    def __init__(self, address: Tuple[str, int], content: str, control_port: int, pos_period: int = 0):
        super().__init__(address, content)
        self._control_port = control_port
        self._pos_period: int = pos_period

    def onStart(self) -> None:
        self.addForm('MAIN', CctvForm, name='cctv', connection=self._connection)

    def on_created(self, form: DisplayForm):
        self._connection: connection.Connection[cctv.Source] = \
            connection.Connection(self._address,
                                  cctv.Source(form, self._content, self._control_port),
                                  self._pos_period)
        self._connection.start()


class AxonApplication(Application):
    """NPSAppManaged application to manage the Axon display"""
    def onStart(self) -> None:
        self.addForm('MAIN', AxonForm, name='axon')

    def on_created(self, form: DisplayForm):
        self._connection: connection.Connection[axon.Source] = \
            connection.Connection(self._address,
                                  axon.Source(form, self._address[0], self._credentials, self._content))
        self._connection.start()


class RtspApplication(Application):
    """NPSAppManaged application to manage the rtsp/rtp display"""
    def onStart(self) -> None:
        self.addForm('MAIN', RtspForm, name='rtsp')

    def on_created(self, form: DisplayForm):
        self._connection: connection.Connection[rtsp.Source] = \
            connection.Connection(self._address,
                                  rtsp.Source(form, self._credentials, self._content))
        self._connection.start()
