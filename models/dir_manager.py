from PyQt6.QtCore import QObject, pyqtSignal


class DirManager(QObject):
    """Manage a shared list of directories and notify listeners on changes.

    This keeps directory logic separate from GUI widgets. Listeners should
    connect to `directoriesChanged` and call `list()` to get the current value.
    """
    directoriesChanged = pyqtSignal(list)

    def __init__(self, dirs=None, parent=None):
        super().__init__(parent)
        self._dirs = list(dirs) if dirs else []

    def add(self, paths):
        changed = False
        for p in paths:
            if p not in self._dirs:
                self._dirs.append(p)
                changed = True
        if changed:
            self.directoriesChanged.emit(self.list())

    def remove(self, paths):
        changed = False
        for p in paths:
            if p in self._dirs:
                self._dirs.remove(p)
                changed = True
        if changed:
            self.directoriesChanged.emit(self.list())

    def clear(self):
        if self._dirs:
            self._dirs = []
            self.directoriesChanged.emit([])

    def list(self):
        return list(self._dirs)
