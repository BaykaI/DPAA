using System.Globalization;
using Avalonia;
using Avalonia.Media;

namespace Dpaa.App.Controls;

/// <summary>Общие цвета и мелкие функции рисования (цвета — как на схемах в docs/img).</summary>
static class Draw
{
    public static readonly IBrush Beam0 = new SolidColorBrush(Color.Parse("#1f63b0"));
    public static readonly IBrush Beam1 = new SolidColorBrush(Color.Parse("#c0392b"));
    public static readonly IBrush Green = new SolidColorBrush(Color.Parse("#2e8b57"));
    public static readonly IBrush Grid = new SolidColorBrush(Color.Parse("#e3e7ed"));
    public static readonly IBrush Axis = new SolidColorBrush(Color.Parse("#9aa3b0"));
    public static readonly IBrush Text = new SolidColorBrush(Color.Parse("#1d1d1f"));
    public static readonly IBrush Muted = new SolidColorBrush(Color.Parse("#5b6270"));
    public static readonly IBrush Off = new SolidColorBrush(Color.Parse("#c5cad3"));
    public static readonly IBrush Paper = Brushes.White;

    public static IBrush BeamBrush(int i) => i == 0 ? Beam0 : Beam1;

    public static IBrush WithAlpha(IBrush b, byte a) =>
        new SolidColorBrush(Color.FromArgb(a, ((ISolidColorBrush)b).Color.R, ((ISolidColorBrush)b).Color.G,
            ((ISolidColorBrush)b).Color.B));

    public static Pen Pen(IBrush b, double w = 1, bool dashed = false) =>
        new(b, w, dashed ? new DashStyle(new double[] { 4, 3 }, 0) : null);

    public static void Label(DrawingContext ctx, string s, Point p, double size = 11, IBrush? brush = null,
                             TextAlignment align = TextAlignment.Left, bool bold = false, bool vcenter = true)
    {
        var ft = new FormattedText(s, CultureInfo.CurrentCulture, FlowDirection.LeftToRight,
            new Typeface(FontFamily.Default, FontStyle.Normal, bold ? FontWeight.SemiBold : FontWeight.Normal),
            size, brush ?? Muted);
        double x = align switch
        {
            TextAlignment.Center => p.X - ft.Width / 2,
            TextAlignment.Right => p.X - ft.Width,
            _ => p.X,
        };
        ctx.DrawText(ft, new Point(x, vcenter ? p.Y - ft.Height / 2 : p.Y));
    }

    public static StreamGeometry Polyline(IReadOnlyList<Point> pts, bool closed = false)
    {
        var g = new StreamGeometry();
        using var c = g.Open();
        if (pts.Count == 0) return g;
        c.BeginFigure(pts[0], closed);
        for (int i = 1; i < pts.Count; i++) c.LineTo(pts[i]);
        c.EndFigure(closed);
        return g;
    }
}
