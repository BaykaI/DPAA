using System.Collections.ObjectModel;
using System.Globalization;
using Avalonia;
using Avalonia.Threading;
using Dpaa.Core;

namespace Dpaa.App;

public enum Mode { Beam, Sweep, Focus, TwoBeams, Elements, Listen }

/// <summary>
/// Логика пульта: подключение, сценарии (как у tools/dpaa_ctl.py), живое обновление луча,
/// опрос уровней микрофонов и расчёт диаграммы по тем же кадрам, что уходят в ПЛИС.
/// </summary>
public sealed class MainViewModel : ViewModelBase
{
    public const string SimPort = "Симулятор (без железа)";
    static readonly string[] SourceNames = { "тон", "шум 1.5–4.3 кГц", "ЛЧМ-пачки 2→4 кГц" };

    IDpaaLink? _link;
    readonly SemaphoreSlim _io = new(1, 1);
    readonly DispatcherTimer _tick = new() { Interval = TimeSpan.FromMilliseconds(20) };
    readonly DispatcherTimer _poll = new() { Interval = TimeSpan.FromMilliseconds(300) };
    readonly DateTime _t0 = DateTime.Now;
    bool _dirty, _polling;
    CancellationTokenSource? _elementsCts;

    public MainViewModel()
    {
        Elements = new ObservableCollection<ElementToggle>(
            Enumerable.Range(0, Hw.NElem).Select(i => new ElementToggle(i, Changed)));
        ConnectCommand = new RelayCommand(() => _ = ToggleConnectAsync());
        RefreshPortsCommand = new RelayCommand(RefreshPorts);
        StartCommand = new RelayCommand(() => _ = StartAsync());
        StopCommand = new RelayCommand(() => _ = StopAsync());
        AllOnCommand = new RelayCommand(() => { foreach (var e in Elements) e.IsOn = true; });
        EveryOtherCommand = new RelayCommand(() => { foreach (var e in Elements) e.IsOn = e.Index % 2 == 0; });
        RefreshPorts();
        _tick.Tick += (_, _) => Tick();
        _poll.Tick += (_, _) => _ = PollAsync();
        _tick.Start();
        _poll.Start();
        Recompute();
    }

    // ---------------------------------------------------------------- подключение
    public ObservableCollection<string> Ports { get; } = new();
    string? _selectedPort;
    public string? SelectedPort { get => _selectedPort; set => Set(ref _selectedPort, value); }
    public bool IsConnected => _link is not null;
    public string ConnectText => IsConnected ? "Отключить" : "Подключить";
    string _status = "Не подключено. Выберите порт или симулятор.";
    public string Status { get => _status; set => Set(ref _status, value); }
    string _deviceInfo = "";
    public string DeviceInfo { get => _deviceInfo; set => Set(ref _deviceInfo, value); }

    public RelayCommand ConnectCommand { get; }
    public RelayCommand RefreshPortsCommand { get; }

    void RefreshPorts()
    {
        var keep = SelectedPort;
        Ports.Clear();
        Ports.Add(SimPort);
        try { foreach (var p in SerialLink.PortNames()) Ports.Add(p); }
        catch (Exception e) { Log($"список портов недоступен: {e.Message}"); }
        SelectedPort = keep is not null && Ports.Contains(keep) ? keep : Ports.Count > 1 ? Ports[1] : Ports[0];
    }

    async Task ToggleConnectAsync()
    {
        if (IsConnected)
        {
            await StopAsync();
            _link?.Dispose();
            _link = null;
            Status = "Отключено.";
            DeviceInfo = "";
            RaiseConnection();
            return;
        }
        var port = SelectedPort ?? SimPort;
        try
        {
            IDpaaLink link = port == SimPort ? new SimulatedLink() : new SerialLink(port);
            int id = await Task.Run(() => link.Read(Hw.RegId));
            _link = link;
            RaiseConnection();
            await SendAsync(Scenarios.Mute(), "тишина");
            Status = id == Hw.IdValue
                ? $"Подключено: {link.Name}, прошивка ПЛИС 0x{id:X6} — в порядке."
                : $"Подключено: {link.Name}, но идентификатор 0x{id:X6} (ожидался 0x{Hw.IdValue:X6}).";
            Log(Status);
        }
        catch (Exception e)
        {
            Status = $"Не удалось подключиться к {port}: {e.Message}";
            Log(Status);
        }
    }

    void RaiseConnection()
    {
        Raise(nameof(IsConnected));
        Raise(nameof(ConnectText));
    }

    // ---------------------------------------------------------------- режим и пуск
    int _modeIndex;
    public int ModeIndex
    {
        get => _modeIndex;
        set
        {
            if (!Set(ref _modeIndex, value)) return;
            Raise(nameof(MapHint));
            Raise(nameof(IsReceive));
            Raise(nameof(ShowSource));
            Raise(nameof(ShowToneHint));
            Raise(nameof(ShowDistribution));
            if (IsRunning) _ = StartAsync();          // сразу переключаем сценарий
            Changed();
        }
    }
    public Mode Mode => (Mode)ModeIndex;

    bool _isRunning;
    public bool IsRunning
    {
        get => _isRunning;
        private set { if (Set(ref _isRunning, value)) Raise(nameof(RunState)); }
    }
    public string RunState => IsRunning ? (IsReceive ? "● ПРИЁМ" : "● ИЗЛУЧЕНИЕ") : "тишина";

    public RelayCommand StartCommand { get; }
    public RelayCommand StopCommand { get; }

    async Task StartAsync()
    {
        _elementsCts?.Cancel();
        if (!IsConnected)
        {
            Status = "Сначала подключитесь (можно к симулятору).";
            return;
        }
        List<byte[]> frames;
        try { frames = BuildFrames(start: true); }
        catch (Exception e) { ConfigError = e.Message; return; }
        IsRunning = true;
        Raise(nameof(RunState));
        await SendAsync(frames, ModeTitle);
        if (Mode == Mode.Elements) _ = RunElementsAsync();
    }

    async Task StopAsync()
    {
        _elementsCts?.Cancel();
        IsRunning = false;
        ActiveElement = -1;
        if (IsConnected) await SendAsync(Scenarios.Mute(), "тишина");
    }

    /// <summary>Вызывается при закрытии окна: установка должна замолчать.</summary>
    public void Shutdown()
    {
        _elementsCts?.Cancel();
        _tick.Stop();
        _poll.Stop();
        try { _link?.Send(Scenarios.Mute()); } catch { /* порт уже закрыт */ }
        _link?.Dispose();
        _link = null;
    }

    string ModeTitle => Mode switch
    {
        Mode.Beam => $"луч {Az:+0.#;−0.#;0}°",
        Mode.Sweep => "сканирование",
        Mode.Focus => $"фокус ({FocusX:0.00}; {FocusY:0.00}) м",
        Mode.TwoBeams => $"два луча {Az1:0.#}° и {Az2:0.#}°",
        Mode.Elements => "поэлементный тест",
        _ => $"приём: левое ухо {LeftAz:0.#}°, правое {RightAz:0.#}°",
    };

    // ---------------------------------------------------------------- сигнал
    public string[] Sources => SourceNames;
    int _sourceIndex;
    public int SourceIndex
    {
        get => _sourceIndex;
        set { if (Set(ref _sourceIndex, value)) { Raise(nameof(IsTone)); Raise(nameof(ShowToneHint)); Changed(); } }
    }
    public bool IsTone => SourceIndex == 0;
    /// <summary>Общий выбор сигнала нужен лучу, сканированию и фокусу; у двух лучей и теста — свои тоны.</summary>
    public bool ShowSource => Mode is Mode.Beam or Mode.Sweep or Mode.Focus;
    public bool ShowToneHint => ShowSource && IsTone;
    /// <summary>В поэлементном тесте веса задаются самим тестом.</summary>
    public bool ShowDistribution => Mode != Mode.Elements;
    double _tone = 3000;
    public double ToneHz { get => _tone; set { if (Set(ref _tone, Math.Round(value / 50) * 50)) Changed(); } }
    double _amp = 0.25;
    public double Amp { get => _amp; set { if (Set(ref _amp, Math.Round(value, 2))) Changed(); } }
    public double MaxAmp => Hw.MaxAmp;

    Source MakeSource(int index, double tone) => new((SourceKind)index, tone);
    Source Source => MakeSource(SourceIndex, ToneHz);

    // ---------------------------------------------------------------- параметры сценариев
    double _az;
    public double Az { get => _az; set { if (Set(ref _az, Math.Round(value * 2) / 2)) Changed(); } }

    double _sweepFrom = -60, _sweepTo = 60, _sweepPeriod = 6, _sweepAz;
    public double SweepFrom { get => _sweepFrom; set { if (Set(ref _sweepFrom, Math.Round(value))) Changed(); } }
    public double SweepTo { get => _sweepTo; set { if (Set(ref _sweepTo, Math.Round(value))) Changed(); } }
    public double SweepPeriod { get => _sweepPeriod; set { if (Set(ref _sweepPeriod, Math.Round(value, 1))) Changed(); } }
    public string SweepNow => $"сейчас {_sweepAz:+0;−0;0}°";

    double _fx = 0.3, _fy = 1.0;
    public double FocusX { get => _fx; set { if (Set(ref _fx, Math.Round(value, 2))) Changed(); } }
    public double FocusY { get => _fy; set { if (Set(ref _fy, Math.Round(value, 2))) Changed(); } }

    double _az1 = -35, _az2 = 35, _tone1 = 2500, _tone2 = 3500;
    int _source2 = 2;
    public double Az1 { get => _az1; set { if (Set(ref _az1, Math.Round(value * 2) / 2)) Changed(); } }
    public double Az2 { get => _az2; set { if (Set(ref _az2, Math.Round(value * 2) / 2)) Changed(); } }
    public double Tone1 { get => _tone1; set { if (Set(ref _tone1, Math.Round(value / 50) * 50)) Changed(); } }
    public double Tone2 { get => _tone2; set { if (Set(ref _tone2, Math.Round(value / 50) * 50)) Changed(); } }
    public int Source2Index { get => _source2; set { if (Set(ref _source2, value)) { Raise(nameof(IsTone2)); Changed(); } } }
    public bool IsTone2 => Source2Index == 0;

    double _elemTone = 2000, _dwell = 0.7;
    int _activeElement = -1;
    public double ElemTone { get => _elemTone; set { if (Set(ref _elemTone, Math.Round(value / 50) * 50)) Changed(); } }
    public double Dwell { get => _dwell; set => Set(ref _dwell, Math.Round(value, 1)); }
    public int ActiveElement { get => _activeElement; set { if (Set(ref _activeElement, value)) Raise(nameof(ElementNow)); } }
    public string ElementNow => ActiveElement < 0 ? "" : $"звучит элемент {ActiveElement + 1}";

    double _left = -30, _right = 30;
    public double LeftAz { get => _left; set { if (Set(ref _left, Math.Round(value * 2) / 2)) Changed(); } }
    public double RightAz { get => _right; set { if (Set(ref _right, Math.Round(value * 2) / 2)) Changed(); } }
    public bool IsReceive => Mode == Mode.Listen;

    // ---------------------------------------------------------------- амплитудное распределение
    public string[] Tapers { get; } = { "равномерное", "Тейлор", "Чебышёв", "Ханн" };
    int _taper;
    public int TaperIndex { get => _taper; set { if (Set(ref _taper, value)) { Raise(nameof(HasSll)); Changed(); } } }
    public bool HasSll => TaperIndex is 1 or 2;
    double _sll = 30;
    public double Sll { get => _sll; set { if (Set(ref _sll, Math.Round(value))) Changed(); } }
    public ObservableCollection<ElementToggle> Elements { get; }
    public RelayCommand AllOnCommand { get; }
    public RelayCommand EveryOtherCommand { get; }
    bool _useCustom;
    public bool UseCustom { get => _useCustom; set { if (Set(ref _useCustom, value)) Changed(); } }
    string _custom = "1,1,1,1,1,1,1,1,-1,-1,-1,-1,-1,-1,-1,-1";
    public string CustomWeights { get => _custom; set { if (Set(ref _custom, value)) Changed(); } }

    Distribution BuildDistribution()
    {
        double[]? w = null;
        if (UseCustom)
        {
            var parts = CustomWeights.Split(new[] { ',', ';', ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            w = parts.Select(p => double.Parse(p.Replace(',', '.'), CultureInfo.InvariantCulture)).ToArray();
            if (w.Length != Hw.NElem)
                throw new FormatException($"нужно {Hw.NElem} весов через запятую, введено {w.Length}");
        }
        return new Distribution
        {
            Taper = (Taper)TaperIndex,
            SllDb = Sll,
            Weights = w,
            Off = Elements.Where(e => !e.IsOn).Select(e => e.Index).ToHashSet(),
        };
    }

    // ---------------------------------------------------------------- кадры сценария
    List<byte[]> BuildFrames(bool start)
    {
        var dist = BuildDistribution();
        return Mode switch
        {
            Mode.Beam => Scenarios.Beam(Source, Az, dist, Amp),
            Mode.Sweep => start
                ? Scenarios.SweepSetup(Source, Amp).Concat(Scenarios.SweepStep(_sweepAz, dist)).ToList()
                : Scenarios.SweepStep(_sweepAz, dist),
            Mode.Focus => Scenarios.Focus(Source, FocusX, FocusY, dist, Amp),
            Mode.TwoBeams => Scenarios.TwoBeams(MakeSource(0, Tone1), Az1, MakeSource(Source2Index, Tone2), Az2,
                                                dist, Amp),
            Mode.Elements => Scenarios.ElementsSetup(ElemTone, Amp)
                .Concat(Scenarios.ElementStep(Math.Max(0, ActiveElement))).ToList(),
            _ => Scenarios.Listen(LeftAz, RightAz, dist),
        };
    }

    void Changed()
    {
        _dirty = true;
        Recompute();
    }

    /// <summary>Такт 20 мс: сканирование и отправка изменённых параметров (вызывается таймером).</summary>
    public void Tick()
    {
        if (Mode == Mode.Sweep)
        {
            _sweepAz = Math.Round(Scenarios.SweepAngle((DateTime.Now - _t0).TotalSeconds, SweepFrom, SweepTo,
                                                       Math.Max(1, SweepPeriod)), 1);
            Raise(nameof(SweepNow));
            Recompute();
            if (IsRunning) _ = TrySendAsync(() => BuildFrames(start: false));
            return;
        }
        if (!_dirty || !IsRunning) return;
        if (Mode == Mode.Elements)   // меняется только тон генератора, обход элементов продолжается
            _ = TrySendAsync(() => { _dirty = false; return Scenarios.ElementsSetup(ElemTone, Amp); });
        else
            _ = TrySendAsync(() => { _dirty = false; return BuildFrames(start: false); });
    }

    async Task RunElementsAsync()
    {
        _elementsCts?.Cancel();
        var cts = _elementsCts = new CancellationTokenSource();
        try
        {
            while (!cts.IsCancellationRequested)
                for (int e = 0; e < Hw.NElem && !cts.IsCancellationRequested; e++)
                {
                    ActiveElement = e;
                    Recompute();
                    await SendAsync(Scenarios.ElementStep(e), null);
                    await Task.Delay(TimeSpan.FromSeconds(Math.Max(0.1, Dwell)), cts.Token);
                }
        }
        catch (TaskCanceledException) { }
    }

    // ---------------------------------------------------------------- обмен с ПЛИС
    async Task SendAsync(List<byte[]> frames, string? what)
    {
        if (_link is not { } link) return;
        await _io.WaitAsync();
        try
        {
            await Task.Run(() => link.Send(frames));
            if (what is not null) Log($"→ {what}: {frames.Count} кадров ({frames.Count * Protocol.FrameLen} байт)");
        }
        catch (Exception e) { OnIoError(e); }
        finally { _io.Release(); }
    }

    /// <summary>Частые обновления (движение ползунка, сканирование): если канал занят — пропускаем.</summary>
    async Task TrySendAsync(Func<List<byte[]>> build)
    {
        if (_link is not { } link || !await _io.WaitAsync(0)) return;
        try
        {
            var frames = build();
            await Task.Run(() => link.Send(frames));
        }
        catch (Exception e) when (e is FormatException or InvalidOperationException or ArgumentException)
        {
            ConfigError = e.Message;
        }
        catch (Exception e) { OnIoError(e); }
        finally { _io.Release(); }
    }

    /// <summary>Опрос уровней микрофонов и счётчика кадров (вызывается таймером раз в 0.3 с).</summary>
    public async Task PollAsync()
    {
        if (_link is not { } link || _polling || !await _io.WaitAsync(0)) return;
        _polling = true;
        try
        {
            var (frames, peaks) = await Task.Run(() =>
            {
                var p = new double[Hw.NMics + 1];
                for (int i = 0; i <= Hw.NMics; i++)
                    p[i] = 20 * Math.Log10(Math.Max(link.Read(Hw.RegPeak + i), 1) / (double)(1 << 23));
                return (link.Read(Hw.RegFrames), p);
            });
            Peaks = peaks;
            DeviceInfo = $"кадров I2S: {frames:N0}   зонд: {peaks[Hw.NMics]:0} дБПШ";
        }
        catch (Exception e) { OnIoError(e); }
        finally
        {
            _polling = false;
            _io.Release();
        }
    }

    void OnIoError(Exception e)
    {
        Status = $"Ошибка связи: {e.Message}";
        Log(Status);
    }

    string _configError = "";
    /// <summary>Ошибка в параметрах (например, неверные веса) — показывается красным, кадры не уходят.</summary>
    public string ConfigError
    {
        get => _configError;
        private set { if (Set(ref _configError, value)) Raise(nameof(HasConfigError)); }
    }
    public bool HasConfigError => ConfigError.Length > 0;

    // ---------------------------------------------------------------- картинки
    double[]? _pattern0, _pattern1, _weights, _peaks;
    string _patternCaption = "";
    Point? _focusPoint;
    bool[] _elementsOn = Enumerable.Repeat(true, Hw.NElem).ToArray();
    public double[]? Pattern0 { get => _pattern0; private set => Set(ref _pattern0, value); }
    public double[]? Pattern1 { get => _pattern1; private set => Set(ref _pattern1, value); }
    public string PatternCaption { get => _patternCaption; private set => Set(ref _patternCaption, value); }
    public double[]? Weights { get => _weights; private set => Set(ref _weights, value); }
    public double[]? Peaks { get => _peaks; private set => Set(ref _peaks, value); }
    public Point? FocusPoint { get => _focusPoint; private set => Set(ref _focusPoint, value); }
    public bool[] ElementsOn { get => _elementsOn; private set => Set(ref _elementsOn, value); }

    public string MapHint => Mode switch
    {
        Mode.Beam => "Щелчок по залу — направить луч",
        Mode.Focus => "Щелчок по залу — точка фокуса",
        Mode.TwoBeams => "Левая кнопка — луч 1 (синий), правая — луч 2 (красный)",
        Mode.Listen => "Левая кнопка — левое ухо, правая — правое ухо",
        Mode.Sweep => "Луч качается сам",
        _ => "Элементы звучат по очереди",
    };

    /// <summary>Пересчёт диаграммы и весов по кадрам текущего сценария.</summary>
    void Recompute()
    {
        List<byte[]> frames;
        try { frames = BuildFrames(start: true); }
        catch (Exception e) when (e is FormatException or InvalidOperationException or ArgumentException)
        {
            ConfigError = e.Message;
            return;
        }
        var regs = new RegisterFile();
        regs.Apply(frames);
        var angles = Controls.PatternPlot.Angles;
        var pos = Geometry.ElementPositions();
        double[] Tx(int beam, double f, double? radius = null)
        {
            var (d, g) = regs.TxTable(beam);
            return Pattern.Compute(pos, d, g, f, angles, radius);
        }
        FocusPoint = Mode == Mode.Focus ? new Point(FocusX, FocusY) : null;
        ElementsOn = Elements.Select(e => e.IsOn).ToArray();
        switch (Mode)
        {
            case Mode.TwoBeams:
            {
                var f2 = MakeSource(Source2Index, Tone2).DisplayHz;
                Pattern0 = Tx(0, Tone1);
                Pattern1 = Tx(1, f2);
                PatternCaption = $"Луч 1 на {Tone1:0} Гц, луч 2 на {f2:0} Гц";
                break;
            }
            case Mode.Listen:
            {
                var mics = Geometry.MicPositions();
                var (d0, g0) = regs.RxTable(0);
                var (d1, g1) = regs.RxTable(1);
                Pattern0 = Pattern.Compute(mics, d0, g0, 3000, angles);
                Pattern1 = Pattern.Compute(mics, d1, g1, 3000, angles);
                PatternCaption = "Приём на 3000 Гц: синий — левое ухо, красный — правое";
                break;
            }
            case Mode.Focus:
            {
                double r = Math.Sqrt(FocusX * FocusX + FocusY * FocusY);
                Pattern0 = Tx(0, Source.DisplayHz, r);
                Pattern1 = null;
                PatternCaption = $"На {Source.DisplayHz:0} Гц по окружности радиусом {r:0.00} м";
                break;
            }
            case Mode.Elements:
                Pattern0 = Tx(0, ElemTone);
                Pattern1 = null;
                PatternCaption = $"Один элемент на {ElemTone:0} Гц — излучает во все стороны";
                break;
            default:
                Pattern0 = Tx(0, Source.DisplayHz);
                Pattern1 = null;
                PatternCaption = $"Диаграмма направленности на {Source.DisplayHz:0} Гц";
                break;
        }
        var (_, gains) = Mode == Mode.Listen ? regs.RxTable(0) : regs.TxTable(0);
        double max = gains.Max(Math.Abs);
        Weights = gains.Select((g, i) => ElementsOn[i] ? (max > 0 ? g / max : 0) : double.NaN).ToArray();
        ConfigError = "";
    }

    /// <summary>Щелчок по виду зала сверху.</summary>
    public void OnMapClicked(Point p, bool right)
    {
        double az = Math.Clamp(Math.Atan2(p.X, p.Y) * 180 / Math.PI, -90, 90);
        switch (Mode)
        {
            case Mode.Beam: Az = az; break;
            case Mode.Focus: FocusX = p.X; FocusY = Math.Max(0.15, p.Y); break;
            case Mode.TwoBeams: if (right) Az2 = az; else Az1 = az; break;
            case Mode.Listen: if (right) RightAz = az; else LeftAz = az; break;
        }
    }

    // ---------------------------------------------------------------- журнал
    public ObservableCollection<string> LogLines { get; } = new();

    void Log(string s)
    {
        LogLines.Insert(0, $"{DateTime.Now:HH:mm:ss}  {s}");
        while (LogLines.Count > 200) LogLines.RemoveAt(LogLines.Count - 1);
    }
}
