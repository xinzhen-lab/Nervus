#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path
import glob
import argparse
from typing import List, Tuple, Union


class Options:
    """
    Class to parse options.
    """
    def __init__(self,  datetime: str = None, isTrain: bool = None) -> None:
        """
            Args:
            datetime (str, optional): date time    Args:
            isTrain (bool, optional): Variable indicating whether training or not. Defaults to None.
        """
        assert isinstance(isTrain, bool), 'isTrain should be bool.'

        self.parser = argparse.ArgumentParser(description='Options for training or test')

        # The blow is common argument both at training and test.
        self.parser.add_argument('--csvpath',   type=str, required=True, help='path to csv for training or test')

        if isTrain:
            # Task
            self.parser.add_argument('--task',  type=str, required=True, choices=['classification', 'regression', 'deepsurv'], help='Task')

            # Model
            self.parser.add_argument('--model', type=str, required=True, help='model: MLP, CNN, ViT, or MLP+(CNN or ViT)')

            # Training and Internal validation
            self.parser.add_argument('--criterion', type=str,  required=True, choices=['CEL', 'MSE', 'RMSE', 'MAE', 'NLL'], help='criterion')
            self.parser.add_argument('--optimizer', type=str,  required=True, choices=['SGD', 'Adadelta', 'RMSprop', 'Adam', 'RAdam'], help='optimzer')
            self.parser.add_argument('--lr',        type=float,               metavar='N', help='learning rate')
            self.parser.add_argument('--epochs',    type=int,  default=10,    metavar='N', help='number of epochs (Default: 10)')

            # Batch size
            self.parser.add_argument('--batch_size',         type=int,  required=True, metavar='N', help='batch size in training')

            # Preprocess for image
            self.parser.add_argument('--augmentation',       type=str,  required=True, choices=['xrayaug', 'trivialaugwide', 'randaug', 'no'], help='kind of augmentation')
            self.parser.add_argument('--normalize_image',    type=str,                 choices=['yes', 'no'], default='yes', help='image nomalization: yes, no (Default: yes)')

            # Sampler
            self.parser.add_argument('--sampler',            type=str,  required=True, choices=['yes', 'no'], help='sample data in traning or not, yes or no')

            # Input channel
            self.parser.add_argument('--in_channel',         type=int,  required=True, choices=[1, 3], help='channel of input image')
            self.parser.add_argument('--vit_image_size',     type=int,  default=0,                     help='input image size for ViT. Set 0 if not used ViT (Default: 0)')

            # Weight saving strategy
            self.parser.add_argument('--save_weight_policy', type=str,  choices=['best', 'each'], default='best', help='Save weight policy: best, or each(ie. save each time loss decreases when multi-label output) (Default: best)')

            # GPU Ids
            self.parser.add_argument('--gpu_ids',            type=str,  default='-1', help='gpu ids: e.g. 0, 0-1-2, 0-2. Use -1 for CPU (Default: -1)')

        else:
            # Directry of weight at traning
            self.parser.add_argument('--weight_dir',         type=str,  default=None, help='directory of weight to be used when test. If None, the latest one is selected')

            # Test bash size
            self.parser.add_argument('--test_batch_size',    type=int,  default=64, metavar='N', help='batch size for test (Default: 64)')

            # Split to be inference
            self.parser.add_argument('--test_splits',        type=str, default='train-val-test', help='splits to be inferred eg. train-val, train-val-test, val-test (Default: train-val-test)')

        self.args = self.parser.parse_args()

        if datetime is not None:
            setattr(self.args, 'datetime', datetime)

        setattr(self.args, 'isTrain', isTrain)

    def _parse_model(self, model_name: str) -> Tuple[Union[str, None], Union[str, None]]:
        """
        Parse model name.

        Args:
            model_name (str): model name (eg. MLP, ResNey18, or MLP+ResNet18)

        Returns:
            Tuple[str, str]: MLP, CNN or Vision Transformer name
            eg. 'MLP', 'ResNet18', 'MLP+ResNet18' ->
                ['MLP'], ['ResNet18'], ['MLP', 'ResNet18']
        """
        _model = model_name.split('+')
        mlp = 'MLP' if 'MLP' in _model else None
        _net = [_n for _n in _model if _n != 'MLP']
        net = _net[0] if _net != [] else None
        return mlp, net

    def _parse_gpu_ids(self, gpu_ids: str) -> List[int]:
        """
        Parse GPU ids concatenated with '-' to list of integers of GPU ids.
        eg. '0-1-2' -> [0, 1, 2], '-1' -> []

        Args:
            gpu_ids (str): GPU Ids

        Returns:
            List[int]: list of GPU ids
        """
        str_ids = gpu_ids.split('-') if gpu_ids != '-1' else ['-1']
        _gpu_ids = []
        for str_id in str_ids:
            id = int(str_id)
            if id >= 0:
                _gpu_ids.append(id)
        return _gpu_ids

    def _parse_test_splits(self, test_splits: str) -> List[str]:
        """
        Parse splits concatenated with '-' to list of strings of splits.

        Args:
            test_splits (str): splits concatenated with '-'

        Returns:
            List[str]: list of strings of splits
        """
        _test_splits = test_splits.split('-')
        return _test_splits

    def _get_latest_weight_dir(self) -> str:
        """
        Return the latest path to directory of weight made at training.

        Returns:
            str: path to directory of the latest weight
            eg. 'materials/results/[csv_name]/sets/2022-09-30-15-56-60/weights'

        Note that:
            parameter.json is in the same directory with the directory of weight.
            If directory of materials is link, Path('.').glob('**/weights' cannot follow below materials.
            Therefore, use glob.glob.
        """
        weight_dirs = glob.glob('**/weights', recursive=True)
        assert (weight_dirs != []), 'No directory of weight.'
        weight_dir = max(weight_dirs, key=lambda weight_dir: Path(weight_dir).stat().st_mtime)
        return str(weight_dir)

    def parse(self) -> None:
        """
        Parse options.
        """
        if self.args.isTrain:
            _mlp, _net = self._parse_model(self.args.model)
            setattr(self.args, 'mlp', _mlp)
            setattr(self.args, 'net', _net)

            _gpu_ids = self._parse_gpu_ids(self.args.gpu_ids)
            setattr(self.args, 'gpu_ids', _gpu_ids)
        else:
            if self.args.weight_dir is None:
                _weight_dir = self._get_latest_weight_dir()
                setattr(self.args, 'weight_dir',  _weight_dir)

            _test_splits = self._parse_test_splits(self.args.test_splits)
            setattr(self.args, 'test_splits', _test_splits)


def check_train_options(datetime_name: str) -> Options:
    """
    Parse options for training.

    Args:
        datetime_name (str): date time

    Returns:
        Options: options
    """
    opt = Options(datetime=datetime_name, isTrain=True)
    opt.parse()
    return opt


def check_test_options() -> Options:
    """
    Parse options for test.

    Returns:
        Options: options
    """
    opt = Options(isTrain=False)
    opt.parse()
    return opt
