import datetime
import json


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


class Dataset:
	@classmethod
	def from_json(cls, json_str):
		return cls(json.loads(json_str))

	def __init__(self, data):
		self.data = data
		self.name = data['name']
		self.price_prefix = data.get('price_prefix', '$')
		self.price_suffix = data.get('price_suffix', '')
		self.formulas = data.get('formulas', None)
		self.results = {k: None for k in self.formulas.keys()}
		self.format = data['format']
		self.groups = self.format.keys()
		self.sheets = {}
		for sheet_name, sheet_data in data['sheets'].items():
			for group_name, group_data in zip(self.format.keys(), sheet_data):
				for value_name, value in zip(self.format[group_name], group_data):
					value_type = self.format[group_name][value_name]
					if value_type in ('int', 'float', 'text'):
						# Preserve the type
						pass
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
					else:
						raise ValueError(f'Unknown data type {value_type} in group {group_name} for value {value_name}')
					self.sheets.setdefault(sheet_name, {})
					self.sheets[sheet_name].setdefault(group_name, {})
					self.sheets[sheet_name][group_name][value_name] = value
		self.default = self.sheets.pop('default', None)

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
			self.results[label] = eval(formula, {
				'sheets': self.sheets,
				'current_sheet': current_sheet,
				'results': self.results,
				'price': self.format_price,
				'cell': self.get_cell
			})
