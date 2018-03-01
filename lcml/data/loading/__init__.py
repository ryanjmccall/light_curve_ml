"""These functions are duck-typed for input: dataDir: str, limit: int and
outputs: labels: List[str], times: List[ndarray], magnitudes: List[ndarray],
errors: List[ndarray]"""
import csv

import numpy as np

from lcml.utils.basic_logging import BasicLogging
from lcml.utils.context_util import absoluteFilePaths, joinRoot


logger = BasicLogging.getLogger(__name__)


# TODO move to another module
def fileLength(fname):
    i = -1
    with open(fname) as f:
        for i, l in enumerate(f):
            pass
    return i + 1


def assertArrayLengths(a, b):
    assert len(a) == len(b), "unequal lengths: %s & %s" % (len(a), len(b))


# TODO try more memory efficient impl
# stackoverflow.com/questions/8956832/python-out-of-memory-on-large-csv-file-numpy
def iterLoadTxt(filename, delimiter=',', skiprows=0, dtype=float):
    def iter_func():
        with open(filename, 'r') as f:
            for _ in range(skiprows):
                next(f)

            line = None
            for line in f:
                line = line.rstrip().split(delimiter)
                for item in line:
                    yield dtype(item)
        iterLoadTxt.rowlength = len(line) if line else -1

    data = np.fromiter(iter_func(), dtype=dtype)
    data = data.reshape((-1, iterLoadTxt.rowlength))
    return data


def _ogle3Uid(r):
    # each ogle3 LC is uniquely defined by the combo of 'field', 'category',
    # 'id', & 'band'
    return "%s_%s_%s_%s" % (r[3].lower(), r[4].lower(), int(r[5]), r[6].lower())


def loadOgle3Dataset(dataDir, limit):
    """Loads OGLE3 data from specified file as light curves
    represented as lists of the following values: labels, times,
    magnitudes, and magnitude errors."""
    # end results
    labels = list()
    times = list()
    magnitudes = list()
    errors = list()
    fullPath = joinRoot(dataDir)

    # 0=HJD, 1=MAGNITUDE, 2=ERROR, 3=FIELD, 4=LABEL, 5=ID, 6=MAGNITUDE_BAND
    data = np.loadtxt(fullPath, skiprows=1, dtype=str, delimiter=",")

    # Light curves uniquely ID'd by field, label, id, band
    uidCol = [_ogle3Uid(r) for r in data]
    uids = np.unique(uidCol)
    selectedUids = set(np.random.choice(uids, limit, replace=False))
    curLabel = data[0, 4].lower()
    curUid = uidCol[0]
    curTimes = []
    curMags = []
    curErrors = []
    for i, row in enumerate(data):
        if uidCol[i] == curUid:
            # continue building current LC
            if curUid in selectedUids:
                curTimes.append(float(row[0]))
                curMags.append(float(row[1]))
                curErrors.append(float(row[2]))
        else:
            # finish current LC
            if curUid in selectedUids:
                labels.append(curLabel)
                times.append(curTimes)
                magnitudes.append(curMags)
                errors.append(curErrors)

            # now start new LC from 'row'
            curUid = uidCol[i]
            if curUid in selectedUids:
                # don't have to recreate these until lc is selected
                curLabel = row[4].lower()
                curTimes = [float(row[0])]
                curMags = [float(row[1])]
                curErrors = [float(row[2])]

    return labels, times, magnitudes, errors


def legacyLoadOgle3Dataset(dataDir, limit):
    """Loads all OGLE3 data files from specified directory as light curves
    represented as lists of the following values: classLabels, times,
    magnitudes, and magnitude errors. Class labels are parsed from originating
    data file name."""
    labels = list()
    times = list()
    magnitudes = list()
    errors = list()

    paths = absoluteFilePaths(dataDir, ext="dat")
    if not paths:
        raise ValueError("No data files found in %s with ext dat" % dataDir)

    # Make a random choice of files up to limit
    selectedIdxs = np.random.choice(len(paths), limit, replace=False)
    paths = [paths[i] for i in selectedIdxs]

    for i, f in enumerate(paths):
        fileName = f.split("/")[-1]
        fnSplits = fileName.split("-")
        if len(fnSplits) > 2:
            category = fnSplits[2].lower()
        else:
            logger.warning("file name lacks category! %s", fileName)
            continue

        lc = np.loadtxt(f)
        if lc.ndim == 1:
            lc.shape = 1, 3

        labels.append(category)
        times.append(lc[:, 0])
        magnitudes.append(lc[:, 1])
        errors.append(lc[:, 2])

    assertArrayLengths(labels, times)
    assertArrayLengths(labels, magnitudes)
    assertArrayLengths(labels, errors)
    return labels, times, magnitudes, errors


def loadMachoDataset(dataPath, limit):
    """Loads MACHO data having red and blue light curve bands. The different
    bands are simply treated as different light curves. The returned arrays
    have the red band in the first half and the blue band in the second.

    CSV file columns:
    0 - classification
    1 - field_id
    2 - tile_id
    3 - sequence
    4 - date_observed
    5 - red_magnitude
    6 - red_error
    7 - blue_magnitude
    8 - blue_error
    """
    # TODO follwo ogle3 route
    # data = np.loadtxt(fullPath, skiprows=1, dtype=str, delimiter=",")
    #
    # # Light curves uniquely ID'd by field, label, id, band
    # uidCol = [_ogle3Uid(r) for r in data]
    # uids = np.unique(uidCol)
    # selectedUids = set(np.random.choice(uids, limit, replace=False))

    # FIXME file contains multiple light curves together, so have a
    # while loop tracking current lc and detecting when it changes and producing
    # two light curve objects for the two bands each loop
    # can still have 'choice' just skip over entire lc if current number is
    # not in choice -- requires knowing number of light curves a priori, or
    # computing them in an initial pass
    choice = set(np.random.choice(fileLength(dataPath), limit, replace=False))
    data = list()
    columns = {0,4,5,6,7,8}
    skiprows = 1
    with open(dataPath, "r") as f:
        reader = csv.reader(f, delimiter=",")
        for _ in range(skiprows):
            next(f)

        for i, row in enumerate(reader):
            if i in choice:
                data.append([np.float32(x)
                             for i, x in enumerate(row)
                             if i in columns])

    # data = np.loadtxt(dataPath, delimiter=",", skiprows=1,
    #                   usecols=(0,4,5,6,7,8), dtype=np.float32)
    # data = data[choice]

    # double labels and times since we have two bands
    labels = np.tile([r[0] for r in data], 2)
    times = np.tile([r[1] for r in data], 2)
    assertArrayLengths(labels, times)

    magnitudes = [r[2] for r in data] + [r[3] for r in data]
    assertArrayLengths(times, magnitudes)

    errors = [r[4] for r in data] + [r[5] for r in data]
    assertArrayLengths(times, errors)
    return labels, times, magnitudes, errors


def loadK2Dataset(dataPath, limit):
    """Parses Light curves from LSST csv K2 data. Ignore data having
    nonzero SAP_QUALITY.

    Col 0 - TIME [64-bit floating point] - The time at the mid-point of the
    cadence in BKJD. Kepler Barycentric Julian Day (BKJD) is Julian day minus
    2454833.0 (UTC=January 1, 2009 12:00:00) and corrected to be the arrival
    times at the barycenter of the Solar System.

    Col 7 - PDCSAP_FLUX [32-bit floating point] - The flux contained in the
    optimal aperture in electrons per second after the PDC module has applied
    its cotrending algorithm to the PA light curve. To better understand how
    PDC manipulated the light curve, read Section 2.3.1.2 and see the PDCSAPFL
    keyword in the header.

    Col 8 - PDCSAP_FLUX_ERR [32-bit floating point] - The 1-sigma error in PDC
    flux values.

    Col 9 - SAP_QUALITY [32-bit integer] - Flags containing information about
    the quality of the data. Table 2-3 explains the meaning of each active bit.
    See the Data Characteristics Handbook and Data Release Notes for more
    details on safe modes, coarse point, argabrightenings, attitude tweaks, etc.
    Unused bits are reserved for future use.

    :param dataPath: full path to source file(s)
    :param limit: restriction number of light curves returned
    :return:
    """
    # TODO can we obtain labels for k2?
    labels = list()
    data = np.genfromtxt(dataPath, delimiter=",", dtype=float, skip_header=1)
    flags = data[:, 9]

    # only select data where SAP quality flags are 0
    goodRows = np.where(flags == 0)[0]
    goodRows = goodRows[np.random.choice(len(goodRows), limit, replace=False)]

    times = data[goodRows, 0]
    magnitudes = data[goodRows, 7]
    errors = data[goodRows, 8]

    return labels, times, magnitudes, errors


if __name__ == "__main__":
    _path = "/Users/ryanjmccall/code/light_curve_ml/data/k2/k2-sample.csv"
    _limit = 10
    _data = loadK2Dataset(_path, _limit)
    print(len(_data[1]))