import numpy as np
import pysynphot
import pysynphot.binning
import pysynphot.spectrum
import pysynphot.reddening
from scipy.integrate import simps

from pfsspec.stellar import ModelSpectrum

class PhoenixSpectrum(ModelSpectrum):
    def __init__(self, orig=None):
        super(PhoenixSpectrum, self).__init__(orig=orig)

        if not isinstance(orig, PhoenixSpectrum):
            self.M_H = np.nan
            self.M_H_err = np.nan
            self.a_M = np.nan
            self.a_M_err = np.nan
        else:
            self.M_H = orig.M_H
            self.M_H_err = orig.M_H_err
            self.a_M = orig.a_M
            self.a_M_err = orig.a_M_err

    def get_param_names(self):
        params = super().get_param_names()
        params = params + [
            'M_H', 'M_H_err',
            'a_M', 'a_M_err'
        ]
        return params
   
    def synthmag_carrie(self, filter, log_L):
        #remember - phoenix flux needs to be multiplied by *1e-8

        #normalising spectra
        #getting bounds of integral
        lam = self.wave[(self.wave <= filter.wave.max()) & (self.wave >= filter.wave.min())]
        T = np.interp(lam, filter.wave, filter.thru)
        T = np.where(T < .001, 0, T)

        R = self.get_radius(log_L, np.log10(self.T_eff))

        #1/(3.08567758128*10**(19))**2 is just 1/10pc^2 in cm! (1/(3.086e19)**2)
        
        s = 1e-8 * self.flux[(self.wave <= filter.wave.max()) & (self.wave >= filter.wave.min())]
        s = s * (R / 3.086e19) ** 2           #NOT multiplied by pi!

        # Interpolating to get filter data on same scale as spectral data
        # Doing classic integral to get flux in bandpass
        stzp = 3.631e-9
        i1 = simps(s * T * lam, lam)
        i2 = simps(T * lam, lam)
        i3 = simps(T / lam, lam)
        a = -2.5 * np.log10(i1 / (stzp * i2))
        b = -2.5 * np.log10(i2 / i3)

        return a + b + 18.6921

    def normalize_to_mag(self, filt, mag):
        try:
            m = self.synthmag(filt)
            # if m <= -10:
            #     # Checking that not really negative number, which happens when flux is from
            #     # Phoenix but isn't properly re-scaled - i.e. flux is ~1e8 too big
            #     # this step probably isn't really catching everything - must look into better way
            # m = self.synthmag_carrie(filt)
        except Exception as ex:
            print('flux max', np.max(self.flux))
            print('mag', mag)
            raise ex
        DM = mag - m
        D = 10 ** (DM / 5)

        self.multiply(1 / D**2)
        self.mag = mag