import logging

import os

import numpy as np

import theano

from blocks.algorithms import (Adam, CompositeRule, GradientDescent,
                               Momentum, RMSProp, StepClipping,
                               RemoveNotFinite)
from blocks.extensions import Printing, ProgressBar
from blocks.extensions.monitoring import (
    TrainingDataMonitoring, DataStreamMonitoring)
from blocks.extensions.saveload import Load
from blocks.graph import ComputationGraph
from blocks.main_loop import MainLoop
from blocks.model import Model
from extensions import EarlyStopping, ResetStates


floatX = theano.config.floatX
logging.basicConfig(level='INFO')
logger = logging.getLogger(__name__)


def learning_algorithm(args):
    name = args.algorithm
    learning_rate = float(args.learning_rate)
    momentum = args.momentum
    clipping_threshold = args.clipping
    if name == 'adam':
        clipping = StepClipping(threshold=np.cast[floatX](clipping_threshold))
        adam = Adam(learning_rate=learning_rate)
        step_rule = CompositeRule([adam, clipping])
    elif name == 'rms_prop':
        clipping = StepClipping(threshold=np.cast[floatX](clipping_threshold))
        rms_prop = RMSProp(learning_rate=learning_rate)
        rm_non_finite = RemoveNotFinite()
        step_rule = CompositeRule([clipping, rms_prop, rm_non_finite])
    else:
        clipping = StepClipping(threshold=np.cast[floatX](clipping_threshold))
        sgd_momentum = Momentum(learning_rate=learning_rate, momentum=momentum)
        rm_non_finite = RemoveNotFinite()
        step_rule = CompositeRule([clipping, sgd_momentum, rm_non_finite])
    return step_rule


def train_model(cost, cross_entropy, train_stream, valid_stream,
                updates, args):

    # Define the model
    model = Model(cost)

    step_rule = learning_algorithm(args)
    cg = ComputationGraph(cost)
    logger.info(cg.parameters)

    algorithm = GradientDescent(cost=cost, step_rule=step_rule,
                                params=cg.parameters)
    algorithm.add_updates(updates)

    # extensions to be added
    extensions = []
    # Creating 'best' folder for saving the best model.
    if not os.path.exists(args.save_path):
        os.makedirs(args.save_path)
    best_path = os.path.join(args.save_path, 'best')
    early_stopping = EarlyStopping('valid_cross_entropy',
                                   args.patience, best_path,
                                   every_n_batches=args.monitoring_freq)
    extensions.append(early_stopping)
    if args.load_path is not None:
        extensions.append(Load(args.load_path, load_iteration_states=True))
    extensions.extend([
        TrainingDataMonitoring([cost], prefix='train'),
        DataStreamMonitoring([cost, cross_entropy],
                             valid_stream, prefix='valid',
                             every_n_batches=args.monitoring_freq),
        ResetStates([v for v, _ in updates], every_n_batches=100),
        Printing(every_n_batches=args.monitoring_freq),
        ProgressBar()])

    main_loop = MainLoop(
        model=model,
        data_stream=train_stream,
        algorithm=algorithm,
        extensions=extensions
    )
    main_loop.run()
