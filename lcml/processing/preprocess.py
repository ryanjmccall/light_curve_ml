from feets import preprocess
from feets.extractors.core import DATA_TIME, DATA_MAGNITUDE, DATA_ERROR
from lcml.utils.basic_logging import getBasicLogger
from lcml.utils.data_util import SUFFICIENT_LC_DATA, lcFilterBogus
from lcml.utils.format_util import fmtPct


logger = getBasicLogger(__name__, __file__)


#: Additional attribute for light curve Bunch data structure specifying the
#: number of bogus values removed from original data
DATA_BOGUS_REMOVED = "bogusRemoved"


#: Additional attribute for light curve Bunch data structure specifying the
#: number of statistical outliers removed from original data
DATA_OUTLIER_REMOVED = "outlierRemoved"


#: cannot use LC because there is simply not enough data to go on
INSUFFICIENT_DATA_REASON = "insufficient at start"


#: cannot use LC because there is insufficient data after removing bogus values
BOGUS_DATA_REASON = "insufficient due to bogus data"


#: cannot use LC because there is insufficient data after removing statistical
#: outliers
OUTLIERS_REASON = "insufficient due to statistical outliers"


def preprocessLc(timeData, magData, errorData, remove, stdLimit, errorLimit):
    """Returns a cleaned version of an LC. LC may be deemed unfit for use, in
    which case the reason for rejection is specified.

    :returns processed lc as a tuple and failure reason (string)
    """
    removedCounts = {DATA_BOGUS_REMOVED: 0, DATA_OUTLIER_REMOVED: 0}
    if len(timeData) < SUFFICIENT_LC_DATA:
        logger.debug("insufficient: %s to start", len(timeData))
        return None, INSUFFICIENT_DATA_REASON, removedCounts

    # remove bogus data
    tm, mag, err = lcFilterBogus(timeData, magData, errorData, remove=remove)
    removedCounts[DATA_BOGUS_REMOVED] = len(timeData) - len(tm)
    if len(tm) < SUFFICIENT_LC_DATA:
        logger.debug("insufficient: %s after removing bogus values", len(tm))
        return None, BOGUS_DATA_REASON, removedCounts

    # removes statistical outliers
    _tm, _mag, _err = preprocess.remove_noise(tm, mag, err,
                                              error_limit=errorLimit,
                                              std_limit=stdLimit)
    removedCounts[DATA_OUTLIER_REMOVED] = len(tm) - len(_tm)
    if len(_tm) < SUFFICIENT_LC_DATA:
        logger.debug("insufficient: %s after statistical outliers removed",
                     len(_tm))
        return None, OUTLIERS_REASON, removedCounts

    return (_tm, _mag, _err), None, removedCounts


def cleanDataset(lcs, remove, stdLimit=5, errorLimit=3):
    """Clean a list of lc's and report details on discards"""
    cleaned = []
    shortIssueCount = 0
    bogusIssueCount = 0
    outlierIssueCount = 0
    for label, times, mags, errs in lcs:
        lc, issue, _ = preprocessLc(times, mags, errs, remove=remove,
                                    stdLimit=stdLimit, errorLimit=errorLimit)
        if lc:
            cleaned.append((label,) + lc)
        else:
            if issue == INSUFFICIENT_DATA_REASON:
                shortIssueCount += 1
            elif issue == BOGUS_DATA_REASON:
                bogusIssueCount += 1
            elif issue == OUTLIERS_REASON:
                outlierIssueCount += 1
            else:
                raise ValueError("Bad reason: %s" % issue)

    passRate = fmtPct(len(cleaned), len(lcs))
    shortRate = fmtPct(shortIssueCount, len(lcs))
    bogusRate = fmtPct(bogusIssueCount, len(lcs))
    outlierRate = fmtPct(outlierIssueCount, len(lcs))
    logger.info("Dataset size: %d Pass rate: %s", len(lcs), passRate)
    logger.info("Discard rates: short: %s bogus: %s outlier: %s", shortRate,
                bogusRate, outlierRate)
    return cleaned
