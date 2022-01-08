import datetime
import sys

from PySide2.QtCore import Signal, QDate, QTime, QDateTime, Qt
from PySide2.QtWidgets import (
	QMainWindow, QWidget,
	QTabWidget, QLabel, QSpinBox, QDateTimeEdit, QDoubleSpinBox, QLineEdit,
	QTabBar, QDateEdit, QTimeEdit, QPushButton, QInputDialog,
	QHBoxLayout, QVBoxLayout, QGridLayout
)
import datasets


class MainWindow(QMainWindow):
	# TODO: use the same SingleXViews for different sheets because their structure
	#  is identical and so that tabs don't switch when switching sheets
	# TODO: update the console font
	def __init__(self, parent=None):
		super().__init__(parent)
		#with open('/home/selplacei/Projects/DatasheetCalculator/sample.json') as f:
		with open('/home/selplacei/Documents/mom_work_2021.json') as f:
			json_str = f.read()
		dataset_view = DatasetView(datasets.Dataset.from_json(json_str))
		self.setCentralWidget(dataset_view)


class DatasetView(QWidget):
	valueChanged = Signal(str, str, str, object)  # sheet, group, value name, value

	def __init__(self, dataset, parent=None):
		super().__init__(parent)
		self.dataset = dataset
		self.tab_bar = QTabBar()
		self.sheet_view = SingleSheetView(
			next(iter(self.dataset.sheets.values()), None),
			self.dataset.price_prefix,
			self.dataset.price_suffix
		)
		self.name_label = QLabel(dataset.name)
		self.formula_view = FormulaView(dataset)
		self.extra_buttons = ExtraButtons()

		self.sheet_view.valueChanged.connect(lambda g, n, v: self.valueChanged.emit(
			self.current_sheet_name(), g, n, v
		))
		for sheet_name in self.dataset.sheets.keys():
			self.tab_bar.addTab(sheet_name)

		layout = QVBoxLayout()
		layout.addWidget(self.name_label)
		layout.addWidget(self.formula_view)
		layout.addWidget(self.sheet_view)
		layout.addWidget(self.tab_bar)
		layout.addWidget(self.extra_buttons)
		self.setLayout(layout)
		self.tab_bar.currentChanged.connect(self.recompute)
		self.tab_bar.currentChanged.connect(self.update_sheet_view)
		self.valueChanged.connect(self.update_dataset)
		self.extra_buttons.createSheet.connect(lambda: self.create_sheet(f'Sheet {self.tab_bar.count() + 1}'))
		self.extra_buttons.duplicateSheet.connect(lambda: self.duplicate_sheet(
			self.tab_bar.currentIndex()
		))
		self.extra_buttons.renameSheet.connect(self.user_rename_sheet)

	def update_dataset(self, sheet, group, name, value, recompute=True):
		self.dataset.sheets[sheet][group][name] = value
		if recompute:
			self.recompute()

	def recompute(self):
		self.dataset.compute_results(self.current_sheet())
		self.formula_view.update()

	def update_sheet_view(self):
		self.sheet_view.set_value(self.current_sheet())

	def current_sheet_name(self):
		try:
			return list(self.dataset.sheets.keys())[self.tab_bar.currentIndex()]
		except IndexError:
			return None

	def current_sheet(self):
		try:
			return list(self.dataset.sheets.values())[self.tab_bar.currentIndex()]
		except IndexError:
			return None

	def set_current_sheet(self, index):
		# Negative indices are supported
		index = index % self.tab_bar.count()
		self.tab_bar.setCurrentIndex(index)

	def find_non_duplicate_name(self, name, exist_ok=True):
		if name in self.dataset.sheets:
			if exist_ok:
				i = 2
				n = name
				while name in self.dataset.sheets:
					name = f'{n} ({i})'
					i += 1
			else:
				raise ValueError(f'The sheet {name} already exists in the dataset')
		return name

	def create_sheet(self, name, switch=True, exist_ok=True):
		name = self.find_non_duplicate_name(name, exist_ok)
		self.dataset.sheets[name] = self.dataset.default.copy()
		self.tab_bar.addTab(name)
		if switch:
			self.set_current_sheet(-1)

	def duplicate_sheet(self, index, switch=True, exist_ok=True):
		name, sheet = list(self.dataset.sheets.items())[index]
		name += ' (copy)'
		name = self.find_non_duplicate_name(name, exist_ok)
		self.dataset.sheets[name] = sheet.copy()
		self.tab_bar.addTab(name)
		if switch:
			self.set_current_sheet(-1)

	def user_rename_sheet(self):
		result, ok = QInputDialog().getText(
			self, "Rename sheet", "New sheet name:", text=self.current_sheet_name()
		)
		if ok:
			self.rename_sheet(self.tab_bar.currentIndex(), result)

	def rename_sheet(self, index, result, exist_ok=True):
		new_sheets = list(self.dataset.sheets.items())
		previous, sheet = new_sheets[index]
		result = self.find_non_duplicate_name(result, exist_ok)
		self.tab_bar.setTabText(index, result)
		new_sheets[index] = (result, sheet)
		self.dataset.sheets = dict(new_sheets)


class ExtraButtons(QWidget):
	createSheet = Signal()
	duplicateSheet = Signal()
	renameSheet = Signal()

	def __init__(self, parent=None):
		super().__init__(parent)
		create_sheet_btn = QPushButton('Add blank sheet')
		duplicate_sheet_btn = QPushButton('Duplicate sheet')
		rename_sheet_btn = QPushButton('Rename sheet')

		layout = QHBoxLayout()
		layout.addWidget(create_sheet_btn)
		layout.addWidget(duplicate_sheet_btn)
		layout.addWidget(rename_sheet_btn)
		self.setLayout(layout)

		create_sheet_btn.clicked.connect(self.createSheet.emit)
		duplicate_sheet_btn.clicked.connect(self.duplicateSheet.emit)
		rename_sheet_btn.clicked.connect(self.renameSheet.emit)


class FormulaView(QWidget):
	def __init__(self, dataset, parent=None):
		super().__init__(parent)
		self.dataset = dataset
		if self.dataset.sheets:
			self.dataset.compute_results(list(self.dataset.sheets.values())[0])
		layout = QGridLayout()
		for name, result in self.dataset.results.items():
			layout.addWidget(QLabel(f'{name}: {result}'))
		self.setLayout(layout)

	def update(self):
		for i, (name, result) in enumerate(self.dataset.results.items()):
			self.layout().itemAt(i).widget().setText(f'{name}: {result}')


class SingleSheetView(QTabWidget):
	valueChanged = Signal(str, str, object)

	def __init__(self, sheet, price_prefix=None, price_suffix=None, parent=None):
		super().__init__(parent)
		sheet = sheet or {}
		for group_name, group_value in sheet.items():
			tab = SingleGroupView(group_name, group_value, price_prefix, price_suffix)
			self.addTab(tab, group_name)
			tab.valueChanged.connect(lambda n, v, t=tab: self.valueChanged.emit(t.name, n, v))

	def set_value(self, sheet):
		# Assuming that the sheet has the same groups and order
		for i, group_value in enumerate(sheet.values()):
			self.widget(i).set_value(group_value)


class SingleGroupView(QWidget):
	valueChanged = Signal(str, object)

	def __init__(self, name, group, price_prefix=None, price_suffix=None, parent=None):
		super().__init__(parent)
		self.name = name
		self.value_widgets = []
		for data_name, value in group.items():
			# Not using isinstance to avoid subclass-related ambiguities and because json has consistent types
			datatype = type(value)
			if datatype is int:
				self.value_widgets.append(SingleIntView(data_name, value))
			elif datatype is float:
				self.value_widgets.append(SingleFloatView(data_name, value))
			elif datatype is datasets.Price:
				self.value_widgets.append(SinglePriceView(data_name, value, prefix=price_prefix, suffix=price_suffix))
			elif datatype is datetime.date:
				self.value_widgets.append(SingleDateView(data_name, value))
			elif datatype is datetime.time:
				self.value_widgets.append(SingleTimeView(data_name, value))
			elif datatype is datetime.datetime:
				self.value_widgets.append(SingleDateTimeView(data_name, value))
			elif datatype is datasets.Timedelta:
				self.value_widgets.append(SingleTimedeltaView(data_name, value))
			elif datatype is datasets.Calcdelta:
				self.value_widgets.append(
					{
						datetime.date: SingleCalcdelta_dView,
						datetime.time: SingleCalcdelta_tView,
						datetime.datetime: SingleCalcdelta_dtView
					}[value.data_type](data_name, value)
				)
			else:
				# Assume a value that can be represented by text
				self.value_widgets.append(SingleValueView(data_name, value))

		layout = QGridLayout()
		for widget in self.value_widgets:
			layout.addWidget(widget)
			widget.valueChanged.connect(lambda v, w=widget: self.valueChanged.emit(w.name, v))
		self.setLayout(layout)

	def set_value(self, group):
		# Assuming that the order and type of values is the same
		for i, value in enumerate(group.values()):
			self.value_widgets[i].set_value(value)


class SingleValueView(QWidget):
	valueChanged = Signal(object)

	def __init__(self, name, value, parent=None):
		super().__init__(parent)
		self.name = name
		self.value_widget = None
		self.make_value_widget()
		self.set_value(value)

		self.label = QLabel(self.name)
		layout = QHBoxLayout()
		layout.addWidget(self.label)
		layout.addWidget(self.value_widget)
		self.setLayout(layout)

	def make_value_widget(self):
		# To be overridden in subclasses
		self.value_widget = QLineEdit()
		self.value_widget.textChanged.connect(self.valueChanged.emit)

	def get_value(self):
		# To be overridden in subclasses
		return self.value_widget.text()

	def set_value(self, value):
		# To be overridden in subclasses
		self.value_widget.setText(str(value))


class SingleIntView(SingleValueView):
	def make_value_widget(self):
		self.value_widget = QSpinBox()
		self.value_widget.setMaximum(2**16)
		self.value_widget.setMinimum(-(2**16-1))
		self.value_widget.valueChanged.connect(self.valueChanged.emit)

	def get_value(self):
		return self.value_widget.value()

	def set_value(self, value):
		self.value_widget.setValue(value)


class SingleFloatView(SingleValueView):
	def make_value_widget(self):
		self.value_widget = QDoubleSpinBox()
		self.value_widget.setMaximum(2**16)
		self.value_widget.setMinimum(-(2**16-1))
		self.value_widget.valueChanged.connect(self.valueChanged.emit)

	def get_value(self):
		return self.value_widget.value()

	def set_value(self, value):
		self.value_widget.setValue(value)


class SinglePriceView(SingleFloatView):
	def __init__(self, *args, prefix=None, suffix=None, **kwargs):
		self.prefix = prefix or '$'
		self.suffix = suffix
		super().__init__(*args, **kwargs)

	def make_value_widget(self):
		self.value_widget = QDoubleSpinBox()
		self.value_widget.setMaximum(2**16)
		self.value_widget.setMinimum(-(2**16-1))
		self.value_widget.valueChanged.connect(self.valueChanged.emit)
		self.value_widget.setPrefix(self.prefix)
		self.value_widget.setSuffix(self.suffix)
		self.value_widget.setDecimals(2)


class SingleDateView(SingleValueView):
	def make_value_widget(self):
		self.value_widget = QDateEdit()
		self.value_widget.setDisplayFormat('yyyy-MM-dd')
		self.value_widget.setCalendarPopup(True)
		self.value_widget.dateChanged.connect(lambda v: self.valueChanged.emit(v.toPython()))

	def get_value(self):
		return self.value_widget.date().toPython()

	def set_value(self, value):
		self.value_widget.setDate(QDate(value.year, value.month, value.day))


class SingleTimeView(SingleValueView):
	def make_value_widget(self):
		self.value_widget = QTimeEdit()
		self.value_widget.setDisplayFormat('HH:mm:ss')
		self.value_widget.timeChanged.connect(lambda v: self.valueChanged.emit(v.toPython()))

	def get_value(self):
		return self.value_widget.time().toPython()

	def set_value(self, value):
		self.value_widget.setTime(QTime(value.hour, value.minute, value.second))


class SingleDateTimeView(SingleValueView):
	def make_value_widget(self):
		self.value_widget = QDateTimeEdit()
		self.value_widget.setDisplayFormat('yyyy-MM-dd HH:mm:ss')
		self.value_widget.setCalendarPopup(True)
		self.value_widget.dateTimeChanged.connect(lambda v: self.valueChanged.emit(v.toPython()))

	def get_value(self):
		return self.value_widget.dateTime().toPython()

	def set_value(self, value):
		self.value_widget.setDateTime(QDateTime(
			QDate(value.year, value.month, value.day),
			QTime(value.hour, value.minute, value.second)
		))


class TimedeltaWidget(QWidget):
	valueChanged = Signal(datetime.timedelta)

	def __init__(self, fmt, parent=None):
		super().__init__(parent)
		self._timedelta = None
		self._fmt = fmt
		self.widget_pairs = {}
		self.setLayout(QHBoxLayout())
		self.set_fmt(fmt)

	def set_fmt(self, fmt):
		self._timedelta = datasets.Timedelta(fmt=fmt)
		self.fmt = fmt
		for w1, w2 in self.widget_pairs.values():
			w1.deleteLater()
			w2.deleteLater()
		self.widget_pairs = {}
		for c in fmt:
			self.widget_pairs[c] = (
				QLabel({
					'd': 'Days:',
					'h': 'Hours:',
					'm': 'Minutes:',
					's': 'Seconds:'
				}[c]),
				QSpinBox()
			)
		for label, spinbox in self.widget_pairs.values():
			spinbox.valueChanged.connect(lambda _: self.update_timedelta(update_widgets=True))
			spinbox.setMaximum(2**16)
			spinbox.setMinimum(-1)
			self.layout().addWidget(label)
			self.layout().addWidget(spinbox)

	def update_widgets(self):
		new_values = self._timedelta.fmt_values()
		for c, (_, w) in reversed(list(self.widget_pairs.items())):
			# Updating the widgets will cause valueChanged to be emitted, which will call this function again
			# We reverse the list to avoid an infinite loop of ever-increasing values
			w.setValue(new_values[c])

	def update_timedelta(self, update_widgets=False):
		total_seconds = 0
		for c, n in self.widget_pairs.items():
			total_seconds += n[1].value() * {'s': 1, 'm': 60, 'h': 60*60, 'd': 60*60*24}[c]
		self._timedelta = datasets.Timedelta(fmt=self.fmt, seconds=total_seconds)
		if update_widgets:
			self.update_widgets()

	def get_value(self):
		return self._timedelta

	def set_value(self, value):
		# This does not update ``fmt`` even if the value's fmt is different.
		self._timedelta = datasets.Timedelta(fmt=self.fmt, seconds=value.total_seconds())
		self.update_widgets()


class SingleTimedeltaView(SingleValueView):
	def __init__(self, name, value, **kwargs):
		self.fmt = value.fmt
		super().__init__(name, value, **kwargs)

	def make_value_widget(self):
		self.value_widget = TimedeltaWidget(self.fmt)
		self.value_widget.valueChanged.connect(self.valueChanged.emit)

	def get_value(self):
		return self.value_widget.get_value()

	def set_value(self, value):
		if isinstance(value, datasets.Timedelta):
			# Update the format as well as the time
			self.fmt = value.fmt
			self.value_widget.set_fmt(value.fmt)
		self.value_widget.set_value(value)


class SingleCalcdeltaView(SingleValueView):
	value_type = NotImplemented
	widget_type = NotImplemented
	signal_name = NotImplemented

	def __init__(self, name, value, **kwargs):
		super().__init__(name, value, **kwargs)
		self.valueChanged.connect(lambda _: self.update_limits())

	def make_value_widget(self):
		# Some absolutely terrible code here, and in this whole "3 things at once" thing
		# in general. I was just too lazy to write so much boilerplate.
		self.value_widget = QWidget()
		layout = QHBoxLayout()
		l_start = QLabel('Start:')
		w_start = self.widget_type()
		l_end = QLabel('End:')
		w_end = self.widget_type()
		getattr(w_start, self.signal_name).connect(lambda _: self.valueChanged.emit(self.get_value()))
		getattr(w_end, self.signal_name).connect(lambda _: self.valueChanged.emit(self.get_value()))
		l_start.setAlignment(Qt.AlignRight)
		l_end.setAlignment(Qt.AlignRight)
		w_start.setCalendarPopup(True)
		w_end.setCalendarPopup(True)
		layout.addWidget(l_start)
		layout.addWidget(w_start)
		layout.addWidget(l_end)
		layout.addWidget(w_end)
		self.value_widget.setLayout(layout)

	def _w_start(self):
		return self.value_widget.layout().itemAt(1).widget()

	def _w_end(self):
		return self.value_widget.layout().itemAt(3).widget()

	def get_start(self):
		raise NotImplemented

	def get_end(self):
		raise NotImplemented

	def set_start(self, value):
		raise NotImplemented

	def set_end(self, value):
		raise NotImplemented

	def get_value(self):
		return datasets.Calcdelta(self.get_start(), self.get_end())

	def set_value(self, value):
		# The value must be a 2-item sequence corresponding to the two elements
		# or a Calcdelta instance.
		if isinstance(value, datasets.Calcdelta):
			value = value.start, value.end
		if not isinstance(value[0], self.value_type):
			raise TypeError(
				f'Attempted to set non-matching value type {type(value[0])} to {type(self)} which only accepts {self.value_type}'
			)
		self.set_start(value[0])
		self.set_end(value[1])

	def update_limits(self):
		if self.get_start() > self.get_end():
			self.set_end(self.get_start())


class SingleCalcdelta_dView(SingleCalcdeltaView):
	value_type = datetime.date
	widget_type = QDateEdit
	signal_name = 'dateChanged'

	def get_start(self):
		return self._w_start().date().toPython()

	def get_end(self):
		return self._w_end().date().toPython()

	def set_start(self, value):
		self._w_start().setDate(QDate(
			value.year, value.month, value.day
		))

	def set_end(self, value):
		self._w_end().setDate(QDate(
			value.year, value.month, value.day
		))

	def update_limits(self):
		super().update_limits()
		current_start = self.get_start()
		current_end = self.get_end()
		self._w_start().setMaximumDate(QDate(
			current_end.year, current_end.month, current_end.day
		))
		self._w_end().setMinimumDate(QDate(
			current_start.year, current_start.month, current_start.day
		))


class SingleCalcdelta_tView(SingleCalcdeltaView):
	value_type = datetime.time
	widget_type = QTimeEdit
	signal_name = 'timeChanged'

	def get_start(self):
		return self._w_start().time().toPython()

	def get_end(self):
		return self._w_end().time().toPython()

	def set_start(self, value):
		self._w_start().setTime(QTime(
			value.hour, value.minute, value.second
		))

	def set_end(self, value):
		self._w_end().setTime(QTime(
			value.hour, value.minute, value.second
		))

	def update_limits(self):
		super().update_limits()
		current_start = self.get_start()
		current_end = self.get_end()
		self._w_start().setMaximumTime(QTime(
			current_end.hour, current_end.minute, current_end.second
		))
		self._w_end().setMinimumTime(QTime(
			current_start.hour, current_start.minute, current_start.second
		))


class SingleCalcdelta_dtView(SingleCalcdeltaView):
	value_type = datetime.datetime
	widget_type = QDateTimeEdit
	signal_name = 'dateTimeChanged'

	def get_start(self):
		return self._w_start().dateTime().toPython()

	def get_end(self):
		return self._w_end().dateTime().toPython()

	def set_start(self, value):
		self._w_start().setDate(QDate(
			value.hour, value.minute, value.second
		))
		self._w_start().setTime(QTime(
			value.hour, value.minute, value.second
		))

	def set_end(self, value):
		self._w_end().setDate(QDate(
			value.hour, value.minute, value.second
		))
		self._w_end().setTime(QTime(
			value.hour, value.minute, value.second
		))

	def update_limits(self):
		super().update_limits()
		current_start = self.get_start()
		current_end = self.get_end()
		self._w_start().setMaximumDate(QDate(
			current_end.year, current_end.month, current_end.day
		))
		self._w_end().setMinimumDate(QDate(
			current_start.year, current_start.month, current_start.day
		))
		self._w_start().setMaximumTime(QTime(
			current_end.hour, current_end.minute, current_end.second
		))
		self._w_end().setMinimumTime(QTime(
			current_start.hour, current_start.minute, current_start.second
		))
