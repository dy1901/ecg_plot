# ECG plot

![example 12 lead plot](https://github.com/dy1901/ecg_plot/raw/master/example_ecg.png)

## Plot standard ECG chart from data.
* Support both direct plotting and plotting SVG preview in browser (currently only works on mac)
* Support saving PNG and SVG to disk
* Support customer defined lead order
* Support customer defined column count

## Install
```
pip install ecg_plot
```

## Notice
* Input data should be m x n matrix, which m is lead count of ECG and n is length of single lead signal.
* Default sample rate is 500 Hz.

## Example


#### Plot 12 lead ECG


params:

|parameter|description|
| --- | --- |
|ecg        | m x n ECG signal data, which m is number of leads and n is length of signal. |
|sample_rate| Sample rate of the signal. |
|title      | Title which will be shown on top off chart
|lead_index | Lead name array in the same order of ecg, will be shown on left of signal plot, defaults to ['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6'] |
|lead_order | Lead display order |
|columns    | display columns, defaults to 2 |
|style      | display style, defaults to None, can be 'bw' which means black white |
|row_height |   how many grid should a lead signal have |
|show_lead_name | show lead name |
|show_grid      | show grid |
|show_separate_line  | show separate line |


```
import ecg_plot

ecg = load_data() # load data should be implemented by yourself 
ecg_plot.plot(ecg, sample_rate = 500, title = 'ECG 12')
ecg_plot.show()

```

#### Plot single lead ECG

```
import ecg_plot

ecg = load_data() # load data should be implemented by yourself 
ecg_plot.plot_1(ecg[1], sample_rate=500, title = 'ECG')
ecg_plot.show()
```

#### Save result as png

```
import ecg_plot

ecg = load_data() # load data should be implemented by yourself 
ecg_plot.plot_12(ecg, sample_rate = 500, title = 'ECG 12')
ecg_plot.save_as_png('example_ecg','tmp/')

```

### License: MIT