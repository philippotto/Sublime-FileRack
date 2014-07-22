import sublime, sublime_plugin
import os
import datetime
import unicodedata, string
import json

class FileInfo:

	def __init__(self, view):

		self.view = view
		self.lastChangeCount = view.change_count() - 1

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

		# strip the first line and take 50 characters (maximum) as fileName
		fileName = self.view.substr(self.view.line(0)).strip()[:50]

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


	def onModify(self, force=False):

		if not force:

			if not self.isInRack:
				return

			if not self.updateChangeCount():
				# for some reason, the event is triggered multiple times
				return

		deleted = self.deleteIfEmpty()
		if not deleted:
			self.save()


	def save(self):

		self.isInRack = True
		fileName = self.generateName()

		if not self.currentName:
			self.currentName = fileName

		if self.currentName != fileName:
			self.renameTo(fileName)


		filePath = os.path.join(Helper.getRackPath(), fileName)
		bufferContent = self.getBufferContent()

		if bufferContent:
			with open(filePath, 'w') as f:
				f.write(bufferContent)

		else:
			self.delete(filePath)

		self.scratchView()


	def getBufferContent(self):

		contentRegion = sublime.Region(0, self.view.size())
		return self.view.substr(contentRegion)


	def deleteIfEmpty(self):

		if not self.getBufferContent() and self.currentName:
			self.delete()
			return True

		return False


	def delete(self):

		filePath = os.path.join(Helper.getRackPath(), self.currentName)
		try:
			os.remove(filePath)
		except:
			print("FileRack: Couldn't delete file")

		self.isInRack = False
		self.currentName = None
		self.view.set_scratch(False)


	def scratchView(self):

		self.view.set_scratch(True)


	def convertToRackedView(self, fileName):

		self.isInRack = True
		self.currentName = fileName



class EventListener(sublime_plugin.EventListener):

	def on_modified(self, view):

		fileInfo = Helper.getOrConstructFileInfoForView(view)
		fileInfo.isInRack = self.shouldBeInRack(fileInfo)
		fileInfo.onModify()


	def shouldBeInRack(self, fileInfo):

		if fileInfo.isInRack:
			return True

		view = fileInfo.view

		activeGroup = sublime.active_window().active_group()
		activeWindow = sublime.active_window()
		activeViewInActiveGroup = activeWindow.active_view_in_group(activeGroup)

		if view != activeViewInActiveGroup:
			# the given view is not the active view in the active group of the active window
			# so it is not a "real" view -> ignore it
			return False

		if view.is_scratch():
			# scratch views aren't meant to be saved (e.g. search results)
			return False

		if view.file_name():
			# the view shows a file which is already on disk
			return False


		settings = sublime.load_settings("FileRack.sublime-settings")
		explicitSave = settings.get("explicit_save_to_file_rack")

		return not explicitSave


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
		activeWindow = sublime.active_window()

		if existingView:
			if activeWindow == existingView.window():
				window.focus_view(existingView)
				return
			else:
				# since we cannot focus another sublime window, close
				# the file and reopen it in the active window.
				# a better approach would be to move the view to the active window, but
				# unfortunately this isn't possible with the ST API.

				existingView.window().focus_view(existingView)
				existingView.window().run_command("close_file")


		rackedView = activeWindow.new_file()

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
	isTestEnvironment = False

	def __init__(self):

		pass


	@staticmethod
	def getRackPath():

		if Helper.isTestEnvironment:
			return os.path.join(sublime.packages_path(), "FileRack", "tmp_test_files")
		else:
			settings = sublime.load_settings("FileRack.sublime-settings")

			path = settings.get("rack_path")

			if path and not os.path.exists(path):
				message = "The rack_path you supplied in FileRack.sublime-settings doesn't exist. I will use the standard path."
				# TODO
				# message_dialog is probably very annoying; print on the other hand is unlikely to be seen
				# sublime.message_dialog(message)
				print(message)
				path = None

			if not path:
				# TODO: does this path work when FileRack is bundled by package_control
				path = os.path.join(sublime.packages_path(), "FileRack", "files")

			return path


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

		# TODO: why is the json invalid sometimes?
		try:
			with open(Helper.getMetaDataPath(), 'r') as file:
				metadata = json.load(file)
		except:
			print("metadata could not be read properly.")
			metadata = {}

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



class TestFileRack(sublime_plugin.TextCommand):

		def run(self, edit, commandName, argTuple):

			getattr(self, commandName)(self.view, edit, argTuple)


		def insertSomeText(self, view, edit, argTuple):

			self.view.insert(edit, 0, argTuple[0])
			self.onModify(view, edit, ())


		def deleteText(self, view, edit, argTuple):

			self.view.run_command('select_all')
			self.view.run_command('left_delete')


		def onModify(self, view, edit, argTuple):

			fileInfo = Helper.getOrConstructFileInfoForView(view)
			fileInfo.onModify(True)


		def enableTestEnvironment(self, view, edit, argTuple):

			Helper.isTestEnvironment = True


		def disableTestEnvironment(self, view, edit, argTuple):

			Helper.isTestEnvironment = False

