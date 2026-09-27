namespace Dpaa.Core;

/// <summary>Точка или вектор в метрах: x — вдоль решётки, y — вперёд (нормаль), z — вверх.</summary>
public readonly record struct Vec3(double X, double Y, double Z)
{
    public static Vec3 operator +(Vec3 a, Vec3 b) => new(a.X + b.X, a.Y + b.Y, a.Z + b.Z);
    public static Vec3 operator -(Vec3 a, Vec3 b) => new(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
    public double Dot(Vec3 b) => X * b.X + Y * b.Y + Z * b.Z;
    public double Length => Math.Sqrt(Dot(this));
}

/// <summary>Геометрия решётки и задержки фазирования (как dpaa/geometry.py).</summary>
public static class Geometry
{
    /// <summary>Линейная решётка из n элементов с шагом pitch, центр — в начале координат.</summary>
    public static Vec3[] Ula(int n, double pitch)
    {
        var p = new Vec3[n];
        for (int i = 0; i < n; i++)
            p[i] = new Vec3((i - (n - 1) / 2.0) * pitch, 0, 0);
        return p;
    }

    /// <summary>Центры динамиков.</summary>
    public static Vec3[] ElementPositions(int n = Hw.NElem, double pitch = Hw.Pitch) => Ula(n, pitch);

    /// <summary>Звуковые отверстия микрофонов (выше динамиков на MicOffset).</summary>
    public static Vec3[] MicPositions(int n = Hw.NMics, double pitch = Hw.Pitch) =>
        Ula(n, pitch).Select(p => p + Hw.MicOffset).ToArray();

    /// <summary>Единичный вектор направления: азимут от нормали в сторону +x, угол места вверх.</summary>
    public static Vec3 Direction(double azDeg, double elDeg = 0)
    {
        double az = azDeg * Math.PI / 180, el = elDeg * Math.PI / 180;
        return new Vec3(Math.Sin(az) * Math.Cos(el), Math.Cos(az) * Math.Cos(el), Math.Sin(el));
    }

    /// <summary>
    /// Неотрицательные задержки элементов, с. Дальняя зона: τ = p·u / c;
    /// фокус в точку: τ = −|focus − p| / c. Одни и те же задержки — для передачи и приёма.
    /// </summary>
    public static double[] SteeringDelays(Vec3[] positions, double azDeg, Vec3? focus = null,
                                          double c = Hw.SoundSpeed)
    {
        var tau = new double[positions.Length];
        var u = Direction(azDeg);
        for (int i = 0; i < positions.Length; i++)
            tau[i] = focus is { } f ? -(f - positions[i]).Length / c : positions[i].Dot(u) / c;
        double min = tau.Min();
        for (int i = 0; i < tau.Length; i++) tau[i] -= min;
        return tau;
    }

    /// <summary>Задержки луча в отсчётах, минимальная равна TapCenter + 1 (как hw.beam_delays).</summary>
    public static double[] BeamDelays(double azDeg, Vec3? focus = null, Vec3[]? positions = null)
    {
        var tau = SteeringDelays(positions ?? ElementPositions(), azDeg, focus);
        return tau.Select(t => t * Hw.Fs + Hw.TapCenter + 1).ToArray();
    }
}
