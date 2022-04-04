"""Common forms to display source information"""
import npyscreen
from collections import deque
from typing import Union


class DisplayException(ValueError):
    """Common exception to raise in display classes if needed"""
    pass


class ActionParameterForm(npyscreen.ActionPopup):
    """Form to get parameter for action scale, if needed"""
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._result: str = ''

    def create(self) -> None:
        self.field = self.add(npyscreen.Textfield)

    def afterEditing(self) -> None:
        self.parentApp.setNextForm('MAIN')

    def on_ok(self) -> None:
        self._result = self.field.value

    def on_cancel(self) -> None:
        raise DisplayException('action cancelled')

    @property
    def result(self) -> str:
        return self._result


class MultilineBox(npyscreen.BoxTitle):
    """Decorator for multiline to have border, header and footer"""
    _contained_widget = npyscreen.MultiLineEdit


class SliderBox(npyscreen.BoxTitle):
    """Decorator for slider to have border, header and footer"""
    _contained_widgets = npyscreen.Slider


class DisplayForm(npyscreen.FormWithMenus):
    """Displays source information"""
    def create(self) -> None:
        raise NotImplementedError

    def afterEditing(self) -> None:
        self.parentApp.setNextForm(None)

    def while_waiting(self) -> None:
        err: Union[IOError, None] = self.parentApp.verify()
        err and self.log_error(str(err))
        self._on_waiting()

    def log_http(self, value: str) -> None:
        raise NotImplementedError

    def log_rtsp(self, value: str) -> None:
        raise NotImplementedError

    def log_rtp(self, value: str) -> None:
        raise NotImplementedError

    def log_flv(self, value: str) -> None:
        raise NotImplementedError

    def log_position(self, value: str) -> None:
        raise NotImplementedError

    def log_error(self, value: str) -> None:
        raise NotImplementedError

    def set_menu(self, name: str) -> None:
        m = self.new_menu(name=name)
        for item in ['scale', 'seek', 'play', 'reverse', 'pause', 'forward', 'backward', 'shift']:
            m.addItem(text=item, onSelect=getattr(self, f'_on_select_{item}'))

    def _on_waiting(self):
        raise NotImplementedError

    def _on_select_scale(self) -> None:
        try:
            self.parentApp.request_action(('scale', DisplayForm._action_param()))
        except DisplayException:
            pass

    def _on_select_seek(self) -> None:
        try:
            self.parentApp.request_action(('scale', DisplayForm._action_param()))
        except DisplayException:
            pass

    def _on_select_play(self):
        self.parentApp.request_action(('play',))

    def _on_select_reverse(self):
        self.parentApp.request_action(('rplay',))

    def _on_select_pause(self) -> None:
        self.parentApp.request_action(('pause',))

    def _on_select_forward(self) -> None:
        try:
            self.parentApp.request_action(('forward', DisplayForm._action_param()))
        except DisplayException:
            pass

    def _on_select_backward(self) -> None:
        try:
            self.parentApp.request_action(('backward', DisplayForm._action_param()))
        except DisplayException:
            pass

    def _on_select_shift(self) -> None:
        try:
            self.parentApp.request_action(('shift', DisplayForm._action_param()))
        except DisplayException:
            pass

    @staticmethod
    def _action_param() -> str:
        f: ActionParameterForm = ActionParameterForm(name='value', lines=6, columns=20)
        f.edit()
        return f.result

    @staticmethod
    def _to_box(box: MultilineBox, value: str):
        q: deque = deque(box.value.split('\n'))
        q.append(value)
        while len(q) > box.height:
            q.popleft()
        box.value = '\n'.join([x for x in q])
