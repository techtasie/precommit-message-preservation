# pylint: disable=no-self-use
"All the tests."
import argparse
import contextlib
import os
from pathlib import Path
import subprocess
import unittest
import unittest.mock

import precommit_message_preservation as pmp

def args():
	"Create args we can use to make a GetAndPreserveMessage"
	parser = argparse.ArgumentParser()
	pmp.add_arguments(parser)
	return parser.parse_args(["somefile.txt"])


@contextlib.contextmanager
def fake_repository(repository: Path, repository_branch: str):
	"Set up a fake repository root and branch."
	with unittest.mock.patch("precommit_message_preservation.get_repository", return_value=repository):
		with unittest.mock.patch("precommit_message_preservation.get_repository_branch", return_value=repository_branch):
			yield


@contextlib.contextmanager
def known_xdg_cache(location: str):
	"Set fake XDG cache for tests."
	with unittest.mock.patch("precommit_message_preservation.xdg_cache_home", return_value=Path(location)):
		yield


class Tests(unittest.TestCase): # pylint: disable=too-many-public-methods
	"All the tests."
	def test_clear_comments_no_comments(self):
		"Don't remove lines that just have '#' in the middle."
		content = "This is\nsome content\nthat only has '#' in the wrong places."
		result = pmp.clear_comments(content)
		self.assertEqual(content, result)

	def test_clear_comments_with_comments(self):
		"Remove any lines that start with '#'."
		content = "This line is fine.\n# This one isn't\nBut this is okay"
		result = pmp.clear_comments(content)
		self.assertEqual(result, "This line is fine.\nBut this is okay")

	def test_clear_comments_empty_lines(self):
		"Ensure we properly handle empty lines when clearing comments."
		content = "This is the summary\n\nthis is the body."
		result = pmp.clear_comments(content)
		self.assertEqual(result, content)

	def test_clear_verbose_code_no_marker(self):
		"Don't remove any content without a code marker."
		content = "This is just content\n# That has comments\nBut no marker."
		result = pmp.clear_verbose_code(content)
		self.assertEqual(content, result)

	def test_clear_verbose_code_with_marker(self):
		"Remove all content after the marker."
		lines = [
			"This is just content",
			"And this is more.",
			pmp.VERBOSE_MARKER,
			"Pretend this is code."
			"And this too."
		]
		result = pmp.clear_verbose_code("\n".join(lines))
		self.assertEqual("\n".join(lines[:2]) + "\n", result)

	def test_get_repository_branch(self):
		"Get the repository branch."
		with unittest.mock.patch("subprocess.check_output", autospec=subprocess.check_output, return_value=b"develop") as check_output:
			root = pmp.get_repository_branch()
			check_output.assert_called_with(["git", "branch", "--show-current"])
			self.assertEqual(root, "develop")

	def test_get_repository_branch_failed(self):
		"Fail to get the repository branch."
		with unittest.mock.patch("subprocess.check_output",
				autospec=subprocess.check_output,
				side_effect=subprocess.CalledProcessError(1, "git")) as check_output:
			root = pmp.get_repository_branch()
			check_output.assert_called_with(["git", "branch", "--show-current"])
			self.assertEqual(root, "unknown")

	def test_get_repository(self):
		"Get the repository root."
		with unittest.mock.patch("subprocess.check_output",
				autospec=subprocess.check_output,
				return_value=b"/some/repository/.git") as check_output:
			root = pmp.get_repository()
			check_output.assert_called_with(["git", "rev-parse", "--git-dir"])
			self.assertEqual(root, Path("/some/repository"))

	def test_get_repository_failed(self):
		"Fail to get the repository root."
		with unittest.mock.patch("subprocess.check_output",
				autospec=subprocess.check_output,
				side_effect=subprocess.CalledProcessError(1, "git")) as check_output:
			root = pmp.get_repository()
			check_output.assert_called_with(["git", "rev-parse", "--git-dir"])
			self.assertEqual(root, Path(os.path.abspath(".")))

	def test_message_preservation_success(self):
		"Message cache should be removed on successful exit from MessagePreservation"
		repo = Path("/repo")
		with fake_repository(repo, "a-branch"):
			with unittest.mock.patch("precommit_message_preservation.remove_message_cache") as remove:
				with pmp.GetAndPreserveMessage(args()):
					pass
				remove.assert_called_with(repo, "a-branch")

	def test_message_preservation_failure(self):
		"Message cache should be saved on unsuccessful exit from MessagePreservation"
		repo = Path("/repo")
		with fake_repository(repo, "a-branch"):
			with unittest.mock.patch("precommit_message_preservation.save_commit_message") as save:
				with self.assertRaises(Exception):
					with pmp.GetAndPreserveMessage(args()):
						raise Exception("for testing.")
					save.assert_called_with(repo, "a-branch")
