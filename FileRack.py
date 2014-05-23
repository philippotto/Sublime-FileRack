import sublime, sublime_plugin
import os
import datetime
import unicodedata, string


class FileInfo:

	def __init__(self, view):

		self.view = view
		self.isInRack = False
		self.currentName = None


	def generateName(self):

		fileName = self.view.name()

		if fileName:
			fileName = Helper.sanitizeFileName(fileName)

		if not fileName:
			currentDate = datetime.datetime.now().strftime("%I-%M_%d-%m-%y")
			fileName = "untitled - " + currentDate

		fileName += ".txt"

		return fileName


	def renameTo(self, fileName):

		oldFilePath = os.path.join(Helper.getRackPath(), self.currentName)
		newFilePath = os.path.join(Helper.getRackPath(), fileName)

		os.rename(oldFilePath, newFilePath)
		self.currentName = fileName


	def onModify(self):

		contentRegion = sublime.Region(0, self.view.size())
		bufferContent = self.view.substr(contentRegion)

		if not bufferContent:
			if self.isInRack:
				filePath = os.path.join(Helper.getRackPath(), self.currentName)
				self.delete(filePath)
			return

		self.save(bufferContent)


	def save(self, bufferContent):

		self.isInRack = True
		fileName = self.generateName()

		if not self.currentName:
			self.currentName = fileName

		if self.currentName != fileName:
			self.renameTo(fileName)


		# TODO
		# - check if fileName already exists
		# - generate IDs and save to meta file


		filePath = os.path.join(Helper.getRackPath(), fileName)

		if bufferContent:
			with open(filePath, 'w') as f:
				f.write(bufferContent)
		else:
			self.delete(filePath)

		self.scratchView()


	def delete(self, filePath):

		os.remove(filePath)
		self.isInRack = False
		self.currentName = None


	def scratchView(self):

		self.view.set_scratch(True)


	def saveMetaData(self):

		# TODO generate sensible metadata
		# metadata = ...

		with open('index.json', 'w') as outfile:
			json.dump(metadata, outfile, sort_keys = True, indent = 4, ensure_ascii = False)



class EventListener(sublime_plugin.EventListener):

	def on_modified(self, view):

		fileInfo = Helper.getOrConstructFileInfoForView(view)

		# put the buffer into the rack if it isn't a file
		if fileInfo.isInRack or not view.file_name():
			fileInfo.onModify()



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


	def getPathForIndex(self, index):

		fileName = self.items[index]
		return os.path.join(Helper.getRackPath(), fileName)


	def openFile(self, index):

		# TODO opened files should behave as the usual "racked files"
		# this means, that they should get
		# - saved when modified
		# - renamed when they buffer name changes
		# - deleted when they are empty

		# TODO check whether the file is already open

		if index == -1:
			# quick panel was cancelled
			self.transientView.close()
			return

		sublime.active_window().open_file(self.getPathForIndex(index))


	def openFileTransient(self, index):

		self.transientView = sublime.active_window().open_file(self.getPathForIndex(index), sublime.TRANSIENT)



class Helper:

	viewToFileInfoMapping = {}

	def __init__(self):

		pass

	@staticmethod
	def getRackPath():

		# TODO: make the path configurable via settings
		return os.path.join(sublime.packages_path(), "FileRack", "files")


	@staticmethod
	def getOrConstructFileInfoForView(view):

		mapping = Helper.viewToFileInfoMapping
		viewID = view.id()

		if not viewID in mapping.keys():
			mapping[viewID] = FileInfo(view)

		fileInfo = mapping[viewID]
		return fileInfo


	@staticmethod
	def hashSelection(selection):

		return str([region for region in selection])


	def sanitizeFileName(filename):

		validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)
		cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
		return ''.join(chr(c) for c in cleanedFilename if chr(c) in validFilenameChars)

