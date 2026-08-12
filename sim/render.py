"""Headless MuJoCo renderer using EGL.

Callers who want pixel output from the MuJoCo-backed plant use this
module directly. :class:`MujocoPlant` never instantiates a renderer
automatically — rendering is never required for prior learning.

Usage::

    from sim.mujoco_plant import MujocoPlant
    from sim.render import MujocoRenderer

    plant = MujocoPlant(dt=0.005)
    plant.reset()
    renderer = MujocoRenderer(plant._bridge.model)
    for _ in range(100):
        plant.step({"roll": 0.0, "pitch": 0.0, "yaw": 0.0, "z": 12.71})
        frame = renderer.render(plant._bridge.data)
        # frame.shape == (height, width, 3), dtype uint8

The renderer requires EGL (``libEGL_nvidia.so`` or a software fallback).
On hosts where EGL is absent, ``is_available()`` returns ``(False, reason)``
and the constructor raises ``RuntimeError``.
"""
from __future__ import annotations

import os

import numpy as np

try:
    import mujoco  # type: ignore
    import mujoco.gui as mujoco_gui  # type: ignore
    _HAS_MUJOCO = True
except ImportError:
    mujoco = None  # type: ignore
    mujoco_gui = None  # type: ignore
    _HAS_MUJOCO = False


class MujocoRenderer:
    """Headless offscreen renderer using EGL.

    The renderer holds a :class:`mujoco.MjrContext` that is created once
    at construction time. It is safe to call :meth:`render` repeatedly
    with the same or different :class:`mujoco.MjData` instances.
    """

    @staticmethod
    def is_available() -> tuple[bool, str]:
        """Return ``(available, reason)`` for the EGL rendering backend.

        Checks three conditions:
        1. ``mujoco`` Python package is importable.
        2. ``MUJOCO_GL`` is not set to ``"disable"``.
        3. EGL context can be created via :class:`mujoco.glfw.Glffw`.
        """
        if not _HAS_MUJOCO:
            return (False, "mujoco is not installed in this venv")
        # Allow caller to override; only block explicit disable.
        gl_env = os.environ.get("MUJOCO_GL", "")
        if gl_env == "disable":
            return (False, "MUJOCO_GL=disable; rendering explicitly disabled")
        # EGL is required. Try to create a minimal context.
        # We test by constructing with a tiny viewport and no model callback;
        # if EGL is absent mujoco will raise before we return.
        try:
            import mujoco.glfw as glfw  # type: ignore
            glfw.init()
            # Attempt to make context current on an offscreen window.
            w = glfw.window(1, 1)
            glfw.make_context_current(w)
            glfw.destroy_window(w)
            glfw.terminate()
            return (True, "mujoco with EGL")
        except Exception as ex:
            return (False, f"EGL unavailable: {ex}")

    def __init__(self,
                 model: "mujoco.MjModel",
                 width: int = 640,
                 height: int = 480):
        """Construct an offscreen renderer for ``model``.

        Raises ``RuntimeError`` if the EGL backend is not available.
        Call :meth:`is_available` first to check.
        """
        if not _HAS_MUJOCO:
            raise RuntimeError(
                "MujocoRenderer: mujoco is not installed in this venv.")
        self._model = model
        self._width = width
        self._height = height
        # Ensure EGL is used if available.
        if os.environ.get("MUJOCO_GL") not in ("egl", "disable"):
            os.environ["MUJOCO_GL"] = "egl"
        # Initialise GLFW for offscreen context.
        import mujoco.glfw as glfw  # type: ignore
        glfw.init()
        self._window = glfw.window(width, height, "", False)
        glfw.make_context_current(self._window)
        # MuJoCo offscreen framebuffer.
        self._scene = mujoco.MjvScene(model, maxgeom=1000)
        self._cam = mujoco.MjvCamera()
        mujoco.mjv_defaultCamera(self._cam)
        self._cam.lookat[0] = 0.0
        self._cam.lookat[1] = 0.0
        self._cam.lookat[2] = 0.0
        self._cam.distance = 2.0
        self._cam.azimuth = 45.0
        self._cam.elevation = -30.0
        self._opt = mujoco.MjvOption()
        mujoco.mjv_defaultOption(self._opt)
        self._ctx = mujoco.MjrContext(model, mujoco.mjtFontScale.mjFONTSCALE_150)
        # Allocate output buffer.
        self._rgb_buf = np.zeros((height, width, 3), dtype=np.uint8)
        self._depth_buf = np.zeros((height, width), dtype=np.float32)

    def render(self, data: "mujoco.MjData") -> np.ndarray:
        """Render ``data`` and return an RGB frame.

        Returns
        -------
        np.ndarray
            Shape ``(height, width, 3)``, dtype ``uint8``.
            Pixel order is standard RGB (top-left origin, row-major).
        """
        mujoco.mjv_updateScene(
            self._model, data, self._opt, None, self._cam,
            mujoco.mjtCatBit.mjCAT_ALL, self._scene)
        mujoco.mjr_render(
            mujoco.Rect(0, 0, self._width, self._height),
            self._scene, self._ctx)
        mujoco.mjr_readPixels(
            self._rgb_buf, self._depth_buf,
            mujoco.Rect(0, 0, self._width, self._height),
            self._ctx)
        return self._rgb_buf.copy()

    def close(self) -> None:
        """Release the GLFW context and window."""
        import mujoco.glfw as glfw  # type: ignore
        glfw.destroy_window(self._window)
        glfw.terminate()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
