"""Deferred numerical primitives for the full declared-label profile."""
from .numeric import (NumericLimits, NumericalError, Scaler, PCA, Ridge, Centroid,
                      ViewBank, c_descriptor, batch_c_descriptor, rms_rows,
                      fit_scaler, apply_scaler, fit_pca_primitive, predict_pca,
                      fit_ridge, predict_ridge, fit_centroid, predict_centroid,
                      fit_view, transform_view, to_dict, from_dict)
