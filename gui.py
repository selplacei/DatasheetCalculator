import datetime
import sys

from PySide2.QtCore import Signal, QDate, QTime, QDateTime
from PySide2.QtWidgets import (
	QMainWindow, QWidget,
	QTabWidget, QLabel, QSpinBox, QDateTimeEdit, QDoubleSpinBox, QLineEdit,
	QTabBar, QDateEdit, QTimeEdit,
	QHBoxLayout, QVBoxLayout, QGridLayout
)
import parser


class MainWindow(QMainWindow):
	# TODO: use the same SingleXViews for different sheets because their structure
	#  is identical and so that tabs don't switch when switching sheets
	# TODO: update the console font
	def __init__(self, parent=None):
		super().__init__(parent)
		with open('/home/selplacei/Projects/DatasheetCalculator/sample.json') as f:
			json_str = f.read()
		dataset_view = DatasetView(parser.Dataset.from_json(json_str))
		self.setCentralWidget(dataset_view)


class DatasetView(QWidget):
	valueChanged = Signal(str, str, str, object)  # sheet, group, value name, value

	def __init__(self, dataset, parent=None):
		super().__init__(parent)
		self.dataset = dataset
		self.tab_bar = QTabBar()
		self.sheet_view = SingleSheetView(
			list(self.dataset.sheets.values())[0],
			self.dataset.price_prefix,
			self.dataset.price_suffix
		)
		self.name_label = QLabel(dataset.name)
		self.formula_view = FormulaView(dataset)

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
		self.setLayout(layout)
		self.tab_bar.currentChanged.connect(self.recompute)
		self.tab_bar.currentChanged.connect(self.update_sheet_view)
		self.valueChanged.connect(self.update_dataset)

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
		return list(self.dataset.sheets.keys())[self.tab_bar.currentIndex()]

	def current_sheet(self):
		return list(self.dataset.sheets.values())[self.tab_bar.currentIndex()]


class FormulaView(QWidget):
	def __init__(self, dataset, parent=None):
		super().__init__(parent)
		self.dataset = dataset
		self.dataset.compute_results(list(self.dataset.sheets.values())[0])
		layout = QVBoxLayout()
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
			elif datatype is parser.Price:
				self.value_widgets.append(SinglePriceView(data_name, value, prefix=price_prefix, suffix=price_suffix))
			elif datatype is datetime.date:
				self.value_widgets.append(SingleDateView(data_name, value))
			elif datatype is datetime.time:
				self.value_widgets.append(SingleTimeView(data_name, value))
			elif datatype is datetime.datetime:
				self.value_widgets.append(SingleDateTimeView(data_name, value))
			elif datatype is parser.Timedelta:
				self.value_widgets.append(SingleTimedeltaView(data_name, value))
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
		self._timedelta = parser.Timedelta(fmt=fmt)
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
		self._timedelta = parser.Timedelta(fmt=self.fmt, seconds=total_seconds)
		if update_widgets:
			self.update_widgets()

	def get_value(self):
		return self._timedelta

	def set_value(self, value):
		# This does not update ``fmt`` even if the value's fmt is different.
		self._timedelta = parser.Timedelta(fmt=self.fmt, seconds=value.total_seconds())
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
		if isinstance(value, parser.Timedelta):
			# Update the format as well as the time
			self.fmt = value.fmt
			self.value_widget.set_fmt(value.fmt)
		self.value_widget.set_value(value)
