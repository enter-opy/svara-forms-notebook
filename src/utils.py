import os
import pickle
import json 
import yaml
import csv
import math

import numpy as np
import pandas as pd 
import numpy as np
from scipy.interpolate import UnivariateSpline, interp1d

def load_json(path):
    """
    Load json at <path> to dict
    
    :param path: path of json
    :type path: str

    :return: dict of json information
    :rtype: dict
    """ 
    # Opening JSON file 
    with open(path) as f: 
        data = json.load(f) 
    return data


def write_json(j, path):
    """
    Write json, <j>, to <path>

    :param j: json
    :type path: json
    :param path: path to write to, 
        if the directory doesn't exist, one will be created
    :type path: str
    """ 
    create_if_not_exists(path)
    # Opening JSON file 
    with open(path, 'w') as f:
        json.dump(j, f)


def create_if_not_exists(path):
    """
    If the directory at <path> does not exist, create it empty
    """
    directory = os.path.dirname(path)
    # Do not try and create directory if path is just a filename
    if (not os.path.exists(directory)) and (directory != ''):
        os.makedirs(directory)


def load_annotations(path, delim='\t'):
    vals = []
    with open(path) as fd:
        rd = csv.reader(fd, delimiter=delim, quotechar='"')
        for l,_,s,e,d,a in rd:
            vals.append([str(l), s, e, d, str(a)])
    
    df = pd.DataFrame(vals, columns=['type', 'start', 'end', 'duration', 'label'])
    
    df['start'] = pd.to_datetime(df['start'])
    df['end'] = pd.to_datetime(df['end'])

    df['start_sec'] = df['start'].dt.microsecond*0.000001 + df['start'].dt.second + df['start'].dt.minute*60
    df['end_sec'] = df['end'].dt.microsecond*0.000001 + df['end'].dt.second + df['end'].dt.minute*60

    df['label'] = df['label'].apply(lambda y: y.strip().lower())

    return df[['start', 'end', 'start_sec', 'end_sec', 'label']]

def load_yaml(path):
    """
    Load yaml at <path> to dictionary, d
    
    Returns
    =======
    Wrapper dictionary, D where
    D = {filename: d}
    """
    import zope.dottedname.resolve
    def constructor_dottedname(loader, node):
        value = loader.construct_scalar(node)
        return zope.dottedname.resolve.resolve(value)

    def constructor_paramlist(loader, node):
        value = loader.construct_sequence(node)
        return ParamList(value)

    yaml.add_constructor('!paramlist', constructor_paramlist)
    yaml.add_constructor('!dottedname', constructor_dottedname)

    if not os.path.isfile(path):
        return None
    with open(path) as f:
        d = yaml.load(f, Loader=yaml.FullLoader)   
    return d


def cpath(*args):
    """
    Wrapper around os.path.join, create path concatenating args and
    if the containing directories do not exist, create them.
    """
    path = os.path.join(*args)
    create_if_not_exists(path)
    return path


def write_pitch_track(pitch_track, path, sep='\t'):
    """
    Write pitch contour to tsv at <path>
    """
    with open(path,'w') as file:
        for t, p in pitch_track:
            file.write(f"{t}{sep}{p}")
            file.write('\n')


def load_pitch_track(path, delim='\t'):
    """
    load pitch contour from tsv at <path>

    :param path: path to load pitch contour from
    :type path: str

    :return: Two numpy arrays of time and pitch values
    :rtype: tuple(numpy.array, numpy.array)
    """
    pitch_track = []
    with open(path) as fd:
        rd = csv.reader(fd, delimiter=delim, quotechar='"')
        for t,p in rd:
            pitch_track.append([float(t),float(p)])

    return np.array(pitch_track)




def pitch_to_cents(p, tonic):
    """
    Convert pitch value, <p> to cents above <tonic>.

    :param p: Pitch value in Hz
    :type p: float
    :param tonic: Tonic value in Hz
    :type tonic: float

    :return: Pitch value, <p> in cents above <tonic>
    :rtype: float
    """
    return 1200*math.log(p/tonic, 2) if p else None


def cents_to_pitch(c, tonic):
    """
    Convert cents value, <c> to pitch in Hz

    :param c: Pitch value in cents above <tonic>
    :type c: float/int
    :param tonic: Tonic value in Hz
    :type tonic: float

    :return: Pitch value, <c> in Hz 
    :rtype: float
    """
    return (2**(c/1200))*tonic


def pitch_seq_to_cents(pseq, tonic):
    """
    Convert sequence of pitch values to sequence of 
    cents above <tonic> values

    :param pseq: Array of pitch values in Hz
    :type pseq: np.array
    :param tonic: Tonic value in Hz
    :type tonic: float

    :return: Sequence of original pitch value in cents above <tonic>
    :rtype: np.array
    """
    return np.vectorize(lambda y: pitch_to_cents(y, tonic))(pseq)


def get_plot_kwargs(raga, tonic, cents=False, svara_cent_path = "conf/svara_cents.yaml", svara_freq_path = "conf/svara_lookup.yaml"):
    svara_cent = load_yaml(svara_cent_path)
    svara_freq = load_yaml(svara_freq_path)

    arohana = svara_freq[raga]['arohana']
    avorahana = svara_freq[raga]['avarohana']
    all_svaras = list(set(arohana+avorahana))

    if not cents:
        svara_cent = {k:cents_to_pitch(v, tonic) for k,v in svara_cent.items()}
    
    yticks_dict = {k:v for k,v in svara_cent.items() if any([x in k for x in all_svaras])}

    return {
        'yticks_dict':yticks_dict,
        'cents':cents,
        'tonic':tonic,
        'emphasize':['S', 'S ', 'S  ', ' S', '  S'],
        'figsize':(15,4)
    }


def subsample_series(time_series, pitch_series, proportion):
    """
    Subsample both time and pitch series by a proportion.
    
    Parameters:
    time_series (array-like): The time values corresponding to the pitch values.
    pitch_series (array-like): The pitch values to be subsampled.
    proportion (float): Proportion of data to retain. Must be between 0 and 1.
    
    Returns:
    subsampled_time (array-like): The subsampled time series.
    subsampled_pitch (array-like): The subsampled pitch series.
    """
    if not (0 < proportion <= 1):
        raise ValueError("Proportion must be between 0 and 1 (exclusive of 0).")
    
    # Calculate the number of points to keep
    total_points = len(time_series)
    num_to_keep = int(np.floor(total_points * proportion))
    
    if num_to_keep == 0:
        raise ValueError("Proportion too small, results in zero points being kept.")
    
    # Generate indices that are evenly spaced based on the proportion
    indices = np.linspace(0, total_points - 1, num_to_keep, dtype=int)
    
    # Subsample both arrays using these indices
    subsampled_time = np.array(time_series)[indices]
    subsampled_pitch = np.array(pitch_series)[indices]
    
    return subsampled_time, subsampled_pitch



def smooth_pitch_curve(time_series, pitch_series, smoothing_factor=0.6, min_points=4):
    """
    Smooth a quantized pitch time series in contiguous chunks using cubic splines,
    while handling None/NaN values and maintaining critical features. The data is 
    normalized to the range 0-1 before smoothing, and rescaled back to its original 
    range afterward.
    
    Parameters:
    time_series (array-like): Time values corresponding to the pitch.
    pitch_series (array-like): Quantized pitch values that need smoothing.
    smoothing_factor (float): Smoothing factor for the spline. Lower values = less smoothing.
    min_points (int): Minimum number of data points required to apply spline smoothing.
    
    Returns:
    smoothed_pitch (array-like): Smoothed pitch values over the entire time series.
    """
    # Convert input series to numpy arrays and handle None or NaN using pd.isna()
    time_series = np.array(time_series, dtype=float)
    pitch_series = np.array(pitch_series, dtype=float)

    # Initialize the result array with NaN values
    smoothed_pitch = np.full_like(pitch_series, np.nan)

    # Create a mask to filter out None/NaN values
    valid_mask = ~pd.isna(time_series) & ~pd.isna(pitch_series)

    # Find the indices of valid (non-NaN) data
    valid_indices = np.where(valid_mask)[0]

    if len(valid_indices) == 0:
        # If no valid data, return all NaNs
        return smoothed_pitch

    # Identify contiguous chunks of valid data
    contiguous_chunks = np.split(valid_indices, np.where(np.diff(valid_indices) > 1)[0] + 1)

    for chunk in contiguous_chunks:
        if len(chunk) >= min_points:  # Only process chunks with enough points
            time_chunk = time_series[chunk]
            pitch_chunk = pitch_series[chunk]

            # Normalize pitch_chunk to the range [0, 1]
            pitch_min = np.min(pitch_chunk)
            pitch_max = np.max(pitch_chunk)
            normalized_pitch_chunk = (pitch_chunk - pitch_min) / (pitch_max - pitch_min)

            # Apply smoothing to the normalized data
            spline_func = UnivariateSpline(time_chunk, normalized_pitch_chunk, s=smoothing_factor)
            smoothed_normalized_pitch = spline_func(time_chunk)

            # Rescale smoothed data back to the original range
            smoothed_pitch[chunk] = smoothed_normalized_pitch * (pitch_max - pitch_min) + pitch_min

        elif len(chunk) > 1:
            # If a chunk has fewer than min_points but more than 1, apply linear interpolation
            time_chunk = time_series[chunk]
            pitch_chunk = pitch_series[chunk]
            smoothed_pitch[chunk] = np.interp(time_chunk, time_chunk, pitch_chunk)

    return smoothed_pitch


def interpolate_below_length(arr, val, gap, indices):
    """
    Interpolate gaps of value, <val> of 
    length equal to or shorter than <gap> in <arr>, 
    except for regions containing any index in <indices>.
    
    :param arr: Array to interpolate
    :type arr: np.array
    :param val: Value expected in gaps to interpolate
    :type val: number
    :param gap: Maximum gap length to interpolate, gaps of <val> longer than <g> will not be interpolated
    :type gap: number
    :param indices: List of indices where interpolation should not occur
    :type indices: list

    :return: interpolated array
    :rtype: np.array
    """
    s = np.copy(arr)
    
    # Identify regions to potentially interpolate
    if np.isnan(val):
        is_zero = np.isnan(s)
    else:
        is_zero = s == val

    cumsum = np.cumsum(is_zero).astype('float')
    diff = np.zeros_like(s)
    diff[~is_zero] = np.diff(cumsum[~is_zero], prepend=0)
    
    # Loop through gaps to find ones that are below the gap length
    for i, d in enumerate(diff):
        if d <= gap:
            gap_start = int(i - d)
            gap_range = set(range(gap_start, i))
            
            # Check if any indices in the gap range are in the forbidden list
            if not gap_range.intersection(indices):
                s[gap_start:i] = np.nan  # Mark the region for interpolation
    
    # Perform interpolation only in marked regions
    interp = pd.Series(s).interpolate(method='linear', order=2, axis=0)\
                         .ffill()\
                         .bfill()\
                         .values
                         
    return interp


def align_time_series(*time_series):
    # Ensure at least one time series is provided
    if len(time_series) < 1:
        raise ValueError("At least one time series must be provided")
    
    # Compute the minimum timestep across all input time series
    min_timesteps = [np.min(np.diff(t[1])) for t in time_series]  # Find timestep for each series
    min_timestep = np.min(min_timesteps)  # Find the smallest timestep across all series
    
    # Initialize list to store the results for each time series
    interpolated_series = []
    
    # Loop over each time series
    for pitch, time in time_series:
        # Create a time grid for this series with the minimum timestep, preserving the original duration
        new_time = np.arange(time[0], time[-1] + min_timestep, min_timestep)
        
        # Interpolate the pitch data on the new time grid
        interp_func = interp1d(time, pitch, kind='linear', fill_value="extrapolate")
        new_pitch = interp_func(new_time)
        
        # Append the new interpolated series (pitch, time) to the results
        interpolated_series.append((new_pitch, new_time))
    
    return interpolated_series


def write_pkl(o, path):
    create_if_not_exists(path)
    with open(path, 'wb') as f:
        pickle.dump(o, f, pickle.HIGHEST_PROTOCOL)


def load_pkl(path):
    file = open(path,'rb')
    return pickle.load(file)


def remove_leading_trailing_nans(arr):
    if not isinstance(arr, np.ndarray):
        raise ValueError("Input must be a NumPy array")
    
    # Find indices of non-NaN values
    mask = ~np.isnan(arr)
    
    # If all values are NaN, return an empty array
    if not mask.any():
        return np.array([])
    
    # Get the indices of the first and last non-NaN value
    first_valid = np.argmax(mask)
    last_valid = len(mask) - np.argmax(mask[::-1]) - 1
    
    # Slice the array to remove leading and trailing NaNs
    return arr[first_valid:last_valid+1]


def expand_zero_regions(arr, x):
    """
    Expands contiguous zero regions in a NumPy array by 'x' elements on both sides.
    The expansion is done by replacing the neighboring values with zeros.

    Parameters:
    arr (numpy array): Input 1D NumPy array.
    x (int): Number of elements to expand on either side of zero regions.

    Returns:
    numpy array: Array with expanded zero regions.
    """
    arr = arr.copy()
    
    # Identify the indices where zeros are present
    zero_mask = arr == 0
    
    # Use convolution to identify contiguous regions and their expansion
    expanded_mask = np.convolve(zero_mask.astype(int), np.ones(2 * x + 1, dtype=int), mode='same') > 0
    
    # Replace the expanded regions with 0s
    arr[expanded_mask] = 0
    
    return arr


def write_list_to_file(filename, my_list):
    # Open the file in write mode ('w')
    with open(filename, 'w') as file:
        # Iterate over each item in the list
        for item in my_list:
            # Write each item followed by a newline
            file.write(f"{item}\n")


def get_context(context_data, track, annot_ix, k, direction):

    cont = context_data[track][annot_ix]
    prec = cont['prec']
    succ = cont['succ']
    precsucc = [' '.join(x) for x in list(zip(prec, succ))]

    if direction == 'prec':
        if k > len(prec):
            return None
        else:
            return ' '.join(prec[:k])
    
    if direction == 'succ':
        if k > len(succ):
            return None
        else:
            return ' '.join(succ[:k])

    if direction == 'both':
        if k > len(precsucc):
            return None
        else:
            return ' '.join(precsucc[:k])

    raise Exception('direction must be prec, succ or both')


def append_row(df, row):
    new_row = pd.DataFrame([row])
    df = pd.concat([df, new_row], ignore_index=True)
    return df



#   def interpolate_below_length(arr, val, gap):
#       """
#       Interpolate gaps of value, <val> of 
#       length equal to or shorter than <gap> in <arr>
#       
#       :param arr: Array to interpolate
#       :type arr: np.array
#       :param val: Value expected in gaps to interpolate
#       :type val: number
#       :param gap: Maximum gap length to interpolate, gaps of <val> longer than <g> will not be interpolated
#       :type gap: number

#       :return: interpolated array
#       :rtype: np.array
#       """
#       s = np.copy(arr)
#       if np.isnan(val):
#           is_zero = np.isnan(arr)
#       else:
#           is_zero = s == val
#       cumsum = np.cumsum(is_zero).astype('float')
#       diff = np.zeros_like(s)
#       diff[~is_zero] = np.diff(cumsum[~is_zero], prepend=0)
#       for i,d in enumerate(diff):
#           if d <= gap:
#               s[int(i-d):i] = np.nan
#       interp = pd.Series(s).interpolate(method='linear', order=2, axis=0)\
#                            .ffill()\
#                            .bfill()\
#                            .values
#       return interp
