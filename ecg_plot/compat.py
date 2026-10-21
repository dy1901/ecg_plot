"""Historical signatures translated into the shared chart core.

This module contains no drawing, tick, grid, coordinate or export implementation.
Legacy line widths and figure dimensions remain points and inches respectively.
"""
from dataclasses import replace
import warnings
import numpy as np
from .data import normalize, Record, positive
from .chart import ECGChart, Style, STANDARD_LEADS


def _record(ecg, sample_rate, names, order):
    record = normalize(ecg, sample_rate=sample_rate)
    if names is not None:
        names = tuple(str(name) for name in names)
        if len(names) < len(record.names):
            raise ValueError('lead_index must name every input lead')
        record = Record(record.values, record.times, names[:len(record.names)], record.sample_rate)
    if order is None:
        order = list(range(len(record.names)))
    order = np.asarray(order)
    if order.ndim != 1 or not len(order) or order.dtype.kind not in 'iu' or np.any(order < 0) or np.any(order >= len(record.names)):
        raise ValueError('lead_order must contain valid lead indices')
    if len(np.unique(order)) != len(order):
        raise ValueError('lead_order must not repeat leads')
    return Record(record.values[order], record.times, tuple(record.names[i] for i in order), record.sample_rate)


def _figure(chart, width_mm=None, height_mm=None):
    # Create/register a managed pyplot figure so historical plt.show() works,
    # then paint the very same scene into it through the backend adapter.
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError('Legacy figure APIs require ecg_plot[matplotlib]') from exc
    from .renderers import render_matplotlib
    if height_mm is not None:
        # Fit without stretching or mislabelling physical calibration.
        width_mm = min(width_mm, height_mm * chart.width_mm / chart.height_mm)
    scene = chart._render_scene(width_mm)
    fig = plt.figure(figsize=(scene.width_mm*scene.scale/25.4, scene.height_mm*scene.scale/25.4))
    render_matplotlib(scene, figure=fig)
    return fig


def plot_12(ecg, sample_rate=500, title='ECG 12', lead_index=STANDARD_LEADS,
            lead_order=None, columns=2, speed=50, voltage=20, line_width=.6,
            *, layout='row-major', width_mm=None):
    """Legacy signature, accurate shared geometry, editable Figure return.

    row-major retains the historical order; limb-chest groups standard leads.
    width_mm explicitly scales the whole output and its calibration labels.
    """
    record = _record(ecg, sample_rate, lead_index, lead_order)
    chart = ECGChart(record, title=title, layout=layout, columns=columns,
                     speed=speed, gain=voltage,
                     style=Style(line_width=positive(line_width, 'line_width')*25.4/72))
    return _figure(chart, width_mm)


def plot_1(ecg, sample_rate=500, title='ECG', fig_width=15, fig_height=2,
           line_w=.5, ecg_amp=1.8, timetick=.2, *, show_grid=True):
    """Fit shared geometry inside the historical figure-size bounds, in inches."""
    width = positive(fig_width, 'fig_width') * 25.4
    height = positive(fig_height, 'fig_height') * 25.4
    amp = positive(ecg_amp, 'ecg_amp')
    record = normalize(ecg, sample_rate=sample_rate)
    if len(record.names) != 1:
        raise ValueError('plot_1 accepts one signal')
    chart = ECGChart(record, title=title, layout='stacked', amplitude_range=(-amp, amp),
                     style=Style(grid=show_grid, line_width=positive(line_w, 'line_w')*25.4/72,
                                 time_tick=positive(timetick, 'timetick')))
    return _figure(chart, width, height)


def plot(ecg, sample_rate=500, title='ECG 12', lead_index=STANDARD_LEADS,
         lead_order=None, style=None, columns=2, row_height=6,
         show_lead_name=True, show_grid=True, show_separate_line=True):
    record = _record(ecg, sample_rate, lead_index, lead_order)
    visual = Style(line_color='black', major_color='#cccccc', minor_color='#eeeeee') if style == 'bw' else Style()
    visual = replace(visual, grid=show_grid, lead_names=show_lead_name)
    if not show_separate_line:
        warnings.warn('show_separate_line is obsolete: panels have separate viewports.', DeprecationWarning, stacklevel=2)
    # Historical row_height represented twice the per-lead mV range.
    amp = positive(row_height, 'row_height') / 4
    chart = ECGChart(record, title=title, layout='columns', columns=columns,
                     amplitude_range=(-amp, amp), style=visual)
    return _figure(chart)
