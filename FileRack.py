import sublime, sublime_plugin
import os
import datetime

class EventListener(sublime_plugin.EventListener):

	def on_selection_modified(self, view):

		pass

	def on_modified(self, view):

		if view.file_name():
			# ignore "real" files
			return

		self.saveView(view)
		self.scratchView(view)


	def saveView(self, view):

		fileName = view.name()

		if not fileName:
			currentDate = datetime.datetime.now().strftime("%I:%M-%d-%m-%y")
			fileName = "untitled - " + currentDate

		fileName += ".txt"

		# TODO
		# check if fileName already exists and whether it is a different one
		# generate IDs and save to meta file
		# handle possible renamings of current file


		contentRegion = sublime.Region(0, view.size())
		bufferContent = view.substr(contentRegion)

		filePath = os.path.join(Helper.getRackPath(), fileName)
		if bufferContent:
			with open(filePath, 'w') as f:
				f.write(bufferContent)
		else:
			os.remove(filePath)

		print(os.path.dirname(__file__))


	def scratchView(self, view):

		view.set_scratch(True)


	def saveMetaData(self):

		# TODO generate sensible metadata
		# metadata = ...

		with open('index.json', 'w') as outfile:
			json.dump(metadata, outfile, sort_keys = True, indent = 4, ensure_ascii = False)




class DisplayFileRack(sublime_plugin.TextCommand):

	def run(self, edit):

		self.items = self.getFiles()

		sublime.active_window().show_quick_panel(
			self.items,
			self.openFile,
			0,
			0,
			self.openFileTransient
		)

	def getFiles(self):

		return [file for file in os.listdir(Helper.getRackPath()) if file.endswith(".txt")]


	def openFile(self, index):

		# TODO opened files should behave as the usual "racked files"
		# this means, that they should get
		# - saved when modified
		# - renamed when they buffer name changes
		# - deleted when they are empty


		fileName = self.items[index]
		filePath = os.path.join(Helper.getRackPath(), fileName)

		sublime.active_window().open_file(filePath)


	def openFileTransient(self, index):

		sublime.active_window().open_file(filePath, sublime.TRANSIENT)



class Helper:

	viewToHelperMap = {}

	def __init__(self):

		pass

	@staticmethod
	def getRackPath:

		return os.path.join(sublime.packages_path(), "FileRack", "files")


	@staticmethod
	def getOrConstructHelperForView(view):

		mapping = Helper.viewToHelperMap
		viewID = view.id()

		if not viewID in mapping.keys():
			mapping[viewID] = Helper()

		helper = mapping[viewID]
		return helper


	@staticmethod
	def hashSelection(selection):

		return str([region for region in selection])
