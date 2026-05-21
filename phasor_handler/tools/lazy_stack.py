"""Lazy frame-stack helpers for large split recordings."""

from __future__ import annotations

import os
import re
from bisect import bisect_right
from typing import Iterator, Sequence

import numpy as np


def natural_key(value: str):
    """Sort key that keeps numbered file parts in numeric order."""
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split(r"(\d+)", os.path.basename(value))
    ]


def discover_channel_npy_files(folder_path: str, prefix: str) -> list[str]:
    """Return channel NPY files in natural order for a recording folder."""
    if not os.path.isdir(folder_path):
        return []
    files = [
        os.path.join(folder_path, name)
        for name in os.listdir(folder_path)
        if name.startswith(prefix) and name.endswith(".npy")
    ]
    return sorted(files, key=natural_key)


class LazyFrameStack:
    """A frame stack backed by one or more memory-mapped ``.npy`` files.

    The object intentionally mimics the small NumPy surface used by the GUI:
    ``shape``, ``ndim``, integer/slice indexing, and chunk iteration. It avoids
    concatenating split recordings into a single in-memory array.
    """

    def __init__(self, paths: Sequence[str]):
        if not paths:
            raise ValueError("LazyFrameStack requires at least one .npy file")

        self.paths = list(paths)
        self._arrays = []
        self._frame_counts = []
        spatial_shape = None
        dtype = None

        for path in self.paths:
            arr = np.load(path, mmap_mode="r")
            arr = np.squeeze(arr)
            if arr.ndim == 2:
                arr = arr[np.newaxis, ...]
            if arr.ndim != 3:
                raise ValueError(
                    f"Expected 2D or 3D image stack in {path}, got shape "
                    f"{arr.shape}"
                )
            if spatial_shape is None:
                spatial_shape = arr.shape[1:]
                dtype = arr.dtype
            elif arr.shape[1:] != spatial_shape:
                raise ValueError(
                    f"Shape mismatch in {path}: {arr.shape[1:]} vs "
                    f"{spatial_shape}"
                )

            self._arrays.append(arr)
            self._frame_counts.append(int(arr.shape[0]))

        self._offsets = np.cumsum([0] + self._frame_counts).tolist()
        self.shape = (self._offsets[-1],) + tuple(spatial_shape)
        self.ndim = 3
        self.dtype = dtype

    def __len__(self) -> int:
        return self.shape[0]

    @property
    def size(self) -> int:
        return int(np.prod(self.shape))

    def __getitem__(self, key):
        if isinstance(key, tuple):
            frame_key = key[0]
            rest = key[1:]
            frames = self._get_frames(frame_key)
            if isinstance(frame_key, slice):
                return frames[(slice(None),) + rest]
            return frames[rest]
        return self._get_frames(key)

    def _get_frames(self, frame_key):
        if isinstance(frame_key, (int, np.integer)):
            idx = int(frame_key)
            if idx < 0:
                idx += len(self)
            if idx < 0 or idx >= len(self):
                raise IndexError(idx)
            part_idx = bisect_right(self._offsets, idx) - 1
            local_idx = idx - self._offsets[part_idx]
            return self._arrays[part_idx][local_idx]

        if isinstance(frame_key, slice):
            start, stop, step = frame_key.indices(len(self))
            if step != 1:
                return np.stack(
                    [self[i] for i in range(start, stop, step)], axis=0
                )
            if stop <= start:
                return np.empty((0,) + self.shape[1:], dtype=self.dtype)
            chunks = []
            for part_idx, arr in enumerate(self._arrays):
                part_start = self._offsets[part_idx]
                part_stop = self._offsets[part_idx + 1]
                overlap_start = max(start, part_start)
                overlap_stop = min(stop, part_stop)
                if overlap_start < overlap_stop:
                    chunks.append(
                        arr[
                            overlap_start - part_start:
                            overlap_stop - part_start
                        ]
                    )
            if len(chunks) == 1:
                return chunks[0]
            return np.concatenate(chunks, axis=0)

        raise TypeError(f"Unsupported index type: {type(frame_key)!r}")

    def iter_chunks(
        self, chunk_size: int = 256
    ) -> Iterator[tuple[int, np.ndarray]]:
        """Yield ``(start_frame, chunk)`` pairs."""
        chunk_size = max(1, int(chunk_size))
        for start in range(0, len(self), chunk_size):
            yield start, self[start:min(start + chunk_size, len(self))]


def is_lazy_stack(value) -> bool:
    return isinstance(value, LazyFrameStack)


def to_stack3d(value):
    """Return a 3D stack without forcing LazyFrameStack into memory."""
    if value is None:
        return None
    if isinstance(value, LazyFrameStack):
        return value
    arr = np.asarray(value).squeeze()
    return arr[np.newaxis, ...] if arr.ndim == 2 else arr


def stack_projection(stack, mode: str, chunk_size: int = 256):
    """Compute a projection over a regular or lazy frame stack."""
    stack = to_stack3d(stack)
    if stack is None:
        return None

    if not isinstance(stack, LazyFrameStack):
        if mode == "std":
            return np.std(stack, axis=0)
        if mode == "max":
            return np.max(stack, axis=0)
        if mode == "mean":
            return np.mean(stack, axis=0)
        raise ValueError(f"Unsupported projection mode: {mode}")

    if mode == "max":
        result = None
        for _, chunk in stack.iter_chunks(chunk_size):
            chunk_max = np.max(chunk, axis=0)
            result = (
                chunk_max if result is None else np.maximum(result, chunk_max)
            )
        return result

    if mode == "mean":
        total = None
        count = 0
        for _, chunk in stack.iter_chunks(chunk_size):
            chunk_sum = np.sum(chunk, axis=0, dtype=np.float64)
            total = chunk_sum if total is None else total + chunk_sum
            count += chunk.shape[0]
        return total / max(count, 1)

    if mode == "std":
        total = None
        total_sq = None
        count = 0
        for _, chunk in stack.iter_chunks(chunk_size):
            chunk_float = chunk.astype(np.float64, copy=False)
            chunk_sum = np.sum(chunk_float, axis=0)
            chunk_sq_sum = np.sum(chunk_float * chunk_float, axis=0)
            total = chunk_sum if total is None else total + chunk_sum
            total_sq = (
                chunk_sq_sum if total_sq is None else total_sq + chunk_sq_sum
            )
            count += chunk.shape[0]
        mean = total / max(count, 1)
        variance = np.maximum(total_sq / max(count, 1) - mean * mean, 0)
        return np.sqrt(variance)

    raise ValueError(f"Unsupported projection mode: {mode}")
