namespace Dpaa.Core;

public enum SourceKind { Tone, Noise, Chirp }

/// <summary>Сигнал генератора луча: тон заданной частоты, полосовой шум 1.5–4.3 кГц или ЛЧМ-пачки 2→4 кГц.</summary>
public sealed record Source(SourceKind Kind = SourceKind.Tone, double ToneHz = 3000)
{
    public static readonly (double Lo, double Hi) NoiseBand = (1500, 4300);
    public static readonly (double F0, double F1, double Dur) ChirpSweep = (2000, 4000, 0.05);
    public static readonly (double On, double Period) ChirpBurst = (0.05, 0.3);

    public List<byte[]> Commands(int beam, double amp)
    {
        amp = Math.Min(amp, Hw.MaxAmp);
        return Kind switch
        {
            SourceKind.Noise => Dpaa.Core.Commands.Gen(beam, GenMode.Noise, amp: amp, band: NoiseBand),
            SourceKind.Chirp => Dpaa.Core.Commands.Gen(beam, GenMode.Chirp, amp: amp, chirp: ChirpSweep,
                                                       burst: ChirpBurst),
            _ => Dpaa.Core.Commands.Gen(beam, GenMode.Sine, freq: ToneHz, amp: amp),
        };
    }

    /// <summary>Частота, на которой имеет смысл рисовать диаграмму направленности.</summary>
    public double DisplayHz => Kind switch
    {
        SourceKind.Tone => ToneHz,
        SourceKind.Chirp => 3000,
        _ => 3000,
    };
}

/// <summary>
/// Сценарии демонстрации — те же последовательности кадров, что у tools/dpaa_ctl.py
/// (совпадение проверяется тестами по эталонам).
/// </summary>
public static class Scenarios
{
    static readonly double[] Zeros = new double[Hw.NElem];

    /// <summary>Один луч в направлении az (dpaa_ctl.py beam).</summary>
    public static List<byte[]> Beam(Source src, double azDeg, Distribution dist, double amp)
    {
        var c = src.Commands(0, amp);
        c.AddRange(Commands.Gen(1, GenMode.Off));
        c.AddRange(Commands.TxBeam(0, azDeg, dist: dist));
        c.AddRange(Commands.TxBeam(1, gains: Zeros));
        c.Add(Commands.Commit());
        c.Add(Commands.Write(Hw.RegCtrl, 3));
        return c;
    }

    /// <summary>Фокусировка в точку (x, y) в метрах (dpaa_ctl.py focus).</summary>
    public static List<byte[]> Focus(Source src, double x, double y, Distribution dist, double amp)
    {
        var c = src.Commands(0, amp);
        c.AddRange(Commands.TxBeam(0, focus: new Vec3(x, y, 0), dist: dist));
        c.AddRange(Commands.TxBeam(1, gains: Zeros));
        c.Add(Commands.Commit());
        c.Add(Commands.Write(Hw.RegCtrl, 3));
        return c;
    }

    /// <summary>Два независимых луча с разными сигналами (dpaa_ctl.py two-beams).</summary>
    public static List<byte[]> TwoBeams(Source src1, double az1, Source src2, double az2, Distribution dist,
                                        double amp)
    {
        var c = src1.Commands(0, amp);
        c.AddRange(src2.Commands(1, amp));
        c.AddRange(Commands.TxBeam(0, az1, dist: dist));
        c.AddRange(Commands.TxBeam(1, az2, dist: dist));
        c.Add(Commands.Commit());
        c.Add(Commands.Write(Hw.RegCtrl, 3));
        return c;
    }

    /// <summary>Подготовка сканирования: сигнал, второй луч выключен, излучение разрешено.</summary>
    public static List<byte[]> SweepSetup(Source src, double amp)
    {
        var c = src.Commands(0, amp);
        c.AddRange(Commands.Gen(1, GenMode.Off));
        c.AddRange(Commands.TxBeam(1, gains: Zeros));
        c.Add(Commands.Write(Hw.RegCtrl, 3));
        return c;
    }

    /// <summary>Одно обновление луча при сканировании (≈ 50 раз в секунду).</summary>
    public static List<byte[]> SweepStep(double azDeg, Distribution dist)
    {
        var c = Commands.TxBeam(0, azDeg, dist: dist);
        c.Add(Commands.Commit());
        return c;
    }

    /// <summary>Угол «маятника»: от lo до hi и обратно за period секунд.</summary>
    public static double SweepAngle(double tSec, double lo, double hi, double period)
    {
        double ph = tSec / period % 1.0;
        return lo + (hi - lo) * (1 - Math.Abs(2 * ph - 1));
    }

    /// <summary>Поэлементный тест: подготовка.</summary>
    public static List<byte[]> ElementsSetup(double toneHz, double amp)
    {
        var c = Commands.Gen(0, GenMode.Sine, freq: toneHz, amp: Math.Min(amp, Hw.MaxAmp));
        c.AddRange(Commands.Gen(1, GenMode.Off));
        c.Add(Commands.Write(Hw.RegCtrl, 1));
        return c;
    }

    /// <summary>Поэлементный тест: звучит только элемент e (с 0).</summary>
    public static List<byte[]> ElementStep(int e)
    {
        var g = new double[Hw.NElem];
        g[e] = 1.0;
        var c = Commands.TxBeam(0, gains: g);
        c.Add(Commands.Commit());
        return c;
    }

    /// <summary>Два луча приёма в наушники: левое ухо и правое (dpaa_ctl.py listen).</summary>
    public static List<byte[]> Listen(double leftDeg, double rightDeg, Distribution dist)
    {
        var c = Commands.RxBeam(0, leftDeg, dist: dist);
        c.AddRange(Commands.RxBeam(1, rightDeg, dist: dist));
        c.Add(Commands.Commit(tx: false, rx: true));
        c.Add(Commands.Write(Hw.RegCtrl, 2));
        return c;
    }

    public static List<byte[]> Mute() => new() { Commands.Write(Hw.RegCtrl, 0) };
}
