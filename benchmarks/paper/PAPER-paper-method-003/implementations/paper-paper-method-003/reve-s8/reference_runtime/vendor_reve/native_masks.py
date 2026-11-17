"""Exact extracted author mask functions; native index order is preserved."""
import numpy as np
import torch
from scipy.spatial import KDTree

def spatial_masking(
    C,
    masking_ratio,
    radius,
    precomp_masked_indices=None,
):
    n_channels = C.shape[0]
    n_masked_channels = int(masking_ratio * n_channels)
    mask = np.zeros(n_channels, dtype=bool)

    # Pre-add masks from dropout
    if precomp_masked_indices is not None:
        mask[precomp_masked_indices] = True

    # Use a KD-Tree to find neighboring channels
    kdtree = KDTree(C)

    unmasked_indices = np.where(~mask)[0]
    while len(unmasked_indices) > 0 and np.sum(mask) < n_masked_channels:
        unmasked_indices = np.where(~mask)[0]
        _index = np.random.choice(unmasked_indices)
        _channel = C[_index]
        _neighbors = kdtree.query_ball_point(_channel, radius)
        mask[_neighbors] = True
    masked_indices = np.where(mask)[0]

    return masked_indices

def create_block_masks(  # noqa: PLR0913
    n_chans,
    masking_ratio,
    radius_spat_mask,
    radius_temp_mask,
    num_patches,
    pos,
    dropout_ratio,
    dropout_ratio_radius,
):
    num_block_patches = num_patches // radius_temp_mask
    num_isolated_patches = num_patches % radius_temp_mask
    num_masked_chans = int(masking_ratio * n_chans)
    chan_indices = np.arange(n_chans)

    # Obtain dropout masks in first pass
    if dropout_ratio > 0:
        dropout_channels = spatial_masking(pos, dropout_ratio, dropout_ratio_radius)[: int(dropout_ratio * n_chans)]
    else:
        dropout_channels = None

    # Create block masks
    block_masks = [
        spatial_masking(pos, masking_ratio, radius_spat_mask, dropout_channels)[:num_masked_chans]
        for _ in range(num_block_patches)
    ]
    idx_block = np.repeat(
        np.array(block_masks)[:, np.newaxis, :],
        radius_temp_mask,
        axis=1,
    ).reshape(-1, num_masked_chans)

    # Create masks for remaining patches (case where num of patches and masks don't overlap)
    isolated_masks = [
        spatial_masking(pos, masking_ratio, radius_spat_mask)[:num_masked_chans] for _ in range(num_isolated_patches)
    ]
    idx_isolated = np.array(isolated_masks)

    mask = np.concatenate([idx_block, idx_isolated], axis=0)

    # Efficient unmasks generation
    unmask = np.array([np.setdiff1d(chan_indices, masked_indices, assume_unique=True) for masked_indices in mask])

    flat_indices = np.arange(mask.shape[0])[:, np.newaxis]
    masked_indices = (n_chans * flat_indices + mask).ravel()
    unmasked_indices = (n_chans * flat_indices + unmask).ravel()
    np.random.shuffle(masked_indices)
    np.random.shuffle(unmasked_indices)

    batch_mask = torch.from_numpy(masked_indices)
    batch_unmask = torch.from_numpy(unmasked_indices)
    return batch_mask, batch_unmask
