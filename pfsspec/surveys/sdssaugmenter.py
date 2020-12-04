import numpy as np

from pfsspec.data.regressionaldatasetaugmenter import RegressionalDatasetAugmenter

class SdssAugmenter(RegressionalDatasetAugmenter):
    """Implements data augmentation to train on observed SDSS spectra."""

    def __init__(self, orig=None):
        super(SdssAugmenter, self).__init__(orig=orig)

        if isinstance(orig, SdssAugmenter):
            pass
        else:
            pass

    @classmethod
    def from_dataset(cls, dataset, labels, coeffs, weight=None, partitions=None, batch_size=None, shuffle=None, chunk_size=None, seed=None):
        d = super(SdssAugmenter, cls).from_dataset(dataset, labels, coeffs, weight,
                                            partitions=partitions,
                                            batch_size=batch_size, shuffle=shuffle, 
                                            chunk_size=chunk_size, seed=seed)
        return d

    def add_args(self, parser):
        parser.add_argument('--noise', type=float, default=None, help='Add noise.\n')
        parser.add_argument('--noise-sch', type=str, choices=['constant', 'linear'], default='constant', help='Noise schedule.\n')
        parser.add_argument('--aug-offset', type=float, default=None, help='Augment by adding a random offset.\n')
        parser.add_argument('--aug-scale', type=float, default=None, help='Augment by multiplying with a random number.\n')

    def augment_batch(self, chunk_id, idx):
        flux, labels, weight = super(SdssAugmenter, self).augment_batch(chunk_id, idx)

        mask = np.full(flux.shape, False)
        mask = self.get_data_mask(chunk_id, idx, flux, mask)

        error = self.get_error(chunk_id, idx)
        flux = self.augment_flux(chunk_id, idx, flux)

        flux = self.cut_lowsnr(flux, error)
        flux = self.cut_extreme(flux, error)
        flux = self.apply_mask(flux, error, mask)

        # flux = self.include_wave()

        return flux, labels, weight
