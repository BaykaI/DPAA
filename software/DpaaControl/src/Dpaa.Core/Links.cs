using System.Diagnostics;
using System.IO.Ports;

namespace Dpaa.Core;

/// <summary>Канал связи с ПЛИС: запись кадров и чтение регистров. Реализации потокобезопасны.</summary>
public interface IDpaaLink : IDisposable
{
    string Name { get; }
    void Send(IReadOnlyList<byte[]> frames);
    int Read(int addr);
}

/// <summary>Последовательный порт: USB-UART отладчика DAPLink или адаптер CP2102/CH340, 1 Мбит/с.</summary>
public sealed class SerialLink : IDpaaLink
{
    readonly SerialPort _port;
    readonly object _lock = new();

    public SerialLink(string portName, int baud = 1_000_000)
    {
        _port = new SerialPort(portName, baud, Parity.None, 8, StopBits.One)
        {
            ReadTimeout = 200,
            WriteTimeout = 1000,
            Handshake = Handshake.None,
        };
        _port.Open();
        Name = portName;
    }

    public string Name { get; }

    public void Send(IReadOnlyList<byte[]> frames)
    {
        var buf = new byte[frames.Count * Protocol.FrameLen];
        for (int i = 0; i < frames.Count; i++) frames[i].CopyTo(buf, i * Protocol.FrameLen);
        lock (_lock) _port.Write(buf, 0, buf.Length);
    }

    public int Read(int addr)
    {
        lock (_lock)
        {
            _port.DiscardInBuffer();
            var req = Protocol.EncodeRead(addr);
            _port.Write(req, 0, req.Length);
            var rsp = new byte[Protocol.FrameLen];
            int got = 0;
            while (got < rsp.Length)
                got += _port.Read(rsp, got, rsp.Length - got);   // TimeoutException, если ответа нет
            var (a, d) = Protocol.DecodeResponse(rsp);
            if (a != addr) throw new IOException($"ответ на адрес 0x{a:X4}, ожидался 0x{addr:X4}");
            return d;
        }
    }

    public static string[] PortNames() => SerialPort.GetPortNames().OrderBy(s => s).ToArray();

    public void Dispose() => _port.Dispose();
}

/// <summary>
/// Программная модель ПЛИС для работы без железа: хранит регистры, отвечает на чтение
/// идентификатора и счётчика кадров, а уровни микрофонов изображает по записанным таблицам
/// (калибровочный зонд стоит на нормали в 2.5 м — при отклонении луча его уровень падает).
/// </summary>
public sealed class SimulatedLink : IDpaaLink
{
    readonly RegisterFile _regs = new();
    readonly Stopwatch _clock = Stopwatch.StartNew();
    readonly Random _rnd = new(1);
    readonly object _lock = new();
    public static readonly Vec3 ProbePosition = new(0, 2.5, 0);

    public string Name => "Симулятор";

    public void Send(IReadOnlyList<byte[]> frames)
    {
        lock (_lock) _regs.Apply(frames);
    }

    public int Read(int addr)
    {
        lock (_lock)
        {
            if (addr == Hw.RegId) return Hw.IdValue;
            if (addr == Hw.RegFrames) return (int)((long)(_clock.Elapsed.TotalSeconds * Hw.Fs) & 0xFFFFFF);
            if (addr == Hw.RegCtrl) return _regs[Hw.RegCtrl] & 3;
            if (addr >= Hw.RegPeak && addr <= Hw.RegPeak + Hw.NMics) return Peak(addr - Hw.RegPeak);
            return 0;
        }
    }

    int Peak(int mic)
    {
        double level = 3e-4 * (1 + _rnd.NextDouble());            // ≈ −70 дБПШ — шум зала
        for (int beam = 0; _regs.TxEnabled && beam < Hw.TxBeams; beam++)
        {
            if (_regs.Mode(beam) == GenMode.Off) continue;
            double amp = _regs.Amp(beam);
            var (d, g) = _regs.TxTable(beam);
            if (mic < Hw.NMics)
            {
                level += 0.6 * amp * Math.Abs(g[mic]);             // свой динамик в 3 см — громче всех
                continue;
            }
            double f = _regs.Mode(beam) == GenMode.Sine ? _regs.Freq(beam) : 3000;
            double az = Math.Atan2(ProbePosition.X, ProbePosition.Y) * 180 / Math.PI;
            double db = Pattern.Compute(Geometry.ElementPositions(), d, g, f, new[] { az },
                                        ProbePosition.Length, -80)[0];
            level += 0.25 * amp * g.Sum(Math.Abs) / Hw.NElem * Math.Pow(10, db / 20);
        }
        return (int)(Math.Min(1.0, level) * (1 << 23));
    }

    public void Dispose() { }
}
