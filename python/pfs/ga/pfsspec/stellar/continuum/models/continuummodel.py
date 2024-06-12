import numpy as np
from collections.abc import Iterable

from pfs.ga.pfsspec.core import PfsObject
from pfs.ga.pfsspec.core import Physics
from pfs.ga.pfsspec.core import Spectrum
from pfs.ga.pfsspec.core.util.array_filters import *

class ContinuumModel(PfsObject):
    """
    Implements functions to fit and evaluate a continuum model to a stellar spectrum.

    The class also supports configuring the model from the command-line and saving/loading
    the model parameters to/from a file.
    """

    PREFIX_CONTINUUM_MODEL = 'continumm_model'

    def __init__(self,
                 continuum_finder=None,
                 max_iter=None,
                 trace=None, orig=None):
        
        """
        Initializes the continuum model.

        Parameters
        ----------
        
        """
        
        super().__init__()

        if not isinstance(orig, ContinuumModel):
            self.version = 1
            self.trace = trace

            self.continuum_finder = continuum_finder
            
            self.max_iter = max_iter if max_iter is not None else 5

            self.use_spec_continuum = False                                 # Fit model to model continuum instead of flux
            self.use_spec_mask = True                                       # Use the mask from the spectrum
            self.mask_bits = None                                           # Mask bits to use when fitting the model
            self.use_log_flux = False                                       # Fit the log of flux

            self.include_ranges = None                                      # Include in control point finding
            self.include_mask = None
            self.include_overflow = None
            self.exclude_ranges = None                                      # Exclude from control point finding
            self.exclude_mask = None
            self.exclude_overflow = None
            
            self.wave = None                                                # Cache for wave when fitting an entire grid
        else:
            self.version = orig.version
            self.trace = trace or orig.trace

            self.continuum_finder = continuum_finder or orig.continuum_finder

            self.max_iter = max_iter if max_iter is not None else orig.max_iter

            self.use_spec_continuum = orig.use_spec_continuum
            self.use_spec_mask = orig.use_spec_mask
            self.use_log_flux = orig.use_log_flux

            self.include_ranges = orig.include_ranges
            self.include_mask = orig.include_mask
            self.include_overflow = orig.include_overflow
            self.exclude_ranges = orig.exclude_ranges
            self.exclude_mask = orig.exclude_mask
            self.exclude_overflow = orig.exclude_overflow
            
            self.wave = orig.wave

    @property
    def name(self):
        """
        Returns the name of the continuum model.
        """

        raise NotImplementedError()
    
    def add_args(self, parser):
        parser.add_argument('--continuum-use-spec-cont', action='store_true', help='Fit model continuum instead of flux.\n')
        parser.add_argument('--continuum-use-spec-mask', action='store_true', help='Use mask from spectrum.\n')
        parser.add_argument('--continuum-max-iter', type=int, help='Continuum fitting iterations.\n')

    def init_from_args(self, args):
        self.use_spec_continuum = self.get_arg('continuum_use_cont', self.use_spec_continuum, args)
        self.use_spec_mask = self.get_arg('continuum_use_mask', self.use_spec_mask, args)
        self.max_iter = self.get_arg('continuum_max_iter', self.max_iter, args)

    #region Functions to support storing continuum models for synthetic stellar model grids

    def get_constants(self, wave=None):
        """
        Return a list of constants to be stored along a synthetic stellar model grid.
        """
        
        return { f'{self.name}_version': self.version }

    def set_constants(self, constants, wave=None):
        """
        Sets the model contants from a list of constants stored along a synthetic stellar model grid.
        """

        self.version = int(constants[f'{self.name}_version'])

    def set_constant(self, name, constants, default):
        """
        Set the value of a model constant with a default value.
        """

        if name in constants and constants[name] is not None:
            return constants[name]
        else:
            return default

    def save_items(self):
        """
        Saves model parameters to a file.
        """

        # e.g.
        # self.save_item('/'.join((self.PREFIX_CONTINUUM_MODEL, 'legendre_deg')), self.legendre_deg)

        pass

    def load_items(self):
        """
        Load model parameters from a file.
        """

        # e.g.
        # self.legendre_deg = self.load_item('/'.join((self.PREFIX_CONTINUUM_MODEL, 'legendre_deg')), int, default=self.legendre_deg)

        pass

    def get_interpolated_params(self):
        """
        Return model parameters that can be interpolated over gridpoints of
        a synthetic stellar model grid.
        """

        return []

    def init_values(self, grid):
        # Initialize the values in a grid necessary to store the fitted parameters
        # These are the parameters that we store for each spectrum and not the grid-wide
        # constants that are the same for each spectrum.
        for p in self.get_interpolated_params():
            grid.init_value(p.name)

    def allocate_values(self, grid):
        # Allocate the values in a grid necessary to store the fitted parameters
        raise NotImplementedError()

    def fill_model_params_grid(self, name, params):
        """
        Fill in the holes of the parameter grid.
        
        The default behavior of filling holes in the parameter grid is to substitute
        nan values with the mean of direct neighbors.
        """

        fill_params = np.full(params.shape, np.nan)
        for i in range(params.shape[-1]):
            fill_params[..., i] = fill_holes_filter(params[..., i], fill_filter=np.nanmean, value_filter=np.nanmin)
        return fill_params

    def smooth_model_params_grid(self, name, params):
        """
        Smooth the model parameters over the gridpoints.

        The default behavior is to apply anisotropic diffusion to the parameters.
        """        
        
        shape = params.shape
        params = params.squeeze()
        sp = anisotropic_diffusion(params, 
                                    niter=self.smoothing_iter,
                                    kappa=self.smoothing_kappa,
                                    gamma=self.smoothing_gamma)
        sp = sp.reshape(shape)
        return sp
    
    #endregion
    #region Functions for handling the wavelength grid, wavelength limits and masks
    
    def init_wave(self, wave, force=True, omit_overflow=False):
        """
        Initialize the wave vector cache and masks in derived classes.
        """

        if force or self.wave is None:
            self.wave = wave

        if self.include_ranges is not None and (force or self.include_mask is None):
            self.include_mask, self.include_overflow = self.ranges_to_mask(
                wave, self.include_ranges,
                omit_overflow=omit_overflow)

        if self.exclude_ranges is not None and (force or self.exclude_mask is None):
            self.exclude_mask, self.exclude_overflow = self.ranges_to_mask(
                wave, self.exclude_ranges,
                omit_overflow=omit_overflow)

    def get_hydrogen_limits(self):
        limits = [2530,] + Physics.HYDROGEN_LIMITS + [17500,]
        return Physics.air_to_vac(np.array(limits))

    def limits_to_ranges(self, limits):
        """
        Convert a list of limits to a list of ranges.
        """

        ranges = []
        for i in range(len(limits) - 1):
            ranges.append([limits[i], limits[i + 1]])
        return ranges
    
    @staticmethod
    def lessthan(a, b, strict=False):
        if strict:
            return a < b
        else:
            return a <= b
    
    def ranges_to_mask(self, wave, ranges, mask=None, dlambda=0, strict=False, omit_overflow=False):
        """
        Convert a list of wavelength ranges to a mask.

        Assume that the wave vector is sorted.

        Parameters
        ----------
        wave : array
            Wavelength vector.
        ranges : list of tuples
            List of wavelength ranges to convert to a mask.
        mask : array
            Optional input mask.
        dlambda : float or tuple
            Buffer around the limits of the ranges.
        strict : bool
            Use strict comparison.
        omit_overflow : bool
            Exclude ranges that overflow the wavelength vector.

        Returns
        -------
        mask : array
            Mask for the wavelength vector.
        overflow : list of bool
            List of indices of ranges that overflow the wavelength vector.
        """

        if not isinstance(ranges, Iterable):
            ranges = [ ranges ]

        if not isinstance(dlambda, Iterable):
            dlambda = ( dlambda, dlambda )

        # Construct a mask by merging all limits with a buffer of `dlambda`
        m = np.full(wave.shape, False)
        overflow = []
        for i, r in enumerate(ranges):
            # Handle overflow
            if r[0] + dlambda[0] < wave[0] or r[1] - dlambda[1] > wave[-1]:
                overflow.append(i)
                if omit_overflow:
                    continue

            # Generate the mask
            m |= self.lessthan(r[0] + dlambda[0], wave, strict) & \
                 self.lessthan(wave, r[1] - dlambda[1], strict)
            
        # Combine with optional input mask
        if mask is not None:
            m &= mask

        return m, overflow
    
    def limits_to_masks(self, wave, limits, mask=None, dlambda=0, strict=False, omit_overflow=False):
        """
        Convert a list of wavelengths into a list of masks in-between the limits.

        Assume that the wavelength vector is sorted.
        """

        if not isinstance(dlambda, Iterable):
            dlambda = ( dlambda, dlambda )

        # Find intervals between the limits
        masks = []
        ranges = []
        overflow = []
        for i in range(len(limits) - 1):
            l0, l1 = limits[i], limits[i + 1]
            
            l0 = l0 if l0 is not None else wave[0]
            l1 = l1 if l1 is not None else wave[-1]
            
            # Handle overflow
            if l0 + dlambda[0] < wave[0] or l1 - dlambda[1] > wave[-1]:
                overflow.append(i)
                if omit_overflow:
                    continue

            m = self.lessthan(l0 + dlambda[0], wave, strict) & \
                self.lessthan(wave, l1 - dlambda[1], strict)

            # Combine with optional input mask
            if mask is not None:
                m &= mask

            masks.append(m)

            # Find the actual range after applying the mask
            w = wave[m]
            if w.size > 0:
                ranges.append([w[0], w[-1]])
            else:
                ranges.append([np.nan, np.nan])

        return masks, ranges, overflow

    #endregion

    def fit(self, spec, mask=None):
        """
        Fit the continuum to a spectum.

        Parameters
        ----------
        spec : Spectrum
            Spectrum to fit the continuum to.
        mask : array
            Optional additional mask to use. Will be AND-ed with the spectrum mask.
        """

        # Wave is cached because masks can be re-used this way
        if self.wave is None:
            self.init_wave(spec.wave, force=True)

        # Collect the flux vectors
        if self.use_spec_continuum:
            flux = spec.cont
            flux_err = None
        else:
            flux = spec.flux
            flux_err = spec.flux_err

        # Transform the flux if necessary
        flux, flux_err = self.transform_flux_forward(flux, flux_err)

        # Construct the full mask
        m = None
        if self.use_spec_mask:
            m = spec.mask_as_bool(bits=self.mask_bits)
        if mask is not None:
            m = m & mask if m is not None else mask

        if self.trace is not None:
            spec = Spectrum()
            spec.wave, spec.flux, spec.flux_err = self.wave, flux, flux_err
            spec.mask_flags, spec.mask_bits = spec.mask_flags, spec.mask_bits
            # TODO: auxilliary mask
            self.trace.on_fit_start(spec)

        params = self.fit_impl(flux, flux_err, m)

        if self.trace is not None:
            # Evaluate the model on the same wavelength grid
            spec = Spectrum()
            spec.wave, spec.cont = self.eval(params)
            spec.flux, spec.flux_err = flux, flux_err
            spec.mask = m
            self.trace.on_fit_finish(spec)

        return params

    def fit_impl(self, flux, flux_err, mask):
        raise NotImplementedError()

    def eval(self, params):
        flux = self.eval_impl(params)

        # Reverse transform the flux if fitting in log
        flux, _ = self.transform_flux_reverse(flux)

        # TODO: add trace hook

        return self.wave, flux
    
    def eval_impl(self, params):
        raise NotImplementedError()
    
    def transform_flux_forward(self, flux, flux_err=None):
        if self.use_log_flux:
            flux = self.safe_log(flux), 
            flux_err = self.safe_log_error(flux, flux_err) if flux_err is not None else None

        return flux, flux_err

    def transform_flux_reverse(self, flux, flux_err=None):
        if self.use_log_flux:
            flux = self.safe_exp(flux)
            flux_err = self.safe_exp_error(flux, flux_err) if flux_err is not None else None

        return flux, flux_err

    def normalize(self, spec, params):
        raise NotImplementedError()

    def denormalize(self, spec, params, s=None):
        raise NotImplementedError()

    def fit_function(self, id, func, x, y, w=None, p0=None, mask=None, continuum_finder=None, **kwargs):
        """
        Fit a function to a set of points. If a continuum finder algorithm is set,
        use that to identify points to fit to.
        """

        param_count = func.get_param_count()
        min_point_count = func.get_min_point_count()

        continuum_finder = continuum_finder if continuum_finder is not None else self.continuum_finder

        if mask is None:
            mask = np.full_like(x, True, dtype=bool)
        else:
            mask = mask.copy()
            
        iter = 0
        params = None
        success = False
        while True:
            if iter == 0 and p0 is not None and self.continuum_finder is not None:
                # Use initial parameter estimates in the first iteration
                params = p0
            else:
                # Filter points based on the previous iteration of fitting
                # and run fitting again
                params = func.fit(x[mask], y[mask], 
                    w=w[mask] if w is not None else None,
                    p0=params, **kwargs)    
            
            if self.trace:
                self.trace.on_fit_function_iter(id, iter, x, y, w, func.eval(x, params), mask)
            
            # We're always successful if it's a linear model and func.fit has been
            # executed at least once.
            # TODO: handle non-linear fitting with unsuccessful convergence here
            #       this requires returning a success flag from func.fit
            success = True  

            # If we fit to all points withing the mask and there's no continuum finder
            # to be executed iteratively, we're done, otherwise just do the iterations
            if continuum_finder is None:
                break

            # Evaluate the model at the current parameters and run the continuum finder to
            # filter out points that are not part of the continuum
            model = func.eval(x, params)
            mask, need_more_iter = continuum_finder.find(iter, x, y, w=w, mask=mask, model=model)
            iter += 1

            if not need_more_iter:
                break

            # Only continue fitting if we have enough data points
            if mask.sum() < min_point_count:
                break

        if success:
            return True, params
        else:
            return False, np.full(param_count, np.nan)

#region Utility functions

    def safe_log(self, x):
        return np.log(np.where(x > 1e-7, x, np.nan))

    def safe_log_error(self, x, sigma):
        return np.where(x > 1e-7, sigma / x, np.nan)

    def safe_exp(self, x):
        return np.exp(np.where(x < 100, x, np.nan))

    def safe_exp_error(self, x, sigma):
        return np.where(x < 100, x * sigma, np.nan)

#endregion