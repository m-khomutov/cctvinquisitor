"""Displays rtp stream data and rtsp protocol commands"""
from .display import DisplayForm, MultilineBox
from typing import Tuple


class RtspForm(DisplayForm):
    """Form to display data"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._size: Tuple[int, int] = (0, 0)

    def create(self) -> None:
        self._size = self.useable_space()
        horizontal_div: int = (self._size[1] * 2) // 3
        vertical_div: int = self._size[0] // 4
        self.keypress_timeout = 1
        super().set_menu('actions')
        self._rtsp_box = self.add(MultilineBox,
                                  name='rtsp',
                                  editable=False,
                                  scroll_exit=True,
                                  relx=2,
                                  max_width=horizontal_div,
                                  rely=vertical_div,
                                  max_height=(self._size[0] - vertical_div - 2))
        self._rtp_box = self.add(MultilineBox,
                                 name='rtp',
                                 editable=False,
                                 scroll_exit=True,
                                 relx=horizontal_div + 2,
                                 max_width=(self._size[1] - horizontal_div - 4),
                                 rely=2,
                                 max_height=self._size[0] - 4)
        self.parentApp.on_created(self)

    def log_http(self, value: str) -> None:
        pass

    def log_rtsp(self, value: str) -> None:
        DisplayForm._to_box(self._rtsp_box, value)

    def log_rtp(self, value: str) -> None:
        DisplayForm._to_box(self._rtp_box, value)

    def log_flv(self, value: str) -> None:
        pass

    def log_position(self, value: str) -> None:
        pass

    def log_error(self, value: str) -> None:
        DisplayForm._to_box(self._rtsp_box, value)

    def _on_waiting(self) -> None:
        self._rtp_box and self._rtp_box.display()
        self._rtsp_box and self._rtsp_box.display()
