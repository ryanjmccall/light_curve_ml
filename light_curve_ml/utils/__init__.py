from __future__ import print_function
import os

from astropy.time import Time
import numpy as np

from light_curve_ml.utils import context


def getDatasetFilePaths(datasetName, ext):
    """Returns the full paths of all dataset files in project data directory:
    ./light_curve_ml/data/
    :param datasetName - Name of specific data whose individual file paths will
    be returned
    :param ext - Required file extension of dataset files
    """
    path = context.joinRoot("data", datasetName)
    return [os.path.join(path, f) for f in os.listdir(path) if f.endswith(ext)]


def toDatetime(time, format="mjd", scale="tt"):
    """Converts time in specified format and scale (e.g, Modified Julian Date
    (MJD) and Terrestrial Time) to datetime."""
    try:
        t = Time(float(time), format=format, scale=scale)
    except ValueError:
        print("Could not create time from: %s" % time)
        return None

    return t.datetime


def reportDataset(dataset, labels=None):
    """Reports the characteristics of a dataset"""
    size = len(dataset)
    dataSizes = [len(x) for x in dataset]
    minSize = min(dataSizes)
    maxSize = max(dataSizes)
    ave = np.average(dataSizes)
    std = float(np.std(dataSizes))
    print("_Dataset Report_")
    print("size: %s \nmin: %s \nave: %.02f (%.02f) \nmax: %s" % (
        size, minSize, ave, std, maxSize))
    if labels:
        print("Unique labels: %s" % sorted(np.unique(labels)))


if __name__ == "__main__":
    print(toDatetime(2015, format="jyear", scale="tcb"))