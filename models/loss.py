#!/usr/bin/env python
# -*- coding: utf-8 -*-

import dataclasses
from typing import List
from pathlib import Path
from abc import ABC, abstractmethod

import torch

import sys

sys.path.append((Path().resolve() / '../').name)
from logger.logger import Logger

logger = Logger.get_logger('models.loss')


@dataclasses.dataclass
class EpochLoss:
    train: List[float] = dataclasses.field(default_factory=list)
    val: List[float] = dataclasses.field(default_factory=list)
    best_val_loss: float = None
    best_epoch: int = None
    update_flag: bool = False

    def append_epoch_loss(self, phase, new_epoch_loss):
        prev_loss_list = getattr(self, phase)
        prev_loss_list.append(new_epoch_loss)

        # ! Below does not work as expected
        # new_epoch_loss = prev_loss_list.append(new_epoch_loss)
        # setattr(self, phase, new_epoch_loss)

    def get_latest_loss(self, phase):
        latest_loss = getattr(self, phase)[-1]
        return latest_loss

    def get_best_val_loss(self):
        return self.best_val_loss

    def set_best_val_loss(self, best_val_loss):
        self.best_val_loss = best_val_loss

    def get_best_epoch(self):
        return self.best_epoch

    def set_best_epoch(self, best_epoch):
        self.best_epoch = best_epoch

    def flag_up(self):
        self.update_flag = True

    def flag_down(self):
        self.update_flag = False

    def is_updated(self):
        return self.update_flag

    def update_best_val_loss_epoch(self, epoch):
        if epoch == 0:
            _best_val_loss = self.get_latest_loss('val')
            self.set_best_val_loss(_best_val_loss)
            self.set_best_epoch(epoch+1)
        else:
            _latest_val_loss = self.get_latest_loss('val')
            _best_val_loss = self.get_best_val_loss()
            if _latest_val_loss < _best_val_loss:
                self.set_best_val_loss(_latest_val_loss)
                self.set_best_epoch(epoch+1)
                self.flag_up()
            else:
                self.flag_down()


class LossRegistory(ABC, EpochLoss):
    """
    raw_loss -> iter_loss -> epoch_loss

    Args:
        ABC (_type_): _description_
        EpochLoss (_type_): _description_
    """
    def __init__(self, internal_label_list):
        self.internal_label_list = internal_label_list

        self.batch_loss = self._init_batch_loss()       # For every batch
        self.running_loss = self._init_running_loss()   # accumlates bacth loss
        self.epoch_loss = self._init_epoch_loss()       # For every epoch

        self.best_val_loss = None
        self.best_epoch = None

    def _init_batch_loss(self):
        _batch_loss = dict()
        for internal_label_name in self.internal_label_list + ['total']:
            _batch_loss[internal_label_name] = None
        return _batch_loss

    def _init_running_loss(self):
        _running_loss = dict()
        for internal_label_name in self.internal_label_list + ['total']:
            _running_loss[internal_label_name] = 0.0
        return _running_loss

    def _init_epoch_loss(self):
        _epoch_loss = dict()
        for internal_label_name in self.internal_label_list + ['total']:
            _epoch_loss[internal_label_name] = EpochLoss()
        return _epoch_loss

    @abstractmethod
    def cal_batch_loss(cls, multi_output, multi_label, period=None, network=None):
        pass

    # batch_loss is accumated in runnning_loss
    def cal_running_loss(self, batch_size):
        for internal_label_name in self.internal_label_list:
            _running_loss = self.running_loss[internal_label_name] + (self.batch_loss[internal_label_name].item() * batch_size)
            self.running_loss[internal_label_name] = _running_loss
            self.running_loss['total'] = self.running_loss['total'] + _running_loss

    def cal_epoch_loss(self, epoch, phase, dataset_size):
        # Update loss list label-wise
        _total = 0.0
        for internal_label_name in self.internal_label_list:
            _new_epoch_loss = self.running_loss[internal_label_name] / dataset_size
            self.epoch_loss[internal_label_name].append_epoch_loss(phase, _new_epoch_loss)
            _total = _total + _new_epoch_loss

        _total = _total / len(self.internal_label_list)
        self.epoch_loss['total'].append_epoch_loss(phase, _total)

        # Updated val_best_loss and best_epoch label-wise when val
        if phase == 'val':
            for internal_label_name in self.internal_label_list + ['total']:
                self.epoch_loss[internal_label_name].update_best_val_loss_epoch(epoch)

        # Initialize
        self.batch_loss = self._init_batch_loss()
        self.running_loss = self._init_running_loss()


class LossMixin:
    def print_epoch_loss(self, num_epochs, epoch):
        _total_epoch_loss = self.epoch_loss['total']

        train_loss = _total_epoch_loss.get_latest_loss('train')
        val_loss = _total_epoch_loss.get_latest_loss('val')
        epoch_comm = f"epoch [{epoch+1:>3}/{num_epochs:<3}]"
        train_comm = f"train_loss: {train_loss:.4f}"
        val_comm = f"val_loss: {val_loss:.4f}"

        updated_commemt = ''
        if _total_epoch_loss.is_updated():
            updated_commemt = '   Updated val_loss!'
        comment = epoch_comm + ', ' + train_comm + ', ' + val_comm + updated_commemt
        logger.info(comment)


class LossWidget(LossRegistory, LossMixin):
    """
    Class for a widget to inherit multiple classes simultaneously
    """
    pass


class ClassificationLoss(LossWidget):
    def __init__(self, criterion, internal_label_list, device):
        super().__init__(internal_label_list)

        self.criterion = criterion
        self.device = device

    def cal_batch_loss(self, multi_output, multi_label):
        for internal_label_name in multi_label.keys():
            _output = multi_output[internal_label_name]
            _label = multi_label[internal_label_name]
            self.batch_loss[internal_label_name] = self.criterion(_output, _label)

        _total = torch.tensor([0.0]).to(self.device)
        for internal_label_name in multi_label.keys():
            _total = torch.add(_total, self.batch_loss[internal_label_name])

        self.batch_loss['total'] = _total


class RegressionLoss(LossWidget):
    def __init__(self, criterion, internal_label_list, device):
        super().__init__(internal_label_list)

        self.criterion = criterion
        self.device = device

    def cal_batch_loss(self, multi_output, multi_label):
        for internal_label_name in multi_label.keys():
            _output = multi_output[internal_label_name].squeeze()
            _label = multi_label[internal_label_name].float()
            self.batch_loss[internal_label_name] = self.criterion(_output, _label)

        _total = torch.tensor([0.0]).to(self.device)
        for internal_label_name in multi_label.keys():
            _total = torch.add(_total, self.batch_loss[internal_label_name])

        self.batch_loss['total'] = _total


"""
class DeepSurvLoss(LossWidget):
    def __init__(self, criterion, internal_label_list, device):
        super().__init__(criterion, internal_label_list, device)

    def cal_batch_loss(self, multi_output, multi_label, period, network):
        internal_label_name = list(multi_label.keys())[0]  # should be unique
        _pred = multi_output[internal_label_name]
        _label = multi_label[internal_label_name].reshape(-1, 1)
        _period = period.reshape(-1, 1)
        self.batch_loss['total'] = self.criterion(_pred, _period, _label, network)  # No need for each label
"""


def create_loss_reg(task, criterion, internal_label_list, device):
    if task == 'classification':
        loss_reg = ClassificationLoss(criterion, internal_label_list, device)
    elif task == 'regression':
        loss_reg = RegressionLoss(criterion, internal_label_list, device)
#     elif task == 'deepsurv':
#        loss_reg = DeepSurvLoss(criterion, internal_label_list, device)
    else:
        logger.error(f"Cannot identify task: {task}.")
    return loss_reg
