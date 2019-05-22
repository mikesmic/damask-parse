"""`damask_parse.readers.py`"""

from pathlib import Path

import pandas
import re
import numpy as np

__all__ = [
    'get_num_header_lines',
    'read_damask_table',
]


def get_num_header_lines(path):
    """Get the number of header lines from a file produced by DAMASK.

    Parameters
    ----------
    path : str or Path
        Path to a DAMASK-generated file that contains a header.

    Returns
    -------
    num : int
        Number of header lines in the DAMASK-generated file.

    """

    path = Path(path)
    with path.open() as handle:
        num = int(handle.read(1))

    return num


def read_damask_table(path, use_dataframe=False, combine_array_columns=True,
                      ignore_duplicate_cols=False):
    """Read the data from a DAMASK-generated ASCII table file, as generated by
    the DAMASK post-processing command named `postResults`.

    Parameters
    ----------
    path : str or Path
        Path to the DAMASK table file.
    use_dataframe : bool, optional
        If True, a Pandas DataFrame is returned. Otherwise, a dict of Numpy
        arrays is returned. By default, set to False.        
    combine_array_columns : bool, optional
        If True, columns that represent elements of an array (e.g. stress) are
        combined into a single column. By default, set to True.
    ignore_duplicate_cols : bool, optional
        If True, duplicate columns (as detected by the `mangle_dupe_cols`
        option of `pandas_read_csv` function) are ignored. Otherwise, an
        exception is raised.

    Returns
    -------
    outputs : dict
        The data in the table file, represented either as a Pandas DataFrame
        (if `use_dataframe` is True) or a dict of Numpy arrays (if
        `use_dataframe` if False).

    """

    arr_shape_lookup = {
        12: [4, 3],
        9: [3, 3],
        3: [3],
        4: [4],
    }

    header_num = get_num_header_lines(path)
    df = pandas.read_csv(str(path), delim_whitespace=True, header=header_num)

    if not ignore_duplicate_cols:
        if np.any(df.columns.str.replace(r'(\.\d+)$', '').duplicated()):
            msg = ('It appears there are duplicated columns in the table.')
            raise ValueError(msg)

    arr_sizes = None
    if combine_array_columns or not use_dataframe:
        # Find number of elements for each "array" column:
        arr_sizes = {}
        for header in df.columns.values:
            match = re.match(r'([0-9]+)_(.+)', header)
            if match:
                arr_name = match.group(2)
                if arr_name in arr_sizes:
                    arr_sizes[arr_name] += 1
                else:
                    arr_sizes.update({
                        arr_name: 1
                    })

        # Check for as yet "unsupported" array dimensions:
        bad_num_elems = set(arr_sizes.values()) - set(arr_shape_lookup.keys())
        if len(bad_num_elems) > 0:
            msg = (
                '"Array" columns must have one of the following number of '
                'elements: {}. However, there are columns with the following '
                'numbers of elements: {}'.format(
                    list(arr_shape_lookup.keys()), list(bad_num_elems)
                )
            )
            raise ValueError(msg)

    if combine_array_columns:
        # Add arrays as single columns:
        for arr_name, arr_size in arr_sizes.items():
            arr_idx = [f'{i}_{arr_name}' for i in range(1, arr_size + 1)]
            df[arr_name] = df[arr_idx].values.tolist()
            # Remove individual array columns:
            df = df.drop(arr_idx, axis=1)

    outputs = df

    if not use_dataframe:
        # Transform each column into a Numpy array:
        arrays = {}
        for header in df.columns.values:
            val = np.array(df[header])

            if header in arr_sizes:
                shp = tuple([-1] + arr_shape_lookup[arr_sizes[header]])
                val = np.array([*df[header]]).reshape(shp)

            arrays.update({
                header: val
            })
            outputs = arrays

    return outputs
