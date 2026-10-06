"""
CHARVIS GUI Widgets Package
"""

from gui.widgets.status import StatusWidget
from gui.widgets.sidebar import SidebarWidget
from gui.widgets.input_bar import InputBarWidget
from gui.widgets.chat import ChatViewWidget
from gui.widgets.task_panel import TaskPanelWidget
from gui.widgets.confirmation import ConfirmationDialog
from gui.widgets.memory_view import MemoryViewWidget
from gui.widgets.settings_view import SettingsViewWidget
from gui.widgets.assistant import AssistantViewWidget

__all__ = [
    "StatusWidget",
    "SidebarWidget",
    "InputBarWidget",
    "ChatViewWidget",
    "TaskPanelWidget",
    "ConfirmationDialog",
    "MemoryViewWidget",
    "SettingsViewWidget",
    "AssistantViewWidget",
]
