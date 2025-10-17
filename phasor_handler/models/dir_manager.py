from PyQt6.QtCore import QObject, pyqtSignal
from pathlib import Path


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
    
    def get_display_names(self):
        """Return a list of (full_path, display_name) tuples.
        
        Display names show just the folder stem unless there are duplicates,
        in which case enough parent folders are included to distinguish them.
        """
        if not self._dirs:
            return []
        
        # Convert paths to Path objects for easier manipulation
        paths = [Path(d) for d in self._dirs]
        
        # Start with just stems
        display_map = {}
        for i, p in enumerate(paths):
            stem = p.name
            if stem not in display_map:
                display_map[stem] = []
            display_map[stem].append((i, p))
        
        # For duplicates, add parent folders until unique
        result = {}
        for stem, path_list in display_map.items():
            if len(path_list) == 1:
                # No duplicates, use just the stem
                idx, path = path_list[0]
                result[idx] = stem
            else:
                # Duplicates found, need to differentiate
                # Start with 2 levels (parent/stem) and increase until unique
                max_depth = max(len(p.parts) for _, p in path_list)
                
                for depth in range(2, max_depth + 1):
                    temp_names = {}
                    all_unique = True
                    
                    for idx, path in path_list:
                        # Get the last 'depth' parts of the path
                        parts = path.parts[-depth:] if len(path.parts) >= depth else path.parts
                        display_name = str(Path(*parts))
                        
                        if display_name in temp_names:
                            all_unique = False
                            break
                        temp_names[display_name] = idx
                    
                    if all_unique:
                        # Found unique names at this depth
                        for display_name, idx in temp_names.items():
                            result[idx] = display_name
                        break
                else:
                    # If we still have duplicates after max depth, use full paths
                    for idx, path in path_list:
                        result[idx] = str(path)
        
        # Return in original order
        return [(self._dirs[i], result[i]) for i in range(len(self._dirs))]
