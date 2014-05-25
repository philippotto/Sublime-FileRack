import sublime, sublime_plugin
import os
import datetime
import unicodedata, string
import json

class FileInfo:

	def __init__(self, view):

		self.view = view
		self.lastChangeCount = view.change_count()

	@property
	def isInRack(self): return self.view.settings().get("isInRack", False)


	@isInRack.setter
	def isInRack(self, value): return self.view.settings().set("isInRack", value)


	@property
	def currentName(self): return self.view.settings().get("currentRackedFileName", None)


	@currentName.setter
	def currentName(self, value):

		self.view.set_name(value or "")
		return self.view.settings().set("currentRackedFileName", value)


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

		isOtherFile = lambda: self.currentName != fileNameWithType()
		fileNameAlreadyExists = lambda: os.path.exists(os.path.join(Helper.getRackPath(), fileNameWithType()))

		disambiguation = 0

		while isOtherFile() and fileNameAlreadyExists():
			disambiguation += 1
			fileName = originalFileName + str(disambiguation)

		return fileName


	def renameTo(self, fileName):

		oldFilePath = os.path.join(Helper.getRackPath(), self.currentName)
		newFilePath = os.path.join(Helper.getRackPath(), fileName)

		os.rename(oldFilePath, newFilePath)
		self.currentName = fileName


	def updateChangeCount(self):

		newChangeCount = self.view.change_count()
		if self.lastChangeCount < newChangeCount:
			self.lastChangeCount = newChangeCount
			return True
		else:
			return False


	def onModify(self):

		if not self.updateChangeCount():
			# for some reason, the event is triggered multiple times
			return

		contentRegion = sublime.Region(0, self.view.size())
		bufferContent = self.view.substr(contentRegion)

		if not bufferContent:
			if self.isInRack and self.currentName:
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


	def on_post_text_command(self, view, command_name, args):

		if command_name == "set_file_type":
			Helper.saveSyntax(view)



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


	def getFilePathByIndex(self, index):

		fileName = self.items[index]
		return os.path.join(Helper.getRackPath(), fileName)


	def getFileNameByIndex(self, index):

		return self.items[index]


	def openFile(self, index):

		if self.transientView:
			self.transientView.close()

		if index == -1:
			# quick panel was cancelled
			return


		fileName = self.getFileNameByIndex(index)

		(window, existingView) = self.getViewFor(fileName)

		if existingView:
			# TODO: work around the fact that the window won't be focused
			window.focus_view(existingView)
			return


		rackedView = sublime.active_window().new_file()

		arguments = dict(filePath = self.getFilePathByIndex(index), fileName = fileName)
		rackedView.run_command("load_racked_file", arguments)


	def getViewFor(self, fileName):

		for window in sublime.windows():
			for view in window.views():
				fileInfo = Helper.getOrConstructFileInfoForView(view)

				if fileInfo.currentName == fileName:
					return (window, view)

		return (None, None)


	def openFileTransient(self, index):

		self.transientView = sublime.active_window().open_file(self.getFilePathByIndex(index), sublime.TRANSIENT)
		Helper.setSyntax(self.transientView, self.getFileNameByIndex(index))



class LoadRackedFile(sublime_plugin.TextCommand):

	def run(self, edit, fileName, filePath):

		with open(filePath, 'r') as f:
			fileContent = f.read()

		fileInfo = Helper.getOrConstructFileInfoForView(self.view)
		fileInfo.convertToRackedView(fileName)

		self.view.insert(edit, 0, fileContent)
		self.view.set_name(fileName)

		Helper.setSyntax(self.view, fileName)



class Helper:

	viewToFileInfoMapping = {}

	def __init__(self):

		pass

	@staticmethod
	def getRackPath():

		# TODO: make the path configurable via settings
		return os.path.join(sublime.packages_path(), "FileRack", "files")


	@staticmethod
	def getMetaDataPath():

		return os.path.join(Helper.getRackPath(), 'index.json')


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
	def getMetaData():

		if not os.path.exists(Helper.getMetaDataPath()):
			return {}

		with open(Helper.getMetaDataPath(), 'r') as file:
			metadata = json.load(file)

		return metadata


	@staticmethod
	def saveSyntax(view):

		metadata = Helper.getMetaData()

		fileInfo = Helper.getOrConstructFileInfoForView(view)
		metadata[fileInfo.currentName] = fileInfo.view.settings().get('syntax')

		with open(Helper.getMetaDataPath(), 'w') as file:
			json.dump(metadata, file, sort_keys = True, indent = 4, ensure_ascii = False)


	@staticmethod
	def getSyntax(fileName):

		metadata = Helper.getMetaData()

		if fileName in metadata:
			return metadata[fileName]
		else:
			return None


	@staticmethod
	def setSyntax(view, fileName):

		syntax = Helper.getSyntax(fileName)
		if syntax:
			view.set_syntax_file(syntax)


	@staticmethod
	def sanitizeFileName(filename):

		validFilenameChars = "-_.() %s%s" % (string.ascii_letters, string.digits)
		cleanedFilename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
		return ''.join(chr(c) for c in cleanedFilename if chr(c) in validFilenameChars)



# TODO:
# - create tests
# - ...

