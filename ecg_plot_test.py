from scipy.io import loadmat
import ecg_plot

def load_ecg_from_mat(file_path):
    mat = loadmat(file_path)
    data = mat["data"]
    feature = data[0:12]
    return(feature)

if __name__ == '__main__':
    from pathlib import Path
    root = Path(__file__).parent
    test_ecg = load_ecg_from_mat(root / 'example_ecg.mat')
    chart = ecg_plot.plot(test_ecg, sample_rate=500, title='Example ECG')
    output = root / 'tmp'
    output.mkdir(exist_ok=True)
    chart.save(output / 'example_ecg.svg')
