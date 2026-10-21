"""Regenerate README figures: python -m examples.render_readme.

Requires pandas and export extras. ecg.csv is a CSV copy of the repository's
example_ecg.mat (first twelve channels, original order), sampled at 500 Hz.
Annotation labels below illustrate the API; they are not clinical annotations.
"""
from pathlib import Path
import pandas as pd
import ecg_plot


def main():
    root = Path(__file__).resolve().parents[1]
    df = pd.read_csv(root / 'examples' / 'ecg.csv')
    output = root / 'docs' / 'images'
    output.mkdir(parents=True, exist_ok=True)

    report = ecg_plot.plot(
        df, sample_rate=500, units='mV', title='12-lead ECG',
        layout='12lead', time_mode='sequential', rhythm_lead='II', window=(0, 10),
    )
    stacked = ecg_plot.plot(
        df[['I', 'II']], sample_rate=500, units='mV',
        layout='stacked', window=(0, 5), title='Two leads from a DataFrame',
    )
    annotated = ecg_plot.plot(
        df['II'], sample_rate=500, units='mV', window=(2, 4),
        title='Point and interval annotations',
    )
    annotated.add_annotations([
        {'sample': 1250, 'lead': 'II', 'label': 'Example event'},
        {'time': 2.7, 'end_time': 3.2, 'label': 'Review window'},
    ])
    for name, chart in [('12lead', report), ('pandas-stacked', stacked), ('annotations', annotated)]:
        chart.save(output / f'{name}.svg')
        chart.save(output / f'{name}.png', dpi=110)


if __name__ == '__main__':
    main()
