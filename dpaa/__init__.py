"""DPAA — акустическая модель цифровой антенной решётки (ЦАФАР в звуковом диапазоне)."""
from .geometry import C_SOUND, direction, steering_delays, steering_vector, ula, ura

__all__ = ["C_SOUND", "direction", "steering_delays", "steering_vector", "ula", "ura"]
