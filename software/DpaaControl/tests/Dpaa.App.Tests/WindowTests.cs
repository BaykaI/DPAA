using Avalonia;
using Avalonia.Headless;
using Avalonia.Headless.XUnit;
using Avalonia.Threading;
using Dpaa.App;
using Dpaa.Core;
using Xunit;

[assembly: AvaloniaTestApplication(typeof(Dpaa.App.Tests.TestApp))]
[assembly: AvaloniaTestIsolation(AvaloniaTestIsolationLevel.PerAssembly)]

namespace Dpaa.App.Tests;

public static class TestApp
{
    public static AppBuilder BuildAvaloniaApp() => AppBuilder.Configure<App>()
        .UseSkia().WithInterFont()
        .UseHeadless(new AvaloniaHeadlessPlatformOptions { UseHeadlessDrawing = false });
}

/// <summary>
/// Окно без экрана: подключение к симулятору, сценарии, снимки окна
/// (сохраняются в каталог screenshots рядом с тестами — удобно смотреть глазами).
/// </summary>
public class WindowTests
{
    static readonly string Shots = Path.Combine(AppContext.BaseDirectory, "screenshots");

    static void WaitUntil(Func<bool> cond, int ms = 3000)
    {
        var t = DateTime.Now;
        while (!cond())
        {
            Dispatcher.UIThread.RunJobs();
            if ((DateTime.Now - t).TotalMilliseconds > ms) throw new TimeoutException("условие не выполнилось");
            Thread.Sleep(10);
        }
    }

    static void Pump(int ms)
    {
        var t = DateTime.Now;
        while ((DateTime.Now - t).TotalMilliseconds < ms)
        {
            Dispatcher.UIThread.RunJobs();
            Thread.Sleep(10);
        }
    }

    static void Poll(MainViewModel vm)
    {
        Pump(100);
        var t = vm.PollAsync();
        WaitUntil(() => t.IsCompleted);
    }

    static (MainWindow, MainViewModel) Open()
    {
        var vm = new MainViewModel { SelectedPort = MainViewModel.SimPort };
        var w = new MainWindow { DataContext = vm };
        w.Show();
        vm.ConnectCommand.Execute(null);
        WaitUntil(() => vm.IsConnected);
        return (w, vm);
    }

    static void Shot(MainWindow w, string name)
    {
        Pump(400);
        Directory.CreateDirectory(Shots);
        w.CaptureRenderedFrame()?.Save(Path.Combine(Shots, name + ".png"));
    }

    static double PeakAngle(double[] db) => Controls.PatternPlot.Angles[Array.IndexOf(db, db.Max())];

    [AvaloniaFact]
    public void BeamFollowsSliderAndSimulatorProbe()
    {
        var (w, vm) = Open();
        Assert.Contains("DAA001", vm.Status);
        vm.ModeIndex = (int)Mode.Beam;
        vm.Az = 30;
        vm.StartCommand.Execute(null);
        WaitUntil(() => vm.IsRunning);
        Assert.InRange(PeakAngle(vm.Pattern0!), 29, 31);
        Poll(vm);
        Shot(w, "1_beam_30");

        // луч на зонд (0°) — зонд слышит громко; луч в сторону — тише.
        // В окне без экрана таймеры не идут, поэтому такт и опрос вызываем сами.
        vm.Az = 0;
        vm.Tick();
        Poll(vm);
        double onAxis = vm.Peaks![Hw.NMics];
        vm.Az = 60;
        vm.Tick();
        Poll(vm);
        double offAxis = vm.Peaks![Hw.NMics];
        Assert.True(onAxis > offAxis + 10, $"зонд: {onAxis:0.0} дБ при 0°, {offAxis:0.0} дБ при 60°");

        vm.StopCommand.Execute(null);
        WaitUntil(() => !vm.IsRunning);
        w.Close();
    }

    [AvaloniaFact]
    public void AllModesRender()
    {
        var (w, vm) = Open();
        vm.TaperIndex = 1;                        // Тейлор
        vm.ModeIndex = (int)Mode.Focus;
        vm.OnMapClicked(new Point(-0.4, 0.8), false);
        Assert.Equal(-0.4, vm.FocusX, 3);
        vm.StartCommand.Execute(null);
        Shot(w, "2_focus_taylor");

        vm.TaperIndex = 0;
        vm.ModeIndex = (int)Mode.TwoBeams;
        vm.OnMapClicked(new Point(1, 1), true);   // правая кнопка — луч 2 на 45°
        Assert.Equal(45, vm.Az2, 1);
        Shot(w, "3_two_beams");

        vm.ModeIndex = (int)Mode.Listen;
        Shot(w, "4_listen");

        vm.ModeIndex = (int)Mode.Sweep;
        for (int i = 0; i < 5; i++) { vm.Tick(); Pump(30); }
        Assert.InRange(vm.SweepFrom, -60, -60);
        Shot(w, "4b_sweep");

        vm.ModeIndex = (int)Mode.Beam;
        vm.EveryOtherCommand.Execute(null);
        vm.ToneHz = 4000;
        vm.Az = 0;
        Shot(w, "5_thinned_grating_lobes");

        vm.AllOnCommand.Execute(null);
        vm.UseCustom = true;
        vm.CustomWeights = "1,2,3";
        Assert.True(vm.HasConfigError);
        Shot(w, "6_bad_weights");
        vm.CustomWeights = "1,1,1,1,1,1,1,1,-1,-1,-1,-1,-1,-1,-1,-1";
        Assert.False(vm.HasConfigError);
        Assert.InRange(vm.Pattern0![Array.IndexOf(Controls.PatternPlot.Angles, 0.0)], -40, -25);  // разностная ДН: провал на нормали

        vm.ModeIndex = (int)Mode.Elements;
        WaitUntil(() => vm.ActiveElement >= 0);
        Shot(w, "7_elements");
        vm.StopCommand.Execute(null);
        w.Close();
    }
}
