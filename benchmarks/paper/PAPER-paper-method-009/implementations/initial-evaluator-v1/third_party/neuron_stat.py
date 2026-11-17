import numpy as np
from scipy.special import erfcinv
from typing import Union, Tuple, Optional, NamedTuple
from numpy.typing import NDArray

# Constants
MAD_SCALING_CONSTANT = -1 / (np.sqrt(2) * erfcinv(3/2))  # MATLAB's scaling constant for MAD
DEFAULT_MAX_ITERATIONS = 10
DEFAULT_OUTLIER_THRESHOLD = 3.0

class NeuronStatsResult(NamedTuple):
    """Result of neuron_stats computation."""
    phi: float
    phi_estimates: Optional[NDArray] = None  # Optional for diagnostic output

class NeuronStatsError(Exception):
    """Custom exception for neuron_stats function errors."""
    pass

def _validate_inputs(
    spikes: NDArray,
    react_time: Optional[NDArray],
    waiting_time_cut: int,
    binsize: int,
    shift: int
) -> NDArray:
    """Validate input parameters and standardize react_time.

    Args:
        spikes: Array of shape (n_trials, n_timepoints) with binary spike data (0 or 1).
        react_time: Array of shape (n_trials,) with reaction times or None if absent.
        waiting_time_cut: Maximum time window for analysis (ms).
        binsize: Size of the small bin (ms).
        shift: Step size for sliding window (ms).

    Returns:
        NDArray: Standardized react_time as a NumPy array (zeros if None).

    Raises:
        NeuronStatsError: If inputs are invalid.
    """
    if not isinstance(spikes, np.ndarray):
        raise NeuronStatsError("spikes must be a NumPy array")
    if spikes.ndim != 2:
        raise NeuronStatsError("spikes must be a 2D array (n_trials, n_timepoints)")
    if not np.issubdtype(spikes.dtype, np.number):
        raise NeuronStatsError("spikes must contain numeric values")
    if not np.all(np.isin(spikes, [0, 1, np.nan])):
        raise NeuronStatsError("spikes must contain only 0s, 1s, or NaN values")

    n_trials = spikes.shape[0]
    if react_time is None:
        react_time = np.zeros(n_trials, dtype=np.float32)
    elif not isinstance(react_time, np.ndarray):
        raise NeuronStatsError("react_time must be a NumPy array or None")
    elif react_time.ndim != 1 or react_time.shape[0] != n_trials:
        raise NeuronStatsError("react_time must be a 1D array with length equal to spikes' first dimension")
    elif np.any(react_time < 0):
        raise NeuronStatsError("react_time values must be non-negative")

    if not all(isinstance(x, (int, float)) and x >= 0 for x in [waiting_time_cut, binsize, shift]):
        raise NeuronStatsError("waiting_time_cut, binsize, and shift must be non-negative")
    if binsize <= 0 or shift <= 0:
        raise NeuronStatsError("binsize and shift must be positive")
    if waiting_time_cut < binsize:
        raise NeuronStatsError("waiting_time_cut must be >= binsize")

    return react_time

def _apply_reaction_time_cuts(
    spikes: NDArray,
    react_time: NDArray,
    waiting_time_cut: int
) -> NDArray:
    """Apply reaction time cuts to spike data.

    Args:
        spikes: Array of shape (n_trials, n_timepoints) with binary spike data.
        react_time: Array of shape (n_trials,) with reaction times (0s if absent).
        waiting_time_cut: Maximum time window for analysis (ms).

    Returns:
        NDArray: Modified spike array with NaN values after cut points.
    """
    spike_copy = spikes.astype(np.float32)
    if np.all(react_time == 0):
        spike_copy[:, waiting_time_cut + 1:] = np.nan
    else:
        cut_points = np.minimum(react_time, waiting_time_cut)
        cut_points[react_time == 0] = 1
        cut_points = cut_points.astype(int) + 1
        indices = np.arange(spike_copy.shape[1])
        mask = indices >= cut_points[:, np.newaxis]
        spike_copy[mask] = np.nan

    return spike_copy

def _compute_bin_counts(
    spikes: NDArray,
    binsize: int,
    shift: int,
    waiting_time_cut: int,
    alpha: float = 2.0
) -> Tuple[NDArray, NDArray, int]:
    """Compute spike counts for small and large bins.

    Args:
        spikes: Array of shape (n_trials, n_timepoints) with spike data.
        binsize: Size of the small bin (ms).
        shift: Step size for sliding window (ms).
        waiting_time_cut: Maximum time window for analysis (ms).
        alpha: Scaling factor for large bins (default: 2.0).

    Returns:
        Tuple[NDArray, NDArray, int]: Small bin counts, large bin counts, number of bin pairs.

    Raises:
        NeuronStatsError: If bin configuration is invalid.
    """
    n_trials = spikes.shape[0]
    binsize_p = int(np.floor(alpha * binsize))
    num_bins_p = int(np.floor((waiting_time_cut - binsize_p) / shift)) + 1

    if num_bins_p <= 0:
        raise NeuronStatsError(
            "Invalid number of bins: num_bins_p must be positive. Check waiting_time_cut, binsize, and shift."
        )

    count_small = np.zeros((n_trials, 2 * num_bins_p))
    count_large = np.zeros((n_trials, 2 * num_bins_p))

    for i in range(num_bins_p):
        start = int(i * shift)
        count_small[:, 2 * i] = np.nansum(spikes[:, start:start + binsize], axis=1)
        count_small[:, 2 * i + 1] = np.nansum(spikes[:, start + binsize:start + 2 * binsize], axis=1)
        count_large[:, 2 * i] = np.nansum(spikes[:, start:start + binsize_p], axis=1)
        count_large[:, 2 * i + 1] = count_large[:, 2 * i]

    return count_small, count_large, num_bins_p

def _remove_outliers_mad(data: NDArray, threshold: float = DEFAULT_OUTLIER_THRESHOLD) -> NDArray:
    """Remove outliers using the Median Absolute Deviation (MAD) method.

    Args:
        data: Input array to filter outliers from.
        threshold: Number of scaled MADs to define outliers (default: 3.0).

    Returns:
        NDArray: Array with outliers removed.
    """
    if len(data) == 0 or np.all(data == data[0]):  # No variability
        return data

    median_val = np.median(data)
    mad = np.median(np.abs(data - median_val))
    if mad == 0:  # Avoid division by zero
        return data

    scaled_mad = MAD_SCALING_CONSTANT * mad
    lower_bound = median_val - threshold * scaled_mad
    upper_bound = median_val + threshold * scaled_mad
    return data[(data >= lower_bound) & (data <= upper_bound)]

def neuron_stats(
    spikes: NDArray,
    react_time: Optional[NDArray] = None,
    waiting_time_cut: int = 2000,
    binsize: int = 100,
    shift: int = 50,
    alpha: float = 2.0,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    outlier_threshold: float = DEFAULT_OUTLIER_THRESHOLD,
    return_diagnostics: bool = False
) -> Union[float, NeuronStatsResult]:
    """Compute neuron statistics (phi) from spike data with optional reaction time cuts.

    This function is alculating a statistic (phi) based on spike counts in small and large bins, 
    with outlier removal using the Median Absolute Deviation (MAD) method. 
    If reaction times are not provided, a default cutoff at waiting_time_cut is applied.

    Args:
        spikes: Array of shape (n_trials, n_timepoints) with binary spike data (0 or 1).
        react_time: Array of shape (n_trials,) with reaction times (ms) or None (default: None).
        waiting_time_cut: Maximum time window for analysis (ms) (default: 2000).
        binsize: Size of the small bin (ms) (default: 100).
        shift: Step size for sliding window (ms) (default: 50).
        alpha: Scaling factor for large bins (default: 2.0).
        max_iterations: Maximum iterations for refinement when phi < 1 (default: 10).
        outlier_threshold: Number of scaled MADs for outlier removal (default: 3.0).
        return_diagnostics: If True, return phi and initial phi estimates (default: False).

    Returns:
        Union[float, NeuronStatsResult]: Computed phi statistic or NamedTuple with diagnostics.

    Raises:
        NeuronStatsError: If inputs are invalid or computations fail.
    """
    # Validate inputs and standardize react_time
    react_time = _validate_inputs(spikes, react_time, waiting_time_cut, binsize, shift)

    # Apply reaction time cuts
    spike_copy = _apply_reaction_time_cuts(spikes, react_time, waiting_time_cut)

    # Compute bin counts
    count_small, count_large, _ = _compute_bin_counts(spike_copy, binsize, shift, waiting_time_cut, alpha)

    # Compute statistics
    nvar_small = np.nanvar(count_small, axis=0)
    nmean_small = np.nanmean(count_small, axis=0)
    nvar_large = np.nanvar(count_large, axis=0)
    nmean_large = np.nanmean(count_large, axis=0)

    # Calculate phi estimates
    try:
        phi_est = (nvar_large - (alpha**2) * nvar_small) / (nmean_large - (alpha**2) * nmean_small)
    except (ZeroDivisionError, RuntimeWarning):
        raise NeuronStatsError("Division by zero or invalid operation in phi calculation")

    # Filter phi estimates and remove outliers
    phi_filtered = phi_est[(phi_est > 0) & (phi_est < 5)]
    phi_filtered = _remove_outliers_mad(phi_filtered, outlier_threshold)
    phi_mean = np.mean(phi_filtered) if len(phi_filtered) > 0 else np.nan

    if np.isnan(phi_mean):
        return NeuronStatsResult(phi=phi_mean, phi_estimates=phi_est) if return_diagnostics else phi_mean

    # Iterative refinement if phi_mean < 1
    if phi_mean < 1:
        for _ in range(max_iterations):
            phiar = (nvar_large - (alpha**2) * nvar_small + ((alpha**2 - 1) / 6) * (1 - phi_mean**2)) / \
                    (nmean_large - (alpha**2) * nmean_small)
            phi_filtered = phiar[(phiar > 0) & (phiar < 5)]
            phi_filtered = _remove_outliers_mad(phi_filtered, outlier_threshold)
            phi_mean = np.mean(phi_filtered) if len(phi_filtered) > 0 else np.nan
            if np.isnan(phi_mean):
                break
    else:
        # Quadratic solution
        a = (alpha**2 - 1) / 6
        b = nmean_large - (alpha**2) * nmean_small
        c = (alpha**2) * nvar_small - nvar_large - ((alpha**2 - 1) / 6)
        try:
            discriminant = b**2 - 4 * a * c
            if np.any(discriminant < 0):
                raise NeuronStatsError("Negative discriminant in quadratic solution")
            phi_est = np.real((-b - np.sqrt(discriminant)) / (2 * a))
            phi_mean = np.mean(phi_est)
        except (ZeroDivisionError, RuntimeWarning):
            raise NeuronStatsError("Invalid quadratic solution in phi calculation")

    return NeuronStatsResult(phi=phi_mean, phi_estimates=phi_est) if return_diagnostics else phi_mean