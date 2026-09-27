namespace Dpaa.Core;

/// <summary>
/// Образ регистров ПЛИС, собранный из отправленных кадров записи. По нему окно рисует
/// диаграмму направленности (показывается ровно то, что ушло в установку), а симулятор
/// изображает уровни микрофонов.
/// </summary>
public sealed class RegisterFile
{
    readonly Dictionary<int, int> _regs = new();

    public void Apply(IEnumerable<byte[]> frames)
    {
        foreach (var f in frames)
            if (Protocol.TryDecodeRequest(f, out int a, out int d, out bool read) && !read)
                _regs[a] = d;
    }

    public int this[int addr] => _regs.TryGetValue(addr, out int v) ? v : 0;

    public bool TxEnabled => (this[Hw.RegCtrl] & 1) != 0;
    public bool RxEnabled => (this[Hw.RegCtrl] & 2) != 0;

    /// <summary>Вес занимает младшие 18 бит 24-битного поля данных (дополнительный код).</summary>
    static int Signed18(int v)
    {
        v &= 0x3FFFF;
        return v >= 0x20000 ? v - 0x40000 : v;
    }

    /// <summary>Таблица луча передачи: регистры задержки и веса (1.0 = единица).</summary>
    public (int[] Delays, double[] Gains) TxTable(int beam) => Table(Hw.TxDelay, Hw.TxGain, Hw.NElem, Hw.TxBeams, beam);

    /// <summary>Таблица луча приёма (выход output = левое/правое ухо).</summary>
    public (int[] Delays, double[] Gains) RxTable(int output) =>
        Table(Hw.RxDelay, Hw.RxGain, Hw.NMics, 1, 0, output * Hw.NMics);

    (int[], double[]) Table(int dBase, int gBase, int n, int stride, int beam, int offset = 0)
    {
        var d = new int[n];
        var g = new double[n];
        for (int i = 0; i < n; i++)
        {
            int idx = offset + i * stride + beam;
            d[i] = Math.Max(this[dBase + idx] & 0xFFFF, Hw.TapCenter * Hw.Phases);   // как в ПЛИС: [15:0]
            g[i] = Signed18(this[gBase + idx]) / (double)Hw.Unity;
        }
        return (d, g);
    }

    public GenMode Mode(int beam) => (GenMode)(this[Hw.GenBase[beam] + Hw.GenMode] & 3);

    public double Amp(int beam) => this[Hw.GenBase[beam] + Hw.GenAmp] / (double)((1 << 17) - 1);

    /// <summary>Частота синуса или начальная частота ЛЧМ луча beam, Гц.</summary>
    public double Freq(int beam)
    {
        int b = Hw.GenBase[beam];
        uint inc = (uint)(this[b + Hw.GenIncLo] | (this[b + Hw.GenIncHi] << 16));
        return inc / 4294967296.0 * Hw.Fs;
    }
}
