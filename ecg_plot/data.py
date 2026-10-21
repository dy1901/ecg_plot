"""Normalize input without importing pandas or changing signal values."""
from dataclasses import dataclass
from collections.abc import Mapping
import numpy as np


@dataclass(frozen=True)
class Record:
    values: np.ndarray  # leads x samples, in mV
    times: np.ndarray  # seconds relative to the original record
    names: tuple
    sample_rate: float | None


def positive(value, name):
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name} must be a positive finite number') from None
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be a positive finite number')
    return value


def normalize(data, sample_rate=None, units='mV', lead_names=None, lead_axis=0):
    """DataFrame columns are leads; ndarray lead_axis defaults to zero.

    A datetime/timedelta index supplies relative times. Without a time index,
    omitted sample_rate retains the historical 500 Hz default.
    """
    if lead_axis not in (0, 1):
        raise ValueError('lead_axis must be 0 or 1')
    is_frame = hasattr(data, 'columns') and hasattr(data, 'to_numpy')
    is_series = not is_frame and hasattr(data, 'index') and hasattr(data, 'to_numpy')
    index = data.index if is_frame or is_series else None
    if is_frame:
        bad = [str(c) for c, dtype in data.dtypes.items() if getattr(dtype, 'kind', '') not in 'iuf']
        if bad:
            raise ValueError('Non-numeric signal columns: ' + ', '.join(bad))
        names = [str(c) for c in data.columns]
        values = data.to_numpy(dtype=float, na_value=np.nan).T
    elif is_series:
        if getattr(data.dtype, 'kind', '') not in 'iuf':
            raise ValueError('Series must contain numeric signal values')
        names = [str(data.name) if data.name is not None else 'CH1']
        try:
            values = data.to_numpy(dtype=float, na_value=np.nan)[None, :]
        except (TypeError, ValueError):
            raise ValueError('Series must contain numeric signal values') from None
    else:
        try:
            raw = np.asarray(data)
            if np.iscomplexobj(raw):
                raise ValueError('Complex signal values are not supported')
            values = np.asarray(data, dtype=float)
        except (TypeError, ValueError):
            raise ValueError('Signals must be a rectangular numeric array') from None
        if values.ndim == 1:
            values = values[None, :]
        elif values.ndim == 2 and lead_axis == 1:
            values = values.T
        names = [f'CH{i + 1}' for i in range(values.shape[0])] if values.ndim == 2 else []
    if values.ndim != 2 or 0 in values.shape:
        raise ValueError('Signals must contain at least one lead and one sample')
    if np.isinf(values).any():
        raise ValueError('Signals contain infinity; use NaN for missing samples')
    if lead_names is not None:
        if isinstance(lead_names, str):
            lead_names = [lead_names]
        names = [str(n) for n in lead_names]
    if len(names) != values.shape[0] or len(set(names)) != len(names):
        raise ValueError('Provide one unique name for each lead')
    factors = {'mv': 1., 'uv': .001, 'μv': .001, 'µv': .001, 'v': 1000.}
    converted = values.copy()
    for i, name in enumerate(names):
        try:
            unit = units[name] if isinstance(units, Mapping) else units
            factor = factors[str(unit).lower()]
        except KeyError:
            raise ValueError(f'Unsupported or missing unit for {name}; use mV, uV or V') from None
        converted[i] *= factor
    if np.isinf(converted).any():
        raise ValueError('Unit conversion overflow')
    fs = positive(sample_rate, 'sample_rate') if sample_rate is not None else None
    kind = getattr(getattr(index, 'dtype', None), 'kind', None)
    if index is not None and kind in ('M', 'm'):
        if index.isna().any():
            raise ValueError('Time index contains missing timestamps')
        times = np.asarray((index - index[0]).total_seconds(), dtype=float)
        if len(times) > 1 and np.any(np.diff(times) <= 0):
            raise ValueError('Time index must be strictly increasing')
        if fs is not None and not np.allclose(times, np.arange(len(times)) / fs, rtol=1e-7, atol=1e-8):
            raise ValueError('sample_rate conflicts with the time index; remove it or reset the index explicitly')
    else:
        fs = 500. if fs is None else fs
        times = np.arange(values.shape[1], dtype=float) / fs
    converted.setflags(write=False)
    times.setflags(write=False)
    return Record(converted, times, tuple(names), fs)
