using System.Numerics;

namespace Dpaa.Core;

/// <summary>
/// Диаграмма направленности решётки в горизонтальной плоскости по реальным (квантованным)
/// регистрам задержки и веса — то, что на самом деле излучит или примет установка.
/// </summary>
public static class Pattern
{
    /// <summary>
    /// Уровень (дБ относительно максимально возможного Σ|g|) для углов anglesDeg.
    /// radius = null — дальняя зона; иначе — окружность этого радиуса (для фокусировки).
    /// </summary>
    public static double[] Compute(Vec3[] positions, int[] delayRegs, double[] gains, double freq,
                                   double[] anglesDeg, double? radius = null, double floorDb = -40)
    {
        double norm = gains.Sum(Math.Abs);
        var res = new double[anglesDeg.Length];
        if (norm == 0)
        {
            Array.Fill(res, floorDb);
            return res;
        }
        double k = 2 * Math.PI * freq / Hw.SoundSpeed;
        double w = 2 * Math.PI * freq;
        for (int a = 0; a < anglesDeg.Length; a++)
        {
            var u = Geometry.Direction(anglesDeg[a]);
            Complex s = Complex.Zero;
            double refR = radius ?? 1;
            for (int n = 0; n < positions.Length; n++)
            {
                double tau = Fixed.DelaySeconds(delayRegs[n]);
                if (radius is { } r)
                {
                    var pt = new Vec3(u.X * r, u.Y * r, 0);
                    double d = (pt - positions[n]).Length;
                    s += gains[n] * refR / d * Complex.FromPolarCoordinates(1, -w * tau - k * d);
                }
                else
                {
                    s += gains[n] * Complex.FromPolarCoordinates(1, -w * tau + k * positions[n].Dot(u));
                }
            }
            res[a] = Math.Max(floorDb, 20 * Math.Log10(Math.Max(s.Magnitude / norm, 1e-12)));
        }
        return res;
    }

    public static double[] Angles(double step = 0.5)
    {
        int n = (int)Math.Round(180 / step) + 1;
        return Enumerable.Range(0, n).Select(i => -90 + i * step).ToArray();
    }

    /// <summary>Частота, выше которой при отклонении на maxSteerDeg появляется дифракционный лепесток.</summary>
    public static double GratingLobeFreeHz(double pitch = Hw.Pitch, double maxSteerDeg = 90) =>
        Hw.SoundSpeed / (pitch * (1 + Math.Sin(Math.Abs(maxSteerDeg) * Math.PI / 180)));
}
