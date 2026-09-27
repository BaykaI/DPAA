namespace Dpaa.Core;

/// <summary>Форматы регистров ПЛИС и фиксированная точка (как dpaa/hw.py).</summary>
public static class Fixed
{
    /// <summary>
    /// Округление к ближайшему, половинки — к чётному (как numpy.round и round в Python).
    /// </summary>
    static long RoundEven(double x) => (long)Math.Round(x, MidpointRounding.ToEven);

    /// <summary>Число с плавающей точкой -> целое Q(bits-frac).frac с насыщением.</summary>
    public static long Quantize(double x, int frac = Hw.CoefFrac, int bits = Hw.W)
    {
        long q = RoundEven(x * (1L << frac));
        long lo = -(1L << (bits - 1)), hi = (1L << (bits - 1)) - 1;
        return Math.Clamp(q, lo, hi);
    }

    /// <summary>Вес (1.0 = 65536) -> 18-битный регистр со знаком.</summary>
    public static int GainReg(double gain) => (int)Quantize(gain);

    /// <summary>Задержка в отсчётах -> регистр (целая часть &lt;&lt; 5 | фаза 1/32).</summary>
    public static int DelayReg(double delaySamples)
    {
        long q = RoundEven(delaySamples * Hw.Phases);
        if (q < Hw.TapCenter * Hw.Phases || q >= Hw.MaxDelay * Hw.Phases)
            throw new ArgumentOutOfRangeException(nameof(delaySamples),
                $"задержка {delaySamples:F2} вне диапазона [{Hw.TapCenter}, {Hw.MaxDelay}) отсчётов");
        return (int)q;
    }

    /// <summary>Регистр задержки -> задержка в секундах.</summary>
    public static double DelaySeconds(int reg) => reg / (double)Hw.Phases / Hw.Fs;

    /// <summary>Приращение фазы 32-битного синтезатора для частоты f.</summary>
    public static uint PhaseInc(double freqHz, double fs = Hw.Fs) =>
        (uint)(RoundEven(freqHz / fs * 4294967296.0) & 0xFFFFFFFF);

    /// <summary>
    /// Полосовой фильтр Баттерворта 1-го порядка (билинейное преобразование с предыскажением,
    /// как scipy.signal.butter): коэффициенты b0 b1 b2 a1 a2 в формате Q2.16.
    /// </summary>
    public static int[] BiquadBandpass(double fLo, double fHi, double fs = Hw.Fs)
    {
        const double k = 4.0;                         // 2·fs нормированной частоты (fs = 2)
        double w1 = k * Math.Tan(Math.PI * fLo / fs);
        double w2 = k * Math.Tan(Math.PI * fHi / fs);
        double bw = w2 - w1, w0sq = w1 * w2;
        double a0 = k * k + bw * k + w0sq;
        double[] c =
        {
            bw * k / a0, 0.0, -bw * k / a0,
            2 * (w0sq - k * k) / a0, (k * k - bw * k + w0sq) / a0,
        };
        return c.Select(v => (int)Quantize(v)).ToArray();
    }
}
