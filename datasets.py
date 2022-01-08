import datetime
import itertools
import json
import sys
# TODO: use the "ambiguous time string" mechanism for single date/time/datetime values


class Price(float):
	...


class Timedelta(datetime.timedelta):
	def __new__(cls, *args, fmt, **kwargs):
		self = super().__new__(cls, *args, **kwargs)
		self.fmt = fmt
		return self

	def fmt_values(self):
		values = {}
		seconds = self.total_seconds()
		for c in sorted(self.fmt, key='dhms'.index):
			coefficient = {
				's': 1, 'm': 60, 'h': 60*60, 'd': 60*60*24
			}[c]
			if seconds / coefficient >= 1:
				values[c], seconds = divmod(seconds, coefficient)
			else:
				values[c] = 0
		return values


class Calcdelta:
	def __init__(self, start, end):
		self.start = start
		self.end = end
		if not (isinstance(end, type(start)) or isinstance(start, type(end))):
			raise TypeError(
				f'The value types passed to Calcdelta must be equivalent (got {type(start)} and {type(end)})'
			)
		self.data_type = type(start)

	@property
	def delta(self):
		return calculate_delta(self.start, self.end)


def calculate_delta(arg1, arg2):
	"""
	Calculates and returns a `datetime.timedelta` object representing
	the difference between arg1 and arg2. Arguments must be either both
	`datetime.date`, both `datetime.time`, or both `datetime.datetime`.
	The difference is absolute, so the order of the arguments doesn't matter.
	"""
	if arg1 > arg2:
		arg1, arg2 = arg2, arg1
	if isinstance(arg1, datetime.date) and isinstance(arg1, datetime.date):
		return (
			datetime.datetime(arg2.year, arg2.month, arg2.day)
			- datetime.datetime(arg1.year, arg1.month, arg1.day)
		)
	if isinstance(arg1, datetime.time) and isinstance(arg1, datetime.time):
		return (
			datetime.datetime(1, 1, 1, arg2.hour, arg2.minute, arg1.second)
			- datetime.datetime(1, 1, 1, arg1.hour, arg1.minute, arg1.second)
		)
	if isinstance(arg1, datetime.datetime) and isinstance(arg1, datetime.datetime):
		return arg2 - arg1
	raise TypeError(
		f'Cannot calculate delta between values of types '
		f'{type(arg1)} and {type(arg2)} because they are not equivalent'
	)


class Dataset:
	@classmethod
	def from_json(cls, json_str):
		return cls(json.loads(json_str))

	def __init__(self, data):
		self._data = data
		self.name = data['name']
		self.price_prefix = data.get('price_prefix', '$')
		self.price_suffix = data.get('price_suffix', '')
		self.formulas = data.get('formulas', None)
		self.results = {k: None for k in self.formulas.keys()}
		self.format = data['format']
		self.special_format = data['special']
		self.groups = self.format.keys()
		self.sheets = {}
		for sheet_name, sheet_data in data['sheets'].items():
			format_spec = self.special_format if sheet_name == '__special__' else self.format
			for group_name, group_data in zip(format_spec.keys(), sheet_data):
				for value_name, value in zip(format_spec[group_name], group_data):
					value_type = format_spec[group_name][value_name]
					if value_type in ('int', 'text'):
						# Preserve the type
						pass
					elif value_type == 'float':
						value = float(value)
					elif value_type == 'price':
						value = Price(value)
					elif value_type == 'date':
						value = datetime.date(*map(int, value.split('-')))
					elif value_type == 'time':
						value = datetime.time(*map(int, value.split(':')))
					elif value_type == 'datetime':
						value = datetime.datetime.fromisoformat(value)
					elif value_type == 'timedelta':
						subvalues = {'d': 0, 'h': 0, 'm': 0, 's': 0}
						parse_temp = ''
						for c in value:
							if c.isdigit():
								parse_temp += c
							else:
								subvalues[c] = int(parse_temp)
								parse_temp = ''
						value = Timedelta(
							fmt=''.join(filter(str.isalpha, value)),
							days=subvalues['d'],
							hours=subvalues['h'],
							minutes=subvalues['m'],
							seconds=subvalues['s']
						)
					elif value_type.startswith('calcdelta'):
						data_type = {
							'd': datetime.date,
							't': datetime.time,
							'dt': datetime.datetime
						}[value_type.split('_')[1]]
						args = []
						for v in value:
							args.append(data_type.fromisoformat(v))
						value = Calcdelta(*args)
					else:
						raise ValueError(
							f'Unknown data type {value_type} in group {group_name} for value {value_name}'
						)
					self.sheets.setdefault(sheet_name, {})
					self.sheets[sheet_name].setdefault(group_name, {})
					self.sheets[sheet_name][group_name][value_name] = value
		self.default = self.sheets.pop('__default__', None) or self.generate_default()
		self.special = self.sheets.pop('__special__', None)

	def generate_default(self):
		sheet = {}
		for group_name, group_d in self.format.items():
			sheet[group_name] = {}
			for val_name, val_type in group_d.items():
				sheet[group_name][val_name] = {
					'text': '',
					'int': 0,
					'float': 0.0,
					'price': Price(0),
					'date': datetime.date.today(),
					'time': datetime.time(),
					'datetime': datetime.datetime.combine(datetime.date.today(), datetime.time()),
					'timedelta': Timedelta(fmt='dhms', seconds=0),
					'calcdelta_d': Calcdelta(
						datetime.date.today(), datetime.date.today()
					),
					'calcdelta_t': Calcdelta(
						datetime.time(), datetime.time()
					),
					'calcdelta_dt': Calcdelta(
						datetime.datetime.combine(datetime.date.today(), datetime.time()),
						datetime.datetime.combine(datetime.date.today(), datetime.time())
					)
				}[val_type]
		return sheet

	def format_price(self, value):
		return f'{self.price_prefix}{round(float(value), 2)}{self.price_suffix}'

	@staticmethod
	def get_cell(sheet, cell_id):
		group = 0
		group_digits = []
		for c in cell_id:
			if c.isdigit():
				break
			group_digits.append(ord(c) - 64)
		for p, d in enumerate(group_digits):
			group += d * 25 ** p
		cell = int(cell_id[len(group_digits):])
		if group < 1 or cell < 1:
			raise ValueError(f'Invalid cell ID: {cell_id}')
		return list(list(sheet.values())[group - 1].values())[cell - 1]

	def compute_results(self, current_sheet):
		for label, formula in self.formulas.items():
			try:
				self.results[label] = eval(formula, {
					'sheets': self.sheets,
					'current': current_sheet,
					'special': self.special,
					'results': self.results,
					'price': self.format_price,
					'cell': self.get_cell,
					'delta': calculate_delta,
					'itertools': itertools,
					'datetime': datetime
				})
			except Exception as e:
				self.results[label] = type(e).__name__ + ' (see output)'
				sys.stderr.write(str(e) + '\n')

	def to_json(self):
		return json.dumps(self)


class DatasetEncoder(json.JSONEncoder):
	def default(self, o):
		if isinstance(o, dict):
			new_dict = {}
			for k, v in o:
				new_dict[k] = self.default(v)
			return super().default(new_dict)
		if isinstance(o, datetime.date):
			return o.strftime('%Y-%M-%d')
		if isinstance(o, datetime.time):
			return o.strftime('%H:%M:%S')
		if isinstance(o, datetime.datetime):
			return o.strftime('%Y-%M-%d %H:%M:%S')
		if isinstance(o, Timedelta):
			return ''.join(f'{u}{v}' for u, v in o.fmt_values())
		if isinstance(o, datetime.timedelta):
			return self.default(Timedelta(fmt='dhms', seconds=o.total_seconds()))
