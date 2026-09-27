using Avalonia.Controls;
using Avalonia.Input;

namespace Dpaa.App;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        InitializeComponent();
        Map.Clicked += (p, right) => (DataContext as MainViewModel)?.OnMapClicked(p, right);
        KeyDown += (_, e) =>
        {
            if (e.Key == Key.Escape) (DataContext as MainViewModel)?.StopCommand.Execute(null);
        };
        Closing += (_, _) => (DataContext as MainViewModel)?.Shutdown();
    }
}
