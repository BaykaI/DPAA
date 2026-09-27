using Dpaa.Core;
using Xunit;

namespace Dpaa.Core.Tests;

/// <summary>Проверки физики и безопасности, которых нет в эталонах.</summary>
public class BehaviourTests
{
    static readonly double[] Angles = Pattern.Angles(0.5);

    static double PeakAngle(double[] db) => Angles[Array.IndexOf(db, db.Max())];

    [Theory]
    [InlineData(-60)]
    [InlineData(-20)]
    [InlineData(0)]
    [InlineData(35)]
    public void PatternPeaksAtSteeringAngle(double az)
    {
        var d = Geometry.BeamDelays(az).Select(Fixed.DelayReg).ToArray();
        var g = Enumerable.Repeat(0.5, Hw.NElem).ToArray();
        var db = Pattern.Compute(Geometry.ElementPositions(), d, g, 3000, Angles);
        Assert.InRange(PeakAngle(db), az - 1, az + 1);
        Assert.InRange(db.Max(), -0.1, 0.0);
    }

    [Fact]
    public void TaylorLowersSidelobes()
    {
        var d = Geometry.BeamDelays(0).Select(Fixed.DelayReg).ToArray();
        // максимум за пределами главного лепестка (его ширина зависит от распределения)
        double Sidelobe(double[] g, double mainLobeDeg)
        {
            var db = Pattern.Compute(Geometry.ElementPositions(), d, g, 3000, Angles, floorDb: -80);
            return Angles.Zip(db).Where(p => Math.Abs(p.First) > mainLobeDeg).Max(p => p.Second) - db.Max();
        }
        double uni = Sidelobe(Distribution.Uniform.ElementWeights(16), 11);
        double tay = Sidelobe(new Distribution { Taper = Taper.Taylor, SllDb = 30 }.ElementWeights(16), 16);
        Assert.InRange(uni, -14, -12);                  // равномерное: −13 дБ
        Assert.True(tay < -27, $"Тейлор 30 дБ: боковые {tay:F1} дБ");
    }

    [Fact]
    public void FocusPatternPeaksAtFocusDirection()
    {
        var f = new Vec3(0.5, 1.0, 0);
        var d = Geometry.BeamDelays(0, f).Select(Fixed.DelayReg).ToArray();
        var db = Pattern.Compute(Geometry.ElementPositions(), d, Enumerable.Repeat(0.5, 16).ToArray(), 3000,
                                 Angles, radius: f.Length);
        Assert.InRange(PeakAngle(db), 25.5, 27.5);       // atan(0.5 / 1) = 26.6°
    }

    [Fact]
    public void AmplitudeIsCappedForSafety()
    {
        var loud = new Source(SourceKind.Tone, 3000).Commands(0, 1.0);
        var capped = new Source(SourceKind.Tone, 3000).Commands(0, Hw.MaxAmp);
        Assert.Equal(capped.Select(Protocol.Hex), loud.Select(Protocol.Hex));
    }

    [Fact]
    public void DelayOutOfRangeThrows()
    {
        Assert.Throws<ArgumentOutOfRangeException>(() => Fixed.DelayReg(1.0));
        Assert.Throws<ArgumentOutOfRangeException>(() => Fixed.DelayReg(Hw.MaxDelay));
    }

    [Fact]
    public void AllElementsOffIsRejected()
    {
        var d = new Distribution { Off = Enumerable.Range(0, 16).ToHashSet() };
        Assert.Throws<InvalidOperationException>(() => d.ElementWeights(16));
    }

    [Fact]
    public void SweepAngleIsTriangle()
    {
        Assert.Equal(-60, Scenarios.SweepAngle(0, -60, 60, 6), 6);
        Assert.Equal(60, Scenarios.SweepAngle(3, -60, 60, 6), 6);
        Assert.Equal(0, Scenarios.SweepAngle(4.5, -60, 60, 6), 6);
    }

    [Fact]
    public void RegisterFileDecodesWhatWasSent()
    {
        var w = Enumerable.Range(0, 16).Select(i => i < 8 ? 1.0 : -1.0).ToArray();
        var regs = new RegisterFile();
        regs.Apply(Scenarios.Beam(new Source(), 20, new Distribution { Weights = w }, 0.25));
        var (d, g) = regs.TxTable(0);
        Assert.Equal(Geometry.BeamDelays(20).Select(Fixed.DelayReg), d);
        Assert.Equal(w.Select(v => 0.5 * v), g);
        regs.Apply(Scenarios.Listen(-30, 30, Distribution.Uniform));
        var (rd, rg) = regs.RxTable(1);
        Assert.Equal(Geometry.BeamDelays(30, null, Geometry.MicPositions()).Select(Fixed.DelayReg), rd);
        Assert.All(rg, v => Assert.Equal(1.0 / 16, v, 4));
        Assert.True(regs.RxEnabled);
        Assert.False(regs.TxEnabled);
    }

    [Fact]
    public void SimulatorAnswersLikeFpga()
    {
        using var sim = new SimulatedLink();
        Assert.Equal(Hw.IdValue, sim.Read(Hw.RegId));
        sim.Send(Scenarios.Beam(new Source(), 0, Distribution.Uniform, 0.25));
        Assert.Equal(3, sim.Read(Hw.RegCtrl));
        int onAxis = sim.Read(Hw.RegPeak + Hw.NMics);
        sim.Send(Scenarios.Beam(new Source(), 60, Distribution.Uniform, 0.25));
        int offAxis = sim.Read(Hw.RegPeak + Hw.NMics);
        Assert.True(onAxis > 4 * offAxis, $"зонд на нормали: {onAxis} при луче 0°, {offAxis} при 60°");
        sim.Send(Scenarios.Mute());
        Assert.Equal(0, sim.Read(Hw.RegCtrl));
    }
}
