# Dataset format
The format of raw dataset files is described here, which can be used to edit them directly.
This is also required to create new datasets or change their structure.

Datasets use the JSON file format for storage. Of course, it's possible to make your own dict
with a compatible structure and pass it to the constructor of `Dataset`.

For an example dataset, see the `sample.json` file in this repository.

## Root
The root object of a dataset is a dictionary. It contains the following elements:

- `name` (string, required): Name of the dataset, displayed in the application's title.
- `price_prefix` (string, optional): Prefix for all price values. `$` by default.
- `price_suffix` (string, optional): Suffix for all price values. Empty by default.
- `format` (dictionary, required): Structure and human-readable names for values in the data.
- `formulas` (dictionary, optional): Values to calculate from the data and display above the dataset itself.
- `sheets` (dictionary, optional): The actual data. Although technically not required, datasets without it are useless.

## The `format` value
This value describes how data in the dataset is structured and how to display it.
Specifically, it tells which groups (tabs above displayed values) exist, how many values are in each one,
and for each value, its human-readable description and its value type (e.g. an integer, a time, or text).

The value is a dictionary where each element is the name of a group mapped to its contents. The order of these groups
is preserved when loading the dataset. The value of each group is another dictionary whose each element is the
name of a value mapped to its type. The following types are recognized (described values are stored in `sheets`):

- `text`: A string of text.
- `int`: An integer.
- `float`: A decimal number.
- `price`: A decimal number that when displayed is rounded to 2 places and with the appropriate prefix and suffix added.
- `date`: A date in ISO 8601 format, i.e. YYYY-MM-DD (for example, `2022-01-05`). MM and DD must not exceed 
  the maximum possible actual values in the given month and year. When loaded, it's converted to `datetime.date`.
- `time`: A time of day in the format HH:MM:SS (for example, `21:50:00`) or HH:MM (for example, `06:00`). HH must be less than 24; MM and SS must both be less than 60.
  When loaded, it's converted to `datetime.time`.
- `datetime`: A time and date in a subset of the ISO 8601 format, specifically YYYY-MM-DD HH:MM:SS (for example, `2022-01-05 21:50:00`).
  The values have the same restrictions as `date` and `time`. When loaded, it's converted to `datetime.datetime`.
- `timedelta`: A duration of time in the format XXdXXhXXmXXs, with each element optional, though at least one is required
  (for example, `2d15h` or `1h25m33s`). Unlike `time`, the total may exceed 24 hours, and each element has an unlimited value.
  When loaded, it's converted to `datetime.timedelta`, but only elements present in the raw value are displayed (exceeding their normal values if needed).
- `calcdelta_d`, `calcdelta_t`, `calcdelta_dt`: Two `date`, `time`, or `datetime` values (stored as a list; both must be of the same type), representing a start time and an end time. When loaded, it's converted to one of the `Calcdelta` classes, which has the attributes `type`, `start`, `end`, and `delta`.

## The `formulas` value
This value describes which values (if any) to calculate and display above the data, and how to calculate them.
It is a dictionary where each key is a human-readable name of the formula and the value is a Python expression that calculates
the corresponding value. All built-in variable are available, plus the libraries `itertools` and `datetime`, as well as the following local variables:

- `sheets`: The value of `dataset.sheets` where `dataset` is the currently loaded Dataset object. It is a dictionary
  where each key is the name of a datasheet and the value is a structure very similar to `format`, except instead of
  value types, it contains actual values (already converted to matching Python types). Note that values of type `Price`
  act as regular floats; there's no need to remove their prefix or suffix.
- `price`: If you'd like to display a price according to the dataset configuration, this function converts a float to a price string.
- `current_sheet`: The currently displayed datasheet (structure identical to an element of `sheets`).
- `results`: Values calculated by previously specified formulas in a dictionary where the keys are formula names.
- `cell`: This is a shorthand way to retrieve values from a sheet. This function takes a sheet as its first argument
  and a cell ID as the second. The ID is one or more capital letters followed by one or more digits; the letter(s) represent
  a group, with A being the first group, B being the second, etc., until Z - it's then followed by AA, AB, and so on;
  the number represents a value in that group (note that they start at 1, not 0). Invalid cell IDs will raise an error.
- `delta`: Calculates the difference (in the form of a `timedelta`) between two dates, two times, or two datetimes. In either case, this is stored as a pair of strings with formats identical to the corresponding formats listed above.

## The `sheets` value
This value contains the actual data in the dataset.
It is a dictionary where datasheet names are mapped to datasheets.
Each datasheet is a list with values corresponding to the groups and value types described in the matching `format` sections, all in the same order.
Values other than those of type `int`, `double`, and `price` should be stored as strings (i.e. quoted).
