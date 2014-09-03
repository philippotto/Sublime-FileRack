import sublime
from unittest import TestCase
import os, shutil

version = sublime.version()

class TestFileRack(TestCase):

	def setUp(self):

		self.view = sublime.active_window().new_file()
		self.secondView = sublime.active_window().new_file()

		self.runCommand("enableTestEnvironment")
		try:
			os.makedirs(self.getFolderPath())
		except:
			shutil.rmtree(self.getFolderPath())
			os.makedirs(self.getFolderPath())


	def runCommand(self, commandName, argTuple = (), view = None):

		if not view:
			view = self.view

		view.run_command("test_file_rack", dict(commandName = commandName, argTuple = argTuple))


	def tearDown(self):

		for view in [self.view, self.secondView]:
			if view:
				view.set_scratch(True)
				view.window().focus_view(view)
				view.window().run_command("close_file")

		self.runCommand("disableTestEnvironment")
		shutil.rmtree(self.getFolderPath())


	def getFolderPath(self):

		return os.path.join(sublime.packages_path(), "FileRack", "tmp_test_files")


	def getFiles(self):

		return [file for file in os.listdir(self.getFolderPath()) if file.endswith(".txt")]


	def test_simple_racking(self):

		testString = "this is a test"
		self.runCommand("insertSomeText", (testString, ))

		files = self.getFiles()

		self.assertEqual(len(files), 1)
		self.assertEqual(files[0], testString + ".txt")


	def test_renaming(self):

		testString = "this is a test"
		self.runCommand("insertSomeText", (testString, ))
		self.runCommand("insertSomeText", (testString, ))

		files = self.getFiles()

		self.assertEqual(len(files), 1)
		self.assertEqual(files[0], testString + testString + ".txt")


	def test_proper_filename(self):

		testString = "this :is ?a /test"
		escapedTestString = "this is a test"
		self.runCommand("insertSomeText", (testString, ))

		files = self.getFiles()

		self.assertEqual(len(files), 1)
		self.assertEqual(files[0], escapedTestString + ".txt")


	def test_file_deletion(self):

		testString = "this is a test"
		self.runCommand("insertSomeText", (testString, ))
		self.runCommand("deleteText")

		files = self.getFiles()

		self.assertEqual(len(files), 0)


	def test_name_collision(self):

		testString = "this is a test"
		self.runCommand("insertSomeText", (testString, ))
		self.runCommand("insertSomeText", (testString, ), self.secondView)

		files = self.getFiles()

		self.assertEqual(len(files), 2)
		self.assertNotEqual(files[0], files[1])
		self.assertIn(testString + "1.txt", files)


	def test_empty_name(self):

		testString = "    "
		self.runCommand("insertSomeText", (testString, ))

		files = self.getFiles()

		self.assertEqual(len(files), 1)
		self.assertGreater(len(files[0]), 5)
