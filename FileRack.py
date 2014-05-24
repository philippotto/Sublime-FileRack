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

		# take maximal 15 characters of the first line (stripped)
		fileName = self.view.substr(sublime.Region(0, 15)).split("\n")[0].strip()

		if fileName:
			fileName = Helper.sanitizeFileName(fileName)

		if not fileName:
			currentDate = datetime.datetime.now().strftime("%I-%M_%d-%m-%y")
			fileName = "untitled - " + currentDate

		fileName = self.disambiguateFileName(fileName)
		fileName += Helper.getFileType()

		return fileName


	def disambiguateFileName(self, fileName):

		originalFileName = fileName
		fileNameWithType = lambda: fileName + Helper.getFileType()

		isSameFile = lambda: self.currentName != fileNameWithType()
		fileNameAlreadyExists = lambda: os.path.exists(os.path.join(Helper.getRackPath(), fileNameWithType()))

		disambiguation = 0

		while isSameFile() and fileNameAlreadyExists():
			disambiguation += 1
			fileName = originalFileName + str(disambiguation)

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


	def convertToRackedView(self, fileName):

		self.isInRack = True
		self.currentName = fileName



class EventListener(sublime_plugin.EventListener):

	def on_modified(self, view):

		if not view.name():
			# ignore input-views (like search boxes)
			return

		fileInfo = Helper.getOrConstructFileInfoForView(view)

		# put the buffer into the rack if it isn't a file
		if fileInfo.isInRack or not view.file_name():
			fileInfo.onModify()



class DisplayFileRack(sublime_plugin.TextCommand):

	def run(self, edit):

		self.items = self.getFiles()
		self.transientView = None
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

		if self.transientView:
			self.transientView.close()

		if index == -1:
			# quick panel was cancelled
			return


		fileName = self.items[index]

		(window, existingView) = self.getViewFor(fileName)

		if existingView:
			# TODO: work around the fact that the window won't be focused
			window.focus_view(existingView)
			return


		rackedView = sublime.active_window().new_file()

		arguments = dict(filePath = self.getPathForIndex(index), fileName = fileName)
		rackedView.run_command("load_racked_file", arguments)


	def getViewFor(self, fileName):

		for window in sublime.windows():
			for view in window.views():
				fileInfo = Helper.getOrConstructFileInfoForView(view)

				if fileInfo.currentName == fileName:
					return (window, view)

		return (None, None)


	def openFileTransient(self, index):

		self.transientView = sublime.active_window().open_file(self.getPathForIndex(index), sublime.TRANSIENT)



class LoadRackedFile(sublime_plugin.TextCommand):

	def run(self, edit, fileName, filePath):

		with open(filePath, 'r') as f:
			fileContent = f.read()

		fileInfo = Helper.getOrConstructFileInfoForView(self.view)
		fileInfo.convertToRackedView(fileName)

		self.view.insert(edit, 0, fileContent)



class Helper:

	viewToFileInfoMapping = {}

	def __init__(self):

		pass

	@staticmethod
	def getRackPath():

		# TODO: make the path configurable via settings
		return os.path.join(sublime.packages_path(), "FileRack", "files")


	@staticmethod
	def getFileType():

		return ".txt"


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


	@staticmethod
	def sanitizeFileName(filename):

		validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)
		cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
		return ''.join(chr(c) for c in cleanedFilename if chr(c) in validFilenameChars)



# TODO:
# - ensure that racked files behave normally when sublime restores an old session
# 	- one possibility: (de)serialize viewToFileInfoMapping (use buffer ids instead of view references?)
# - create tests
# - ...

