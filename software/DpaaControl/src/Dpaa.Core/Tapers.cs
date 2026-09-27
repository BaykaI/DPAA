namespace Dpaa.Core;

public enum Taper { Uniform, Taylor, Chebyshev, Hann }

/// <summary>
/// Амплитудное распределение по элементам (весовые окна как в scipy.signal.windows,
/// dpaa/patterns.py → taper). Максимум окна равен 1.
/// </summary>
public static class Tapers
{
    public static double[] Window(int n, Taper kind, double sllDb = 30)
    {
        double[] w = kind switch
        {
            Taper.Uniform => Enumerable.Repeat(1.0, n).ToArray(),
            Taper.Taylor => Taylor(n, 4, sllDb),
            Taper.Chebyshev => Chebyshev(n, sllDb),
            Taper.Hann => Enumerable.Range(1, n)
                .Select(k => 0.5 - 0.5 * Math.Cos(2 * Math.PI * k / (n + 1))).ToArray(),
            _ => throw new ArgumentOutOfRangeException(nameof(kind)),
        };
        double max = w.Max();
        return w.Select(v => v / max).ToArray();
    }

    /// <summary>Окно Тейлора (nbar, уровень боковых лепестков sll, без нормировки) — scipy.windows.taylor.</summary>
    static double[] Taylor(int m, int nbar, double sll)
    {
        double b = Math.Pow(10, sll / 20);
        double a = Math.Acosh(b) / Math.PI;
        double s2 = nbar * nbar / (a * a + (nbar - 0.5) * (nbar - 0.5));
        var fm = new double[nbar - 1];
        for (int mi = 0; mi < nbar - 1; mi++)
        {
            double mm = mi + 1, m2 = mm * mm;
            double numer = (mi % 2 == 0 ? 1 : -1);
            for (int j = 1; j < nbar; j++)
                numer *= 1 - m2 / s2 / (a * a + (j - 0.5) * (j - 0.5));
            double denom = 2;
            for (int j = 1; j < nbar; j++)
                if (j != mi + 1) denom *= 1 - m2 / ((double)j * j);
            fm[mi] = numer / denom;
        }
        var w = new double[m];
        for (int n = 0; n < m; n++)
        {
            double s = 1;
            for (int mi = 0; mi < nbar - 1; mi++)
                s += 2 * fm[mi] * Math.Cos(2 * Math.PI * (mi + 1) * (n - m / 2.0 + 0.5) / m);
            w[n] = s;
        }
        return w;
    }

    /// <summary>Окно Дольфа — Чебышёва с подавлением боковых лепестков at дБ — scipy.windows.chebwin.</summary>
    static double[] Chebyshev(int m, double at)
    {
        if (m == 1) return new[] { 1.0 };
        double order = m - 1.0;
        double beta = Math.Cosh(Math.Acosh(Math.Pow(10, Math.Abs(at) / 20)) / order);
        var p = new double[m];
        for (int k = 0; k < m; k++)
        {
            double x = beta * Math.Cos(Math.PI * k / m);
            p[k] = x > 1 ? Math.Cosh(order * Math.Acosh(x))
                 : x < -1 ? (2 * (m % 2) - 1) * Math.Cosh(order * Math.Acosh(-x))
                 : Math.Cos(order * Math.Acos(x));
        }
        // вещественная часть ДПФ; для чётного m — со сдвигом на полотсчёта
        var re = new double[m];
        for (int j = 0; j < m; j++)
        {
            double s = 0;
            for (int k = 0; k < m; k++)
            {
                double ph = -2 * Math.PI * j * k / m + (m % 2 == 0 ? Math.PI * k / m : 0);
                s += p[k] * Math.Cos(ph);
            }
            re[j] = s;
        }
        var w = new List<double>(m);
        if (m % 2 == 1)
        {
            int h = (m + 1) / 2;
            for (int j = h - 1; j >= 1; j--) w.Add(re[j]);
            for (int j = 0; j < h; j++) w.Add(re[j]);
        }
        else
        {
            int h = m / 2 + 1;
            for (int j = h - 1; j >= 1; j--) w.Add(re[j]);
            for (int j = 1; j < h; j++) w.Add(re[j]);
        }
        return w.ToArray();
    }
}

/// <summary>
/// Параметры амплитудного распределения — то же, что общие ключи dpaa_ctl.py
/// (--taper, --sll, --weights, --off).
/// </summary>
public sealed record Distribution
{
    public Taper Taper { get; init; } = Taper.Uniform;
    public double SllDb { get; init; } = 30;
    /// <summary>Произвольные веса элементов (могут быть отрицательными); перекрывают окно.</summary>
    public double[]? Weights { get; init; }
    /// <summary>Выключенные элементы, номера с 0.</summary>
    public IReadOnlySet<int> Off { get; init; } = new HashSet<int>();

    public static Distribution Uniform { get; } = new();

    /// <summary>Нормированные (max |w| = 1) веса n элементов с учётом выключенных.</summary>
    public double[] ElementWeights(int n)
    {
        var w = (Weights ?? Tapers.Window(n, Taper, SllDb)).ToArray();
        if (w.Length != n) throw new ArgumentException($"нужно {n} весов, задано {w.Length}");
        foreach (int i in Off)
            if (i >= 0 && i < n) w[i] = 0;
        double max = w.Max(Math.Abs);
        if (max == 0) throw new InvalidOperationException("все элементы выключены");
        return w.Select(v => v / max).ToArray();
    }
}
