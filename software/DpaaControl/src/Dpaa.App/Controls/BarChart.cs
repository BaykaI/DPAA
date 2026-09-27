using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;

namespace Dpaa.App.Controls;

/// <summary>
/// Столбики по элементам: веса амплитудного распределения (−1…1) или уровни микрофонов (дБПШ).
/// </summary>
public sealed class BarChart : Control
{
    public static readonly StyledProperty<double[]?> ValuesProperty =
        AvaloniaProperty.Register<BarChart, double[]?>(nameof(Values));
    public static readonly StyledProperty<double> MinimumProperty =
        AvaloniaProperty.Register<BarChart, double>(nameof(Minimum), -1);
    public static readonly StyledProperty<double> MaximumProperty =
        AvaloniaProperty.Register<BarChart, double>(nameof(Maximum), 1);
    public static readonly StyledProperty<int> HighlightProperty =
        AvaloniaProperty.Register<BarChart, int>(nameof(Highlight), -1);
    public static readonly StyledProperty<string?> CaptionProperty =
        AvaloniaProperty.Register<BarChart, string?>(nameof(Caption));
    public static readonly StyledProperty<double> BaselineProperty =
        AvaloniaProperty.Register<BarChart, double>(nameof(Baseline));
    public static readonly StyledProperty<string?> LastLabelProperty =
        AvaloniaProperty.Register<BarChart, string?>(nameof(LastLabel));

    static BarChart() => AffectsRender<BarChart>(ValuesProperty, HighlightProperty, CaptionProperty,
                                                 MinimumProperty, MaximumProperty, LastLabelProperty,
                                                 BaselineProperty);

    public double[]? Values { get => GetValue(ValuesProperty); set => SetValue(ValuesProperty, value); }
    public double Minimum { get => GetValue(MinimumProperty); set => SetValue(MinimumProperty, value); }
    public double Maximum { get => GetValue(MaximumProperty); set => SetValue(MaximumProperty, value); }
    public int Highlight { get => GetValue(HighlightProperty); set => SetValue(HighlightProperty, value); }
    public string? Caption { get => GetValue(CaptionProperty); set => SetValue(CaptionProperty, value); }
    /// <summary>От какого значения растут столбики: 0 для весов, нижняя граница шкалы для уровней.</summary>
    public double Baseline { get => GetValue(BaselineProperty); set => SetValue(BaselineProperty, value); }
    /// <summary>Подпись последнего столбика вместо номера (например, «зонд»).</summary>
    public string? LastLabel { get => GetValue(LastLabelProperty); set => SetValue(LastLabelProperty, value); }

    public override void Render(DrawingContext ctx)
    {
        var b = Bounds;
        ctx.FillRectangle(Draw.Paper, new Rect(b.Size));
        var v = Values;
        Draw.Label(ctx, Caption ?? "", new Point(8, 10), 12, Draw.Text, bold: true);
        if (v is null || v.Length == 0) return;
        var r = new Rect(34, 24, Math.Max(10, b.Width - 42), Math.Max(10, b.Height - 42));
        double lo = Minimum, hi = Maximum;
        double Y(double x) => r.Bottom - (Math.Clamp(x, lo, hi) - lo) / (hi - lo) * r.Height;
        double zero = Y(Math.Clamp(Baseline, lo, hi));
        var grid = Draw.Pen(Draw.Grid);
        foreach (var t in new[] { lo, (lo + hi) / 2, hi })
        {
            ctx.DrawLine(grid, new Point(r.Left, Y(t)), new Point(r.Right, Y(t)));
            Draw.Label(ctx, $"{t:0.#}", new Point(r.Left - 4, Y(t)), 10, align: TextAlignment.Right);
        }
        double w = r.Width / v.Length;
        for (int i = 0; i < v.Length; i++)
        {
            double y = Y(v[i]);
            IBrush brush = i == Highlight ? Draw.Green : v[i] < 0 ? Draw.Beam1 : Draw.Beam0;
            if (double.IsNaN(v[i])) brush = Draw.Off;
            var bar = new Rect(r.Left + i * w + w * 0.15, Math.Min(y, zero), w * 0.7, Math.Max(1, Math.Abs(zero - y)));
            ctx.FillRectangle(brush, bar);
            string lab = i == v.Length - 1 && LastLabel is { } l ? l : $"{i + 1}";
            Draw.Label(ctx, lab, new Point(r.Left + (i + 0.5) * w, r.Bottom + 9), 10, align: TextAlignment.Center);
        }
        ctx.DrawLine(Draw.Pen(Draw.Axis), new Point(r.Left, zero), new Point(r.Right, zero));
    }
}
