namespace Dpaa.Core;

/// <summary>Кадры записи регистров: таблицы лучей и генераторы (как функции dpaa/hw.py).</summary>
public static class Commands
{
    public static byte[] Write(int addr, long data) => Protocol.EncodeWrite(addr, data);

    public static byte[] Ctrl(bool tx, bool rx) => Write(Hw.RegCtrl, (tx ? 1 : 0) | (rx ? 2 : 0));

    public static byte[] Commit(bool tx = true, bool rx = false) =>
        Write(Hw.RegCommit, (tx ? 1 : 0) | (rx ? 2 : 0));

    /// <summary>
    /// Задержки и веса луча beam на передачу (без «применить»). Веса = level · распределение;
    /// gains — готовые веса, перекрывают распределение.
    /// </summary>
    public static List<byte[]> TxBeam(int beam, double azDeg = 0, Vec3? focus = null, double[]? gains = null,
                                      Distribution? dist = null, double level = Hw.TxLevel, int nOut = Hw.NElem)
    {
        var d = Geometry.BeamDelays(azDeg, focus).Select(Fixed.DelayReg).ToArray();
        gains ??= (dist ?? Distribution.Uniform).ElementWeights(nOut).Select(v => level * v).ToArray();
        var cmds = new List<byte[]>(2 * nOut);
        for (int o = 0; o < nOut; o++)
        {
            int idx = o * Hw.TxBeams + beam;
            cmds.Add(Write(Hw.TxDelay + idx, d[o]));
            cmds.Add(Write(Hw.TxGain + idx, Fixed.GainReg(gains[o])));
        }
        return cmds;
    }

    /// <summary>Задержки и веса луча приёма; веса нормированы к единичному усилению в направлении луча.</summary>
    public static List<byte[]> RxBeam(int output, double azDeg = 0, Vec3? focus = null, double[]? gains = null,
                                      Distribution? dist = null, int nIn = Hw.NMics)
    {
        var d = Geometry.BeamDelays(azDeg, focus, Geometry.MicPositions(nIn)).Select(Fixed.DelayReg).ToArray();
        if (gains is null)
        {
            // для окон веса положительны, и Σ|w| = Σw; произвольные веса могут быть отрицательными
            var w = (dist ?? Distribution.Uniform).ElementWeights(nIn);
            double sum = w.Sum(Math.Abs);
            gains = w.Select(v => v / sum).ToArray();
        }
        var cmds = new List<byte[]>(2 * nIn);
        for (int i = 0; i < nIn; i++)
        {
            int idx = output * nIn + i;
            cmds.Add(Write(Hw.RxDelay + idx, d[i]));
            cmds.Add(Write(Hw.RxGain + idx, Fixed.GainReg(gains[i])));
        }
        return cmds;
    }

    /// <summary>
    /// Настройка генератора луча beam (hw.gen_commands).
    /// chirp = (f0, f1, длительность, с); burst = (включено, период, с); band — полоса фильтра шума.
    /// </summary>
    public static List<byte[]> Gen(int beam, GenMode mode, double? freq = null, double amp = 0.5,
                                   (double F0, double F1, double Dur)? chirp = null,
                                   (double On, double Period)? burst = null,
                                   (double Lo, double Hi)? band = null, double envMs = 5.0)
    {
        int b = Hw.GenBase[beam];
        byte[] W(int off, long val) => Write(b + off, val);
        var cmds = new List<byte[]>();
        if (mode == GenMode.Chirp)
        {
            var (f0, f1, dur) = chirp ?? throw new ArgumentNullException(nameof(chirp));
            long n = (long)Math.Round(dur * Hw.Fs, MidpointRounding.ToEven);
            long inc0 = Fixed.PhaseInc(f0);
            long rate = (long)Math.Round((Fixed.PhaseInc(f1) - (double)inc0) / n, MidpointRounding.ToEven);
            cmds.Add(W(Hw.GenIncLo, inc0 & 0xFFFF));
            cmds.Add(W(Hw.GenIncHi, inc0 >> 16));
            cmds.Add(W(Hw.GenRateLo, rate & 0xFFFF));
            cmds.Add(W(Hw.GenRateHi, (rate >> 16) & 0xFFFF));
            cmds.Add(W(Hw.GenChirpLen, n));
        }
        else if (freq is { } f)
        {
            long inc = Fixed.PhaseInc(f);
            cmds.Add(W(Hw.GenIncLo, inc & 0xFFFF));
            cmds.Add(W(Hw.GenIncHi, inc >> 16));
        }
        if (band is { } bd)
        {
            var c = Fixed.BiquadBandpass(bd.Lo, bd.Hi);
            int[] offs = { Hw.GenB0, Hw.GenB1, Hw.GenB2, Hw.GenA1, Hw.GenA2 };
            for (int i = 0; i < 5; i++) cmds.Add(W(offs[i], c[i]));
            cmds.Add(W(Hw.GenFilt, 1));
        }
        else
        {
            cmds.Add(W(Hw.GenFilt, 0));
        }
        var (on, per) = burst ?? (0, 0);
        cmds.Add(W(Hw.GenPeriod, (long)Math.Round(per * Hw.Fs, MidpointRounding.ToEven)));
        cmds.Add(W(Hw.GenOnLen, (long)Math.Round(on * Hw.Fs, MidpointRounding.ToEven)));
        long step = Math.Max(1, (long)((1 << 17) / Math.Max(1.0, envMs * 1e-3 * Hw.Fs)));
        cmds.Add(W(Hw.GenEnvStep, step));
        cmds.Add(W(Hw.GenAmp, (long)(amp * ((1 << 17) - 1))));
        cmds.Add(W(Hw.GenMode, (int)mode));
        return cmds;
    }
}
