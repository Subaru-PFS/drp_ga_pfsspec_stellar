import numpy as np
import matplotlib.pyplot as plt
import pysynphot
import pysynphot.binning
import pysynphot.spectrum
import pysynphot.reddening

from pfsspec.constants import Constants
from pfsspec.pfsobject import PfsObject

class Spectrum(PfsObject):
    def __init__(self):
        super(Spectrum, self).__init__()
        self.wave = None
        self.flux = None

    def fnu_to_flam(self):
        # ergs/cm**2/s/hz/ster to erg/s/cm^2/A surface flux
        self.flux /= 3.336e-19 * (self.wave) ** 2 / 4 / np.pi

    def flam_to_fnu(self):
        self.flux *= 3.336e-19 * (self.wave) ** 2 / 4 / np.pi

    def redshift(self, z):
        self.wave *= 1 + z

    def rebin(self, nwave):
        spec = pysynphot.spectrum.ArraySourceSpectrum(wave=self.wave, flux=self.flux)
        filt = pysynphot.spectrum.ArraySpectralElement(self.wave, np.ones(len(self.wave)), waveunits='angstrom')
        obs = pysynphot.observation.Observation(spec, filt, binset=nwave, force='taper')

        res = Spectrum()
        res.wave = obs.binwave
        res.flux = obs.binflux

        return res

    def redden(self, extval):
        spec = pysynphot.spectrum.ArraySourceSpectrum(wave=self.wave, flux=self.flux)
        obs = spec * pysynphot.reddening.Extinction(extval, 'mwavg')

        res = Spectrum()
        res.wave = obs.wave
        res.flux = obs.flux

        return res

    def synthflux(self, filter):
        spec = pysynphot.spectrum.ArraySourceSpectrum(wave=self.wave, flux=self.flux)
        filt = pysynphot.spectrum.ArraySpectralElement(filter.wave, filter.thru, waveunits='angstrom')
        obs = pysynphot.observation.Observation(spec, filt)
        return obs.effstim('Jy')

    def synthmag(self, filter):
        flux = self.synthflux(filter)
        return -2.5 * np.log10(flux) + 8.90

    def plot(self, ax=None, xlim=Constants.DEFAULT_PLOT_WAVE_RANGE, ylim=None, labels=True):
        ax = self.plot_getax(ax, xlim, ylim)
        ax.plot(self.wave, self.flux)
        if labels:
            ax.set_xlabel(r'$\lambda$ [A]')
            ax.set_ylabel(r'$F_\lambda$ [erg s-1 cm-2 A-1]')

        return ax