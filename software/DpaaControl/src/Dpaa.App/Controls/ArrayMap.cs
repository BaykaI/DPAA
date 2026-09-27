using Avalonia;
using Avalonia.Controls;
using Avalonia.Input;
using Avalonia.Media;
using Dpaa.Core;

namespace Dpaa.App.Controls;

/// <summary>
/// Вид зала сверху: решётка, «лепесток» звука (диаграмма в линейном масштабе),
/// направления лучей, точка фокуса и калибровочный зонд. Щелчок задаёт направление или
/// точку: левая кнопка — луч 1 (или левое ухо), правая — луч 2 (правое ухо).
/// </summary>
public sealed class ArrayMap : Control
{
    public static readonly StyledProperty<double[]?> Lobe0Property =
        AvaloniaProperty.Register<ArrayMap, double[]?>(nameof(Lobe0));
    public static readonly StyledProperty<double[]?> Lobe1Property =
        AvaloniaProperty.Register<ArrayMap, double[]?>(nameof(Lobe1));
    public static readonly StyledProperty<Point?> FocusPointProperty =
        AvaloniaProperty.Register<ArrayMap, Point?>(nameof(FocusPoint));
    public static readonly StyledProperty<bool[]?> ElementsOnProperty =
        AvaloniaProperty.Register<ArrayMap, bool[]?>(nameof(ElementsOn));
    public static readonly StyledProperty<int> ActiveElementProperty =
        AvaloniaProperty.Register<ArrayMap, int>(nameof(ActiveElement), -1);
    public static readonly StyledProperty<string?> HintProperty =
        AvaloniaProperty.Register<ArrayMap, string?>(nameof(Hint));
    public static readonly StyledProperty<bool> ReceiveProperty =
        AvaloniaProperty.Register<ArrayMap, bool>(nameof(Receive));

    /// <summary>Щелчок по залу: точка в метрах (x — вправо, y — вперёд) и признак правой кнопки.</summary>
    public event Action<Point, bool>? Clicked;

    const double XMin = -2.0, XMax = 2.0, YMin = -0.35, YMax = 3.1, FloorDb = -30;

    static ArrayMap() => AffectsRender<ArrayMap>(Lobe0Property, Lobe1Property, FocusPointProperty, ElementsOnProperty,
                                                ActiveElementProperty, HintProperty, ReceiveProperty);

    public double[]? Lobe0 { get => GetValue(Lobe0Property); set => SetValue(Lobe0Property, value); }
    public double[]? Lobe1 { get => GetValue(Lobe1Property); set => SetValue(Lobe1Property, value); }
    public Point? FocusPoint { get => GetValue(FocusPointProperty); set => SetValue(FocusPointProperty, value); }
    public bool[]? ElementsOn { get => GetValue(ElementsOnProperty); set => SetValue(ElementsOnProperty, value); }
    public int ActiveElement { get => GetValue(ActiveElementProperty); set => SetValue(ActiveElementProperty, value); }
    public string? Hint { get => GetValue(HintProperty); set => SetValue(HintProperty, value); }
    public bool Receive { get => GetValue(ReceiveProperty); set => SetValue(ReceiveProperty, value); }

    (double Scale, double Ox, double Oy) Transform()
    {
        var b = Bounds;
        double s = Math.Min((b.Width - 20) / (XMax - XMin), (b.Height - 20) / (YMax - YMin));
        double ox = (b.Width - s * (XMax - XMin)) / 2 - s * XMin;
        double oy = (b.Height + s * (YMax - YMin)) / 2 + s * YMin;
        return (s, ox, oy);
    }

    Point ToScreen(double x, double y)
    {
        var (s, ox, oy) = Transform();
        return new Point(ox + s * x, oy - s * y);
    }

    protected override void OnPointerPressed(PointerPressedEventArgs e)
    {
        base.OnPointerPressed(e);
        var p = e.GetPosition(this);
        var (s, ox, oy) = Transform();
        var world = new Point((p.X - ox) / s, (oy - p.Y) / s);
        if (world.Y < 0.05) return;
        Clicked?.Invoke(world, e.GetCurrentPoint(this).Properties.IsRightButtonPressed);
    }

    public override void Render(DrawingContext ctx)
    {
        ctx.FillRectangle(new SolidColorBrush(Color.Parse("#f7f9fc")), new Rect(Bounds.Size));
        var grid = Draw.Pen(Draw.Grid);
        for (double y = 0.5; y <= YMax; y += 0.5)
        {
            ctx.DrawLine(grid, ToScreen(XMin, y), ToScreen(XMax, y));
            Draw.Label(ctx, $"{y:0.#} м", ToScreen(XMax, y) + new Point(-4, -8), 10, align: TextAlignment.Right);
        }
        for (double x = -2; x <= 2.01; x += 0.5)
            ctx.DrawLine(grid, ToScreen(x, 0), ToScreen(x, YMax));
        for (int a = -60; a <= 60; a += 30)
        {
            double t = a * Math.PI / 180;
            ctx.DrawLine(Draw.Pen(Draw.Grid, 1, true), ToScreen(0, 0), ToScreen(3.0 * Math.Sin(t), 3.0 * Math.Cos(t)));
            if (a != 0) Draw.Label(ctx, $"{a}°", ToScreen(2.9 * Math.Sin(t), 2.9 * Math.Cos(t)), 10,
                                   align: TextAlignment.Center);
        }

        void Lobe(double[]? db, IBrush brush)
        {
            if (db is null || db.Length != PatternPlot.Angles.Length) return;
            var pts = new List<Point> { ToScreen(0, 0) };
            for (int i = 0; i < db.Length; i++)
            {
                double r = 2.8 * Math.Pow(10, Math.Max(db[i], FloorDb) / 20);
                double t = PatternPlot.Angles[i] * Math.PI / 180;
                pts.Add(ToScreen(r * Math.Sin(t), r * Math.Cos(t)));
            }
            ctx.DrawGeometry(Draw.WithAlpha(brush, 50), Draw.Pen(brush, 1.6), Draw.Polyline(pts, closed: true));
        }
        Lobe(Lobe1, Draw.Beam1);
        Lobe(Lobe0, Draw.Beam0);

        // зонд на нормали в 2.5 м
        var probe = ToScreen(SimulatedLink.ProbePosition.X, SimulatedLink.ProbePosition.Y);
        ctx.DrawEllipse(Draw.Paper, Draw.Pen(Draw.Muted, 1.5), probe, 6, 6);
        Draw.Label(ctx, "зонд", probe + new Point(10, 0), 10);

        if (FocusPoint is { } f)
        {
            var p = ToScreen(f.X, f.Y);
            ctx.DrawEllipse(null, Draw.Pen(Draw.Beam0, 2), p, 9, 9);
            ctx.DrawLine(Draw.Pen(Draw.Beam0, 2), p - new Point(14, 0), p + new Point(14, 0));
            ctx.DrawLine(Draw.Pen(Draw.Beam0, 2), p - new Point(0, 14), p + new Point(0, 14));
            Draw.Label(ctx, $"фокус ({f.X:0.00}; {f.Y:0.00}) м", p + new Point(14, -14), 11, Draw.Beam0);
        }

        // решётка: 16 элементов по 40 мм (в масштабе)
        var pos = Dpaa.Core.Geometry.ElementPositions();
        var on = ElementsOn;
        for (int i = 0; i < pos.Length; i++)
        {
            var c = ToScreen(pos[i].X, 0);
            var (s, _, _) = Transform();
            double hw = Math.Max(2, s * 0.018);
            IBrush brush = i == ActiveElement ? Draw.Green : on is { } o && i < o.Length && !o[i] ? Draw.Off : Draw.Text;
            ctx.FillRectangle(brush, new Rect(c.X - hw, c.Y - 3, 2 * hw, 12));
        }
        Draw.Label(ctx, Receive ? "решётка (приём)" : "решётка", ToScreen(0.75, -0.18), 11, Draw.Text);
        if (Hint is { } h) Draw.Label(ctx, h, new Point(10, 12), 11, Draw.Muted);
    }
}
