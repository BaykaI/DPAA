using System.Text.Json;
using Dpaa.Core;
using Xunit;

namespace Dpaa.Core.Tests;

/// <summary>
/// Сверка с эталонами, посчитанными Python-моделью (scripts/make_csharp_golden.py):
/// кадры должны совпадать байт в байт — прошивка ПЛИС проверена против той же модели.
/// </summary>
public class GoldenTests
{
    static readonly JsonElement G = JsonDocument.Parse(File.ReadAllText(
        Path.Combine(AppContext.BaseDirectory, "golden.json"))).RootElement;

    static string[] Hex(IEnumerable<byte[]> frames) => frames.Select(Protocol.Hex).ToArray();

    static string[] Expected(JsonElement e) => e.EnumerateArray().Select(x => x.GetString()!).ToArray();

    static void SameFrames(JsonElement expected, IEnumerable<byte[]> actual, string what)
    {
        var exp = Expected(expected);
        var act = Hex(actual);
        Assert.True(exp.Length == act.Length, $"{what}: кадров {act.Length}, ожидалось {exp.Length}");
        for (int i = 0; i < exp.Length; i++)
            Assert.True(exp[i] == act[i], $"{what}: кадр {i}: {act[i]} != {exp[i]}");
    }

    [Fact]
    public void ProtocolFrames()
    {
        foreach (var c in G.GetProperty("protocol").EnumerateArray())
        {
            int a = c.GetProperty("addr").GetInt32();
            long d = c.GetProperty("data").GetInt64();
            Assert.Equal(c.GetProperty("write").GetString(), Protocol.Hex(Protocol.EncodeWrite(a, d)));
            Assert.Equal(c.GetProperty("read").GetString(), Protocol.Hex(Protocol.EncodeRead(a)));
            var rsp = Protocol.EncodeResponse(a, (int)d);
            Assert.Equal((a, (int)d), Protocol.DecodeResponse(rsp));
        }
    }

    [Fact]
    public void BadResponseIsRejected()
    {
        var rsp = Protocol.EncodeResponse(0x100, 1234);
        rsp[4] ^= 1;
        Assert.Throws<FormatException>(() => Protocol.DecodeResponse(rsp));
    }

    [Fact]
    public void PhaseIncrements()
    {
        foreach (var c in G.GetProperty("phase_inc").EnumerateArray())
            Assert.Equal(c.GetProperty("inc").GetUInt32(), Fixed.PhaseInc(c.GetProperty("f").GetDouble()));
    }

    [Fact]
    public void BiquadCoefficients()
    {
        foreach (var c in G.GetProperty("biquad").EnumerateArray())
        {
            var exp = c.GetProperty("coef").EnumerateArray().Select(x => x.GetInt32()).ToArray();
            Assert.Equal(exp, Fixed.BiquadBandpass(c.GetProperty("lo").GetDouble(), c.GetProperty("hi").GetDouble()));
        }
    }

    [Fact]
    public void GainRegisters()
    {
        foreach (var c in G.GetProperty("gain_reg").EnumerateArray())
            Assert.Equal(c.GetProperty("reg").GetInt32(), Fixed.GainReg(c.GetProperty("x").GetDouble()));
    }

    [Fact]
    public void Windows()
    {
        foreach (var c in G.GetProperty("windows").EnumerateArray())
        {
            var kind = Enum.Parse<Taper>(c.GetProperty("kind").GetString()!, ignoreCase: true);
            int n = c.GetProperty("n").GetInt32();
            var exp = c.GetProperty("w").EnumerateArray().Select(x => x.GetDouble()).ToArray();
            var act = Tapers.Window(n, kind, c.GetProperty("sll").GetDouble());
            for (int i = 0; i < n; i++)
                Assert.True(Math.Abs(exp[i] - act[i]) < 1e-12, $"{kind} n={n}: w[{i}] = {act[i]}, ожидалось {exp[i]}");
        }
    }

    [Fact]
    public void BeamDelays()
    {
        foreach (var c in G.GetProperty("delays").EnumerateArray())
        {
            double az = c.GetProperty("az").GetDouble();
            Vec3? focus = null;
            if (c.GetProperty("focus").ValueKind == JsonValueKind.Array)
            {
                var f = c.GetProperty("focus").EnumerateArray().Select(x => x.GetDouble()).ToArray();
                focus = new Vec3(f[0], f[1], f[2]);
            }
            var tx = c.GetProperty("tx").EnumerateArray().Select(x => x.GetInt32()).ToArray();
            var rx = c.GetProperty("rx").EnumerateArray().Select(x => x.GetInt32()).ToArray();
            Assert.Equal(tx, Geometry.BeamDelays(az, focus).Select(Fixed.DelayReg).ToArray());
            Assert.Equal(rx, Geometry.BeamDelays(az, focus, Geometry.MicPositions()).Select(Fixed.DelayReg).ToArray());
        }
    }

    [Fact]
    public void GeneratorCommands()
    {
        foreach (var c in G.GetProperty("gen").EnumerateArray())
        {
            static (double, double)? Pair(JsonElement e) => e.ValueKind == JsonValueKind.Array
                ? (e[0].GetDouble(), e[1].GetDouble()) : null;
            var ch = c.GetProperty("chirp");
            (double, double, double)? chirp = ch.ValueKind == JsonValueKind.Array
                ? (ch[0].GetDouble(), ch[1].GetDouble(), ch[2].GetDouble()) : null;
            var fq = c.GetProperty("freq");
            var frames = Commands.Gen(c.GetProperty("beam").GetInt32(), (GenMode)c.GetProperty("mode").GetInt32(),
                fq.ValueKind == JsonValueKind.Number ? fq.GetDouble() : null, c.GetProperty("amp").GetDouble(),
                chirp, Pair(c.GetProperty("burst")), Pair(c.GetProperty("band")), c.GetProperty("env_ms").GetDouble());
            SameFrames(c.GetProperty("frames"), frames, $"генератор {c}");
        }
    }

    static Distribution Dist(JsonElement a)
    {
        string S(string k, string def) => a.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.String
            ? v.GetString()! : def;
        double D(string k, double def) => a.TryGetProperty(k, out var v) && v.ValueKind == JsonValueKind.Number
            ? v.GetDouble() : def;
        var off = S("off", "");
        var weights = S("weights", "");
        return new Distribution
        {
            Taper = Enum.Parse<Taper>(S("taper", "uniform"), ignoreCase: true),
            SllDb = D("sll", 30),
            Off = off.Length == 0 ? new HashSet<int>() : off.Split(',').Select(v => int.Parse(v) - 1).ToHashSet(),
            Weights = weights.Length == 0 ? null : weights.Split(',').Select(v => double.Parse(v, System.Globalization.CultureInfo.InvariantCulture)).ToArray(),
        };
    }

    [Fact]
    public void ScenariosMatchDpaaCtl()
    {
        foreach (var c in G.GetProperty("scenarios").EnumerateArray())
        {
            var a = c.GetProperty("args");
            double D(string k, double def) => a.TryGetProperty(k, out var v) ? v.GetDouble() : def;
            bool B(string k) => a.TryGetProperty(k, out var v) && v.GetBoolean();
            var src = new Source(B("noise") ? SourceKind.Noise : B("chirp") ? SourceKind.Chirp : SourceKind.Tone,
                                 D("tone", 3000));
            double amp = D("amp", 0.25);
            var dist = Dist(a);
            var name = c.GetProperty("name").GetString();
            List<byte[]> frames = name switch
            {
                "beam" => Scenarios.Beam(src, D("az", 0), dist, amp),
                "focus" => Scenarios.Focus(src, D("x", 0), D("y", 1), dist, amp),
                "two" => Scenarios.TwoBeams(new Source(SourceKind.Tone, D("tone1", 2500)), D("az1", -35),
                                            new Source(SourceKind.Chirp, D("tone2", 3500)), D("az2", 35), dist, amp),
                "listen" => Scenarios.Listen(D("left", -30), D("right", 30), dist),
                _ => throw new InvalidOperationException(name),
            };
            SameFrames(c.GetProperty("frames"), frames, $"сценарий {name} {a}");
        }
    }

    [Fact]
    public void ElementsTest()
    {
        var frames = Scenarios.ElementsSetup(2000, 0.25);
        for (int e = 0; e < Hw.NElem; e++) frames.AddRange(Scenarios.ElementStep(e));
        frames.AddRange(Scenarios.Mute());
        SameFrames(G.GetProperty("elements"), frames, "поэлементный тест");
    }

    [Fact]
    public void Sweep()
    {
        SameFrames(G.GetProperty("sweep_setup"), Scenarios.SweepSetup(new Source(SourceKind.Tone, 3000), 0.25),
                   "подготовка сканирования");
        foreach (var c in G.GetProperty("sweep_step").EnumerateArray())
            SameFrames(c.GetProperty("frames"), Scenarios.SweepStep(c.GetProperty("az").GetDouble(),
                       Distribution.Uniform), "шаг сканирования");
    }
}
