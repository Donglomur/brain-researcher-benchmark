"""Equal target-field weights, independent of trial-count imbalance."""


def equal_field_amplitudes(left_po7, left_po8, right_po7, right_po8):
    contra = 0.5 * (left_po8 + right_po7)
    ipsi = 0.5 * (left_po7 + right_po8)
    fixed = 0.5 * (left_po8 + right_po8 - left_po7 - right_po7)
    return contra, ipsi, fixed
