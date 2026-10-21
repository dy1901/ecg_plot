"""Public interface and lazy compatibility with historical Matplotlib calls."""
from contextvars import ContextVar
from pathlib import Path
import warnings
import numpy as np
from .chart import ECGChart, Style
from .data import normalize

_current = ContextVar('ecg_current_chart', default=None)


def plot(data, *args, sample_rate=None, units='mV', lead_names=None,
         lead_axis=0, title=None, layout='columns', columns=2,
         speed=25, gain=10, window=None, rhythm_lead=None,
         seconds_per_row=10, time_mode='simultaneous', style=None,
         row_height=None, amplitude_range=None, **legacy_options):
    """Create an SVG-first chart. See README for input and compatibility rules.

    Legacy positional calls and legacy-only keywords use argument adapters
    and render the shared scene as a managed Matplotlib figure. New calls always return ECGChart.
    """
    old_keys = {'lead_index', 'lead_order', 'show_lead_name', 'show_grid', 'show_separate_line'}
    unknown = set(legacy_options) - old_keys
    if unknown:
        raise TypeError('Unexpected options: ' + ', '.join(sorted(unknown)))
    if args or legacy_options:
        if amplitude_range is not None:
            raise TypeError('amplitude_range requires the new chart interface')
        if isinstance(style, Style):
            raise TypeError('Style objects require the new chart interface; remove legacy arguments')
        if any((units != 'mV', lead_names is not None, lead_axis != 0, layout != 'columns', speed != 25, gain != 10, window is not None, rhythm_lead is not None, seconds_per_row != 10, time_mode != 'simultaneous')):
            raise TypeError('Do not mix legacy arguments with the new chart options')
        warnings.warn('Legacy plot arguments use Matplotlib; use named leads and Style with the new interface.', DeprecationWarning, stacklevel=2)
        kwargs = dict(legacy_options)
        # Preserve positional bindings without sending duplicate arguments.
        names = ['sample_rate', 'title', 'lead_index', 'lead_order', 'style', 'columns', 'row_height', 'show_lead_name', 'show_grid', 'show_separate_line']
        if len(args) > len(names):
            raise TypeError('Too many positional arguments')
        explicit = {'sample_rate': sample_rate, 'title': title, 'style': style, 'columns': columns, 'row_height': row_height}
        for name, value in explicit.items():
            if name not in names[:len(args)] and value is not None:
                kwargs[name] = value
        fig = _legacy().plot(np.asarray(data), *args, **kwargs)
        _current.set(fig)
        return fig
    record = normalize(data, sample_rate, units, lead_names, lead_axis)
    chart = ECGChart(record, title=title, layout=layout, columns=columns,
                     speed=speed, gain=gain, window=window, rhythm_lead=rhythm_lead,
                     seconds_per_row=seconds_per_row, time_mode=time_mode,
                     style=style, row_height=row_height, amplitude_range=amplitude_range)
    _current.set(chart)
    return chart


def _legacy():
    try:
        from . import compat
    except ImportError as exc:
        raise ImportError('Legacy plotting requires ecg_plot[matplotlib]') from exc
    return compat


def plot_1(*args, **kwargs):
    fig = _legacy().plot_1(*args, **kwargs)
    _current.set(fig)
    return fig


def plot_12(*args, **kwargs):
    fig = _legacy().plot_12(*args, **kwargs)
    _current.set(fig)
    return fig


def _save(file_name, path, extension, *, dpi=100, layout=None, figure=None):
    target = _current.get() if figure is None else figure
    if target is None:
        raise RuntimeError('Create an ECG chart before saving')
    output = Path(path) / (str(file_name) + extension)
    if isinstance(target, ECGChart):
        return target.save(output, dpi=dpi)
    target.savefig(output, dpi=dpi, bbox_inches=layout)
    return output


def save_as_png(file_name, path='./', dpi=100, layout='tight'):
    return _save(file_name, path, '.png', dpi=dpi, layout=layout)


def save_as_svg(file_name, path='./'):
    return _save(file_name, path, '.svg')


def save_as_jpg(file_name, path='./'):
    return _save(file_name, path, '.jpg')


def save_as_pdf(file_name, path='./'):
    return _save(file_name, path, '.pdf')


def show():
    chart = _current.get()
    if isinstance(chart, ECGChart):
        return chart.show()
    import matplotlib.pyplot as plt
    return plt.show()


def show_svg(tmp_path='./'):
    import tempfile
    import webbrowser
    with tempfile.NamedTemporaryFile(dir=tmp_path, suffix='.svg', prefix='ecg-', delete=False) as f:
        path = Path(f.name)
    _save(path.stem, path.parent, '.svg')
    webbrowser.open(path.resolve().as_uri())
    return path
