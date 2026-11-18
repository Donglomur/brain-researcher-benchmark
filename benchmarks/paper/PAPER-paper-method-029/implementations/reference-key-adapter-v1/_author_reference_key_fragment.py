"""Verbatim author reference loaders (source lines23-45), for generated parity tests.
Original-release commit edbff02edd6a08d3c6c829af45a957fd14bdc460
Full plot_figure.py SHA256638811c8038d1c0d43e03577d7ddd2243eb2bf9c5b061412288add7e51fd8566
Git blob27f1255c19db57380877250badddc38f64148578

MIT License

Copyright (c) 2025 Kamitani Lab

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
import pandas as pd

def load_nc_data_pattern(nc_file, nc_thd_file):
    """Load noise ceiling data and add identifiers for pattern analysis."""
    df_nc = pd.read_csv(nc_file)
    df_nc_thd = pd.read_csv(nc_thd_file)
    df_nc['Subject'] = df_nc['Subject'].str.replace('-', '')
    df_nc['Image index'] = df_nc['Image index'].astype(int)
    df_nc_thd['Image index'] = df_nc_thd['Image index'].astype(int)
    df_nc['identifier'] = df_nc['Subject'].values + df_nc['ROI'].values + df_nc['Image index'].values.astype(str)
    df_nc_thd['identifier'] = df_nc_thd['Subject'].values + df_nc_thd['ROI'].values + df_nc_thd[
        'Image index'].values.astype(str)
    df_nc = df_nc.join(df_nc_thd.set_index('identifier'), rsuffix='_', on='identifier')
    return df_nc


def load_nc_data_profile(nc_file, nc_thd_file):
    """Load noise ceiling data and add identifiers for profile analysis."""
    df_nc = pd.read_csv(nc_file)
    df_nc_thd = pd.read_csv(nc_thd_file)
    df_nc['identifier'] = df_nc['Subject'].values + df_nc['ROI'].values + df_nc['Vox_idx'].values.astype(str)
    df_nc_thd['identifier'] = df_nc_thd['Subject'].values + df_nc_thd['ROI'].values + df_nc_thd[
        'Vox_idx'].values.astype(str)
    df_nc = df_nc.join(df_nc_thd.set_index('identifier'), rsuffix='_', on='identifier')
    return df_nc
