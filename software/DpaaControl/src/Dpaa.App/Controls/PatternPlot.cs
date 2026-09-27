using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;
using Dpaa.Core;

namespace Dpaa.App.Controls;

/// <summary>Диаграмма направленности: уровень, дБ, от угла −90…+90° (до двух лучей).</summary>
public sealed class PatternPlot : Control
{
    public static readonly StyledProperty<double[]?> Data0Property =
        AvaloniaProperty.Register<PatternPlot, double[]?>(nameof(Data0));
    public static readonly StyledProperty<double[]?> Data1Property =
        AvaloniaProperty.Register<PatternPlot, double[]?>(nameof(Data1));
    public static readonly StyledProperty<string?> CaptionProperty =
        AvaloniaProperty.Register<PatternPlot, string?>(nameof(Caption));

    public const double FloorDb = -40;
    public static readonly double[] Angles = Pattern.Angles(0.5);

    static PatternPlot() => AffectsRender<PatternPlot>(Data0Property, Data1Property, CaptionProperty);

    public double[]? Data0 { get => GetValue(Data0Property); set => SetValue(Data0Property, value); }
    public double[]? Data1 { get => GetValue(Data1Property); set => SetValue(Data1Property, value); }
    public string? Caption { get => GetValue(CaptionProperty); set => SetValue(CaptionProperty, value); }

    public override void Render(DrawingContext ctx)
    {
        var b = Bounds;
        ctx.FillRectangle(Draw.Paper, new Rect(b.Size));
        var r = new Rect(44, 26, Math.Max(10, b.Width - 58), Math.Max(10, b.Height - 54));
        double X(double deg) => r.X + (deg + 90) / 180 * r.Width;
        double Y(double db) => r.Y + Math.Min(1, db / FloorDb) * r.Height;

        var grid = Draw.Pen(Draw.Grid);
        for (int a = -90; a <= 90; a += 15)
        {
            ctx.DrawLine(grid, new Point(X(a), r.Top), new Point(X(a), r.Bottom));
            if (a % 30 == 0) Draw.Label(ctx, $"{a}°", new Point(X(a), r.Bottom + 12), 11, align: TextAlignment.Center);
        }
        for (int db = 0; db >= FloorDb; db -= 10)
        {
            ctx.DrawLine(grid, new Point(r.Left, Y(db)), new Point(r.Right, Y(db)));
            Draw.Label(ctx, $"{db}", new Point(r.Left - 6, Y(db)), 11, align: TextAlignment.Right);
        }
        ctx.DrawLine(Draw.Pen(Draw.Axis, 1, true), new Point(r.Left, Y(-13.3)), new Point(r.Right, Y(-13.3)));
        Draw.Label(ctx, "−13 дБ (равномерное)", new Point(r.Right - 4, Y(-13.3) - 8), 10, align: TextAlignment.Right);
        ctx.DrawRectangle(Draw.Pen(Draw.Axis), new Rect(r.TopLeft, r.Size));
        Draw.Label(ctx, "дБ", new Point(r.Left - 6, r.Top - 14), 11, align: TextAlignment.Right);
        Draw.Label(ctx, Caption ?? "", new Point(r.Left, r.Top - 14), 12, Draw.Text, bold: true);

        void Curve(double[]? d, IBrush brush)
        {
            if (d is null || d.Length != Angles.Length) return;
            var pts = new Point[d.Length];
            for (int i = 0; i < d.Length; i++) pts[i] = new Point(X(Angles[i]), Y(d[i]));
            ctx.DrawGeometry(null, Draw.Pen(brush, 2), Draw.Polyline(pts));
        }
        Curve(Data1, Draw.Beam1);
        Curve(Data0, Draw.Beam0);
    }
}
