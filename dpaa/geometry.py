"""Геометрия решётки, направления и задержки.

Система координат:
  * решётка лежит в плоскости x-z и «смотрит» вдоль +y (нормаль, broadside);
  * азимут az отсчитывается от нормали (+y) в сторону +x;
  * угол места el отсчитывается от плоскости x-y в сторону +z.

Для линейной решётки (ULA) элементы расположены вдоль оси x.
"""
import numpy as np

C_SOUND = 343.0  # скорость звука в воздухе при ~20 °C, м/с


def ula(n, spacing):
    """Линейная эквидистантная решётка из n элементов с шагом spacing (м).

    Возвращает массив координат (n, 3), центрированный в начале координат.
    """
    x = (np.arange(n) - (n - 1) / 2) * spacing
    return np.column_stack([x, np.zeros(n), np.zeros(n)])


def ura(nx, nz, dx, dz=None):
    """Плоская прямоугольная решётка nx x nz в плоскости x-z (м)."""
    dz = dx if dz is None else dz
    x = (np.arange(nx) - (nx - 1) / 2) * dx
    z = (np.arange(nz) - (nz - 1) / 2) * dz
    xx, zz = np.meshgrid(x, z, indexing="xy")
    return np.column_stack([xx.ravel(), np.zeros(xx.size), zz.ravel()])


def direction(az_deg, el_deg=0.0):
    """Единичный вектор (или массив векторов (..., 3)) направления."""
    az = np.deg2rad(np.asarray(az_deg, dtype=float))
    el = np.deg2rad(np.asarray(el_deg, dtype=float))
    az, el = np.broadcast_arrays(az, el)
    return np.stack(
        [np.sin(az) * np.cos(el), np.cos(az) * np.cos(el), np.sin(el)], axis=-1
    )


def steering_delays(positions, az_deg=0.0, el_deg=0.0, focus=None, c=C_SOUND):
    """Неотрицательные задержки элементов (с) для управления лучом.

    Одни и те же задержки работают и на передачу (задержка запуска каждого
    излучателя), и на приём (задержка каждого канала перед суммированием) —
    это проявление принципа взаимности.

    * Дальняя зона (focus=None): tau_n = p_n·u / c — элемент, который ближе
      к цели, излучает позже, чтобы фронты сложились в направлении u.
    * Ближняя зона (focus=(x, y, z)): tau_n = -|focus - p_n| / c —
      фокусировка в точку («акустический прожектор»).
    """
    positions = np.asarray(positions, dtype=float)
    if focus is not None:
        tau = -np.linalg.norm(positions - np.asarray(focus, dtype=float), axis=1) / c
    else:
        tau = positions @ direction(az_deg, el_deg) / c
    return tau - tau.min()


def steering_vector(positions, freq, dirs, c=C_SOUND):
    """Вектор фазирования a_n(f, u) = exp(j 2π f p_n·u / c).

    dirs: (3,) или (M, 3). Возвращает (N,) или (N, M).
    Соглашение: комплексная амплитуда сигнала на элементе n при приходе
    плоской волны с направления u равна S(f)·a_n.
    """
    positions = np.asarray(positions, dtype=float)
    return np.exp(2j * np.pi * freq * (positions @ np.asarray(dirs).T) / c)


def near_field_vector(positions, freq, point, c=C_SOUND):
    """Вектор фазирования для точечного источника в ближней зоне (с 1/r)."""
    r = np.linalg.norm(np.asarray(positions) - np.asarray(point), axis=1)
    return np.exp(-2j * np.pi * freq * r / c) * (r.min() / r)


def fraunhofer_distance(aperture, freq, c=C_SOUND):
    """Граница дальней зоны 2D²/λ (м)."""
    return 2 * aperture**2 / (c / freq)
