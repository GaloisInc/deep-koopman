"""Handle and process input data to DeepKoopman."""


from collections import defaultdict
import torch

from deepk import config as cfg
from deepk import utils


class DataHandler:
    """Handler class for providing data to train (and optionally validate and test) DeepKoopman's neural net.

    ## Parameters
    - **'Xtr'**: Training data. Can be any data type that can be expressed as a 2D structure of *shape=(num_training_samples, num_input_states)*, for example, *numpy.array*, *torch.Tensor*, *list[list]* where all inner lists have same size, etc.

    - **'ttr'**: Training indices. Can be any data type that can be expressed as a 1D structure of *shape=(num_training_samples)*, for example, *numpy.array*, *torch.Tensor*, *list*, *range*, etc. **Must be in ascending order and should ideally be equally spaced**. Small deviations are okay, e.g. `[100, 203, 298, 400, 500]` will become `[100, 200, 300, 400, 500]`, but larger deviations that cannot be unambiguously rounded will lead to errors.

    - **'Xva'** (*optional*): Validation data. Same data type requirements as `Xtr`, *shape=(num_validation_samples, num_input_states)*.

    - **'tva'** (*optional*): Validation indices. Same data type requirements as `ttr`, *shape=(num_validation_samples)*. The order and spacing restrictions on `ttr` do *not* apply. The values of these indices can be anything.
        
    - **'Xte'** (*optional*): Test data. Same data type requirements as `Xtr`, *shape=(num_test_samples, num_input_states)*.

    - **'tte'** (*optional*): Test indices. Same data type requirements as `ttr`, *shape=(num_test_samples)*. The order and spacing restrictions on `ttr` do *not* apply. The values of these indices can be anything.
    """

    def __init__(self, Xtr, ttr, Xva=None, tva=None, Xte=None, tte=None):
        self.Xtr = utils._tensorize(Xtr, dtype=cfg._RTYPE, device=cfg._DEVICE)
        self.Xva = utils._tensorize(Xva, dtype=cfg._RTYPE, device=cfg._DEVICE)
        self.Xte = utils._tensorize(Xte, dtype=cfg._RTYPE, device=cfg._DEVICE)
        self.ttr = utils._tensorize(ttr, dtype=cfg._RTYPE, device=cfg._DEVICE)
        self.tva = utils._tensorize(tva, dtype=cfg._RTYPE, device=cfg._DEVICE)
        self.tte = utils._tensorize(tte, dtype=cfg._RTYPE, device=cfg._DEVICE)

        ## Check sizes
        assert len(self.Xtr) == len(self.ttr), f"Expected 'Xtr' and 'ttr' to have same length of 1st dimension, instead found {len(self.Xtr)} and {len(self.ttr)}"
        assert len(self.Xva) == len(self.tva), f"Expected 'Xva' and 'tva' to have same length of 1st dimension, instead found {len(self.Xva)} and {len(self.tva)}"
        assert len(self.Xte) == len(self.tte), f"Expected 'Xte' and 'tte' to have same length of 1st dimension, instead found {len(self.Xte)} and {len(self.tte)}"

        ## Define Xscale, and normalize X data if applicable
        self.Xscale = torch.max(torch.abs(self.Xtr)).item()
        if cfg.normalize_Xdata:
            self.Xtr = utils._scale(self.Xtr, scale=self.Xscale)
            self.Xva = utils._scale(self.Xva, scale=self.Xscale)
            self.Xte = utils._scale(self.Xte, scale=self.Xscale)

        ## Shift t data to make ttr start from 0 if it doesn't
        self.tshift = self.ttr[0].item()
        self.ttr = utils._shift(self.ttr, shift=self.tshift)
        self.tva = utils._shift(self.tva, shift=self.tshift)
        self.tte = utils._shift(self.tte, shift=self.tshift)

        ## Find differences between ttr values
        self.dts = defaultdict(int) # define this as a class attribute because it will be accessed outside for writing to log file
        for i in range(len(self.ttr)-1):
            self.dts[self.ttr[i+1].item()-self.ttr[i].item()] += 1

        ## Define t scale as most common difference between ttr values, and normalize t data by it
        self.tscale = max(self.dts, key=self.dts.get)
        self.ttr = utils._scale(self.ttr, scale=self.tscale)
        self.tva = utils._scale(self.tva, scale=self.tscale)
        self.tte = utils._scale(self.tte, scale=self.tscale)

        ## Ensure that ttr now goes as [0,1,2,...], i.e. no gaps
        self.ttr = torch.round(self.ttr)
        dts_set = set(self.ttr[i+1].item()-self.ttr[i].item() for i in range(len(self.ttr)-1))
        if dts_set != {1}:
            raise ValueError(f"Training indexes are not equally spaced and cannot be rounded to get equal spacing. Please check 'ttr' = {ttr}")
