using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Input;

namespace Dpaa.App;

public abstract class ViewModelBase : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;

    protected void Raise([CallerMemberName] string? name = null) =>
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));

    protected bool Set<T>(ref T field, T value, [CallerMemberName] string? name = null)
    {
        if (EqualityComparer<T>.Default.Equals(field, value)) return false;
        field = value;
        Raise(name);
        return true;
    }
}

public sealed class RelayCommand : ICommand
{
    readonly Action _run;
    readonly Func<bool>? _can;

    public RelayCommand(Action run, Func<bool>? can = null) => (_run, _can) = (run, can);

    public event EventHandler? CanExecuteChanged;
    public bool CanExecute(object? parameter) => _can?.Invoke() ?? true;
    public void Execute(object? parameter) => _run();
    public void Refresh() => CanExecuteChanged?.Invoke(this, EventArgs.Empty);
}

/// <summary>Переключатель «элемент включён» для амплитудного распределения.</summary>
public sealed class ElementToggle : ViewModelBase
{
    bool _isOn = true;
    readonly Action _changed;

    public ElementToggle(int index, Action changed) => (Index, _changed) = (index, changed);

    public int Index { get; }
    public string Number => (Index + 1).ToString();

    public bool IsOn
    {
        get => _isOn;
        set { if (Set(ref _isOn, value)) _changed(); }
    }
}
