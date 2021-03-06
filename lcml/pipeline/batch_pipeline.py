"""This batch pipeline currently assumes a fixed choice of model type, e.g.,
random forest. It performs model selection for the model type using k-fold cross
validation on the training set. Then the winning model is retrained on the full
training set and evaluated on the test set.

See 'Scenario 2 - Train a model and tune (optimize) its hyperparameters' at:
https://sebastianraschka.com/faq/docs/evaluate-a-model.html
"""
from abc import abstractmethod
from datetime import timedelta
import logging
import time

from prettytable import PrettyTable
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

from lcml.pipeline.database.sqlite_db import (classLabelHistogram,
                                              ensureDbTables,
                                              selectFeaturesLabels)
from lcml.pipeline.ml_pipeline_conf import MlPipelineConf
from lcml.pipeline.stage.extract import getFeatureSpace
from lcml.pipeline.stage.model_selection import (ClassificationMetrics,
                                                 ModelSelectionResult)
from lcml.utils.dataset_util import convertClassLabels, reportClassHistogram


logger = logging.getLogger(__name__)


class BatchPipeline:
    def __init__(self, conf: MlPipelineConf):
        self.conf = conf
        self.globalParams = conf.globalParams
        self.dbParams = conf.dbParams
        self.loadStage = conf.loadStage
        self.preprocStage = conf.preprocessStage
        self.extractStage = conf.extractStage
        self.searchStage = conf.searchStage
        self.postprocStage = conf.postprocessStage
        self.serStage = conf.serStage

    def runPipe(self):
        """Runs initial phase of batch machine learning pipeline storing
        intermediate results in a database. Performs following stages:
        1) parse light curves from data source and store to db
        2) preprocess light curves and store cleaned LC's to db
        3) compute features and store to db
        """
        logger.info("___Begin batch ML pipeline___")
        startAll = time.time()

        ensureDbTables(self.dbParams)

        lim = self.globalParams.get("dataLimit", float("inf"))
        if self.loadStage.skip:
            logger.info("Skip dataset loading")
        else:
            logger.info("Loading dataset...")
            self.loadStage.fcn(self.loadStage.params, self.dbParams,
                               self.loadStage.writeTable, lim)

        if self.preprocStage.skip:
            logger.info("Skip dataset cleaning")
        else:
            logger.info("Cleaning dataset...")
            self.preprocStage.fcn(self.preprocStage.params, self.dbParams,
                                  rawTable=self.loadStage.writeTable,
                                  cleanTable=self.preprocStage.writeTable,
                                  limit=lim)

        logger.info("Cleaned dataset class histogram...")
        histogram = classLabelHistogram(self.dbParams)
        reportClassHistogram(histogram)
        if self.extractStage.skip:
            logger.info("Skip extract features")
        else:
            logger.info("Extracting features from LCs...")
            extractStart = time.time()
            self.extractStage.fcn(self.extractStage.params, self.dbParams,
                                  lcTable=self.preprocStage.writeTable,
                                  featuresTable=self.extractStage.writeTable,
                                  limit=lim)
            extractElapsed = timedelta(seconds=time.time() - extractStart)
            logger.info("extracted in: %s", extractElapsed)

        features, labels = selectFeaturesLabels(self.dbParams,
                                                self.extractStage.writeTable,
                                                lim)
        if not features:
            logger.warning("No features returned from db")
            return

        procFeats = self.postprocStage.fcn(features, self.postprocStage.params)

        intLabels, labelMapping = convertClassLabels(labels)
        trainSize = self.globalParams["trainSize"]
        if trainSize == 1:
            XTrain, XTest, yTrain, yTest = procFeats, [], intLabels, []
        else:
            XTrain, XTest, yTrain, yTest = train_test_split(procFeats,
                intLabels, train_size=trainSize, test_size=1 - trainSize)

        logger.info("train size: %s test size: %s", len(XTrain), len(XTest))
        bestRes = self.modelSelectionPhase(XTrain, yTrain, labelMapping)

        bestimator = bestRes.model
        if isinstance(bestimator, RandomForestClassifier):
            # connect feets features names with feature importances
            feats = getFeatureSpace(self.extractStage.params).features_as_array_
            namedImportances = list(zip(feats, bestimator.feature_importances_))
            namedImportances.sort(key=lambda x: x[1], reverse=True)
            t = PrettyTable(["rank", "feature name", "importance"])
            t.align = "l"
            for i, namedImports in enumerate(namedImportances):
                t.add_row([i, namedImports[0],
                           round(namedImports[1], self.globalParams["places"])])
            logger.info("rf feat. importances: \n%s", str(t))

        testMetrics = self.evaluateTestSet(bestRes, XTest, yTest, labelMapping)
        if self.serStage.skip:
            logger.info("Skip serialization")
        else:
            logger.info("Serializing pipeline results")
            self.serStage.fcn(self.conf, labelMapping, bestRes, testMetrics)

        elapsedMins = timedelta(seconds=time.time() - startAll)
        logger.info("Pipeline completed in: %s", elapsedMins)

    @abstractmethod
    def modelSelectionPhase(self, trainFeatures, trainLabels,
                            classLabel) -> ModelSelectionResult:
        """Performs model selection on the training set and returns the selected
        model trained on the full training set"""

    @abstractmethod
    def evaluateTestSet(self, model, featuresTest, labelsTest,
                        classLabels) -> ClassificationMetrics:
        """Evaluates specified model on the held-out test set."""
